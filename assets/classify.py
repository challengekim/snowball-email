#!/usr/bin/env python3
"""Pluggable classifier (PLAN.md §10 W2, opt-in).

Backends:
    substring        — default. Free, offline, no API key. W1 baseline.
    llm_anthropic    — opt-in. Uses ANTHROPIC_API_KEY env. Single HTTP call,
                       returns (classification, confidence, llm_flags).

API:
    classify(parsed, pattern_ids, *, cfg, compiled_md="")
        -> (classification: str, confidence: float, llm_flags: dict)

cfg keys (read from inbox config.yaml):
    classify.backend       — substring | llm_anthropic    (default: substring)
    classify.api_key_env   — env var name with API key    (default: ANTHROPIC_API_KEY)
    classify.model         — model id                     (default: claude-haiku-4-5-20251001)

The substring backend never raises. The llm_anthropic backend falls back to
substring on any error (missing key, network failure, parse error) and prints
the cause to stderr. This keeps the skill usable when W2 is not configured.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

MONEY_TOKENS = re.compile(
    r"(?:₩|KRW|USD|\$|€|¥)\s*[\d,]+|\d{1,3}(?:,\d{3})+\s*(?:원|만원|달러|불)|\d+\s*(?:원|만원|달러|불)"
)
URL_TOKENS = re.compile(r"https?://[^\s)\]>'\"]+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def classify(parsed: dict, pattern_ids: list[str], *,
             cfg: dict | None = None, compiled_md: str = "") -> tuple[str, float, dict]:
    cfg = cfg or {}
    backend = (cfg.get("classify", {}).get("backend") or "substring").lower()
    if backend == "llm_anthropic":
        try:
            return _classify_llm_anthropic(parsed, pattern_ids, cfg, compiled_md)
        except Exception as e:  # noqa: BLE001 — fall back regardless of failure mode
            print(f"[classify] llm_anthropic fallback to substring: {e}", file=sys.stderr)
    return _classify_substring(parsed, pattern_ids)


# ---------------------------------------------------------------------------
# Substring backend (W1 baseline, always available)
# ---------------------------------------------------------------------------
def _classify_substring(parsed: dict, pattern_ids: list[str]) -> tuple[str, float, dict]:
    haystack = (parsed.get("subject", "") + "\n" + parsed.get("body_text", "")).lower()
    flags = _regex_flags(haystack)
    for pid in pattern_ids:
        token = pid.replace("_", " ").lower()
        if token and token in haystack:
            return pid, 0.95, flags
    return "UNKNOWN", 0.4, flags


# ---------------------------------------------------------------------------
# LLM backend (W2 opt-in)
# ---------------------------------------------------------------------------
def _classify_llm_anthropic(parsed: dict, pattern_ids: list[str], cfg: dict,
                            compiled_md: str) -> tuple[str, float, dict]:
    classify_cfg = cfg.get("classify") or {}
    api_key_env = classify_cfg.get("api_key_env") or "ANTHROPIC_API_KEY"
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"env {api_key_env} not set")
    model = classify_cfg.get("model") or DEFAULT_MODEL

    pattern_list = "\n".join(f"- {p}" for p in pattern_ids) or "- (none yet)"
    system = (
        "You are a strict email classifier for a customer-support inbox. "
        "Return ONLY a single compact JSON object with keys: "
        "classification (one of the listed pattern ids OR \"UNKNOWN\"), "
        "confidence (number 0–1), money (boolean), external_link (boolean). "
        "Do not invent new pattern ids. Be conservative — prefer UNKNOWN over a bad guess.\n\n"
        f"Available patterns:\n{pattern_list}\n\n"
        f"Reference (truncated):\n{(compiled_md or '')[:4000]}"
    )
    user = (
        f"Subject: {parsed.get('subject','')}\n"
        f"From: {parsed.get('from','')}\n\n"
        f"Body:\n{(parsed.get('body_text','') or '')[:3000]}"
    )

    payload = {
        "model": model,
        "max_tokens": 200,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    blocks = data.get("content") or []
    text = next((b.get("text", "") for b in blocks if b.get("type") == "text"), "")
    obj = _extract_json(text)
    if not obj:
        raise RuntimeError(f"could not parse JSON from model output: {text[:200]}")

    cls = str(obj.get("classification") or "UNKNOWN").strip()
    if cls != "UNKNOWN" and cls not in pattern_ids:
        # Model hallucinated a pattern id → demote to UNKNOWN per conservative bias.
        cls = "UNKNOWN"
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    flags = {
        "money": bool(obj.get("money", False)),
        "external_link": bool(obj.get("external_link", False)),
    }
    # Combine with regex flags (OR) so dual-gate stays sensitive
    rflags = _regex_flags((parsed.get("subject", "") + "\n" + parsed.get("body_text", "")).lower())
    flags["money"] = flags["money"] or rflags["money"]
    flags["external_link"] = flags["external_link"] or rflags["external_link"]
    return cls, max(0.0, min(1.0, conf)), flags


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    # Take the first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _regex_flags(haystack: str) -> dict:
    return {
        "money": bool(MONEY_TOKENS.search(haystack)),
        "external_link": bool(URL_TOKENS.search(haystack)),
    }


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------
def _selftest() -> int:
    fails = 0
    sample = {"subject": "refund request",
              "from": "user@example.com",
              "body_text": "Please process my refund request — total 50,000원. "
                           "See https://x.example/a for details."}

    cls, conf, flags = classify(sample, ["refund_request"], cfg={})
    ok = cls == "refund_request" and conf > 0.9 and flags["money"] and flags["external_link"]
    print(f"[{'OK' if ok else 'FAIL'}] substring backend hit: cls={cls} conf={conf} flags={flags}")
    if not ok:
        fails += 1

    cls2, conf2, _ = classify({"subject": "x", "body_text": "x"}, ["refund_request"], cfg={})
    ok = cls2 == "UNKNOWN" and conf2 < 0.5
    print(f"[{'OK' if ok else 'FAIL'}] substring backend miss: cls={cls2} conf={conf2}")
    if not ok:
        fails += 1

    cls3, conf3, _ = classify(sample, ["refund_request"],
                              cfg={"classify": {"backend": "llm_anthropic",
                                                "api_key_env": "DEFINITELY_NOT_SET_XYZ"}})
    ok = cls3 == "refund_request" and conf3 > 0.9
    print(f"[{'OK' if ok else 'FAIL'}] llm backend no-key fallback: cls={cls3} conf={conf3}")
    if not ok:
        fails += 1

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(_selftest())
