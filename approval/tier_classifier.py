#!/usr/bin/env python3
"""2-tier approval classifier with conservative bias (PLAN §8.1, Pin-1).

classify_tier(draft) -> 'A' | 'B'

Tier A triggers (any one):
  (a) calibration_mode (first 30 rounds + every 50 round recalibration)
  (b) classification == 'UNKNOWN'
  (c) draft contains money amount (regex)         — dual-gate (regex AND llm)
  (d) draft contains a non-canonical link         — dual-gate (regex AND llm)
  (e) classifier confidence < 0.85
  (f) first_send_for_inbox

Conservative bias: any uncertainty defaults to tier-A (single-confirm).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

CONFIDENCE_FLOOR = 0.85
MONEY_REGEX = re.compile(
    r"(?:₩|KRW|USD|\$|EUR|€|JPY|¥)\s*[\d,]+(?:\.\d+)?"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:원|만원|달러|불)"
    r"|\d+\s*(?:원|만원|달러|불)"
)
URL_REGEX = re.compile(r"https?://[^\s)\]>'\"]+", re.IGNORECASE)


@dataclass
class Draft:
    body: str
    classification: str = "UNKNOWN"
    confidence: float = 0.0
    llm_flags: dict[str, bool] | None = None  # {"money": bool, "external_link": bool}


def _has_money_regex(text: str) -> bool:
    return bool(MONEY_REGEX.search(text))


def _external_links(text: str, known_links: Iterable[str]) -> list[str]:
    found = URL_REGEX.findall(text)
    known = {u.strip().lower() for u in known_links if u.strip()}
    return [u for u in found if not any(u.lower().startswith(k) for k in known)]


def classify_tier(
    draft: Draft,
    *,
    known_links: Iterable[str] = (),
    calibration_mode: bool = False,
    first_send_for_inbox: bool = False,
) -> str:
    """Return 'A' (single-confirm) or 'B' (batch-confirm)."""
    # (a) calibration mode forces tier-A on every draft
    if calibration_mode:
        return "A"
    # (f) first send for this inbox
    if first_send_for_inbox:
        return "A"
    # (b) UNKNOWN classification → tier-A
    if (draft.classification or "").upper() == "UNKNOWN":
        return "A"
    # (e) low classifier confidence → tier-A (conservative bias)
    if draft.confidence < CONFIDENCE_FLOOR:
        return "A"
    # (c) money trigger — dual-gate: regex AND llm
    money_regex = _has_money_regex(draft.body)
    money_llm = bool((draft.llm_flags or {}).get("money", False))
    if money_regex and money_llm:
        return "A"
    # (d) non-canonical link — dual-gate: regex AND llm
    ext = _external_links(draft.body, known_links)
    link_llm = bool((draft.llm_flags or {}).get("external_link", False))
    if ext and link_llm:
        return "A"
    # otherwise tier-B
    return "B"


# --- minimal self-test (pytest-free) ----------------------------------------
def _selftest() -> int:
    fixtures = [
        # (draft, expected_tier, label)
        (Draft(body="안녕하세요 환불 가능한가요?", classification="refund_request",
               confidence=0.92, llm_flags={"money": False, "external_link": False}),
         "B", "plain refund question"),
        (Draft(body="총 50,000원 환불 가능 여부 부탁드립니다.", classification="refund_request",
               confidence=0.95, llm_flags={"money": True}),
         "A", "money mentioned + dual-gate match"),
        (Draft(body="자료는 https://malicious.example/abc 에서 받아주세요.",
               classification="info_share", confidence=0.91,
               llm_flags={"external_link": True}),
         "A", "non-canonical link + dual-gate match"),
        (Draft(body="문의 주신 내용 확인 중입니다.", classification="UNKNOWN", confidence=0.4),
         "A", "UNKNOWN classification"),
        (Draft(body="감사합니다.", classification="ack", confidence=0.7),
         "A", "low confidence < 0.85"),
    ]
    fails = 0
    for d, expected, label in fixtures:
        got = classify_tier(d, known_links=["https://canonical.example/"])
        ok = got == expected
        print(f"[{'OK' if ok else 'FAIL'}] {label}: expected={expected} got={got}")
        if not ok:
            fails += 1
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
