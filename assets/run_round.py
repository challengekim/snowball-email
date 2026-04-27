#!/usr/bin/env python3
"""Round orchestrator (PLAN.md §10 W1 deliverable, SKILL.md 8-step workflow).

  fetch_unread → parse_thread → classify → draft
       → present_approval_table → dispatch_send
       → mark_read → reference_append + metrics_log

Stdlib-only. gws cli is invoked via subprocess. Reference store + tier classifier
+ metrics logger are imported from sibling modules.

Dry-run modes:
    --dry-run                       Use mock fixture (assets/_mock_unread.json) and
                                    simulate every side effect (no Gmail mutation,
                                    no send, no mark-read).
    --fixture <path>                Override the mock fixture path.
    --auto-approve                  Skip stdin prompt (CI / smoketest only).
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import email
import email.policy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("SUPPORT_REPLY_HOME",
                           Path.home() / ".claude/skills/support-reply-public"))

sys.path.insert(0, str(HOME / "approval"))
sys.path.insert(0, str(HOME / "metrics"))
sys.path.insert(0, str(HOME / "assets"))

from tier_classifier import Draft as TierDraft, classify_tier  # noqa: E402
from logger import append_round  # noqa: E402
import reference_store  # noqa: E402
import send_backends  # noqa: E402
import classify as classifier  # noqa: E402


CALIBRATION_INITIAL_ROUNDS = 30
CALIBRATION_PERIODIC_EVERY = 50


# ---------------------------------------------------------------------------
# Config loader (minimal stdlib YAML-ish — flat key:value or key.subkey:value)
# ---------------------------------------------------------------------------
def load_config(inbox_dir: Path) -> dict:
    p = inbox_dir / "config.yaml"
    if not p.exists():
        return _default_config(inbox_dir.name)
    cfg: dict = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        keys = key.strip().split(".")
        val = val.strip().strip('"').strip("'")
        d = cfg
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = val
    return cfg


def _default_config(inbox_name: str) -> dict:
    return {
        "inbox": {"name": inbox_name, "label": ""},
        "send": {"backend": "gws_drafts", "from_email": "", "from_name": "",
                 "bcc": "", "sendgrid": {"api_key_env": "SENDGRID_API_KEY"}},
        "draft": {"signoff": "감사합니다.\n", "language": "ko"},
    }


# ---------------------------------------------------------------------------
# Step 1: fetch unread
# ---------------------------------------------------------------------------
def fetch_unread(label: str, *, max_results: int = 20) -> list[dict]:
    q = f"label:{label} is:unread" if label else "is:unread"
    params = {"userId": "me", "q": q, "maxResults": max_results}
    proc = subprocess.run(
        ["gws", "gmail", "users", "messages", "list", "--params", json.dumps(params)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gws messages list failed: {proc.stderr.strip()[:300]}")
    data = json.loads(proc.stdout or "{}")
    return data.get("messages") or []


def fetch_message_full(msg_id: str) -> dict:
    params = {"userId": "me", "id": msg_id, "format": "full"}
    proc = subprocess.run(
        ["gws", "gmail", "users", "messages", "get", "--params", json.dumps(params)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gws messages get failed for {msg_id}: {proc.stderr.strip()[:300]}")
    return json.loads(proc.stdout or "{}")


# ---------------------------------------------------------------------------
# Step 2: parse thread
# ---------------------------------------------------------------------------
def parse_message(msg_full: dict) -> dict:
    """Extract headers + plaintext body from Gmail messages.get full payload."""
    payload = msg_full.get("payload") or {}
    headers = {h["name"].lower(): h["value"] for h in (payload.get("headers") or [])}
    text = _extract_plain_body(payload)
    return {
        "gmail_id": msg_full.get("id", ""),
        "thread_id": msg_full.get("threadId", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "message_id": headers.get("message-id", ""),
        "in_reply_to": headers.get("in-reply-to", ""),
        "date": headers.get("date", ""),
        "body_text": _strip_quoted(text),
        "label_ids": msg_full.get("labelIds") or [],
    }


def _extract_plain_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = (payload.get("body") or {}).get("data", "")
        return _b64url_decode(data)
    if mime.startswith("multipart/"):
        for part in payload.get("parts") or []:
            if part.get("mimeType") == "text/plain":
                data = (part.get("body") or {}).get("data", "")
                if data:
                    return _b64url_decode(data)
        for part in payload.get("parts") or []:
            sub = _extract_plain_body(part)
            if sub:
                return sub
    if mime == "text/html":
        data = (payload.get("body") or {}).get("data", "")
        html = _b64url_decode(data)
        return _html_to_text_minimal(html)
    return ""


def _b64url_decode(data: str) -> str:
    if not data:
        return ""
    pad = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + pad).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _html_to_text_minimal(html: str) -> str:
    import re
    txt = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    txt = re.sub(r"</p>", "\n\n", txt, flags=re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", "", txt)
    return txt


def _strip_quoted(text: str) -> str:
    out = []
    for ln in text.splitlines():
        if ln.startswith(">"):
            continue
        if ln.strip().startswith("-----Original Message-----"):
            break
        if ln.strip().startswith("On ") and ln.strip().endswith("wrote:"):
            break
        out.append(ln)
    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# Step 3: classify
# ---------------------------------------------------------------------------
def classify_message(parsed: dict, pattern_ids: list[str]) -> tuple[str, float]:
    """Rule-based classification against pattern ids in the reference.

    Pattern id is matched as a case-insensitive substring of the body or subject.
    Confidence is 0.95 on hit, 0.4 when nothing matches (UNKNOWN).
    The full-fidelity LLM-driven classifier is W2 scope (PLAN.md §10).
    """
    haystack = (parsed.get("subject", "") + "\n" + parsed.get("body_text", "")).lower()
    for pid in pattern_ids:
        token = pid.replace("_", " ").lower()
        if token and token in haystack:
            return pid, 0.95
    return "UNKNOWN", 0.4


# ---------------------------------------------------------------------------
# Step 4: draft (template-based; LLM-fancier drafter is W2)
# ---------------------------------------------------------------------------
def build_draft(parsed: dict, classification: str, cfg: dict) -> dict:
    signoff = cfg.get("draft", {}).get("signoff", "감사합니다.\n")
    body_text = (
        f"{_addressee(parsed.get('from', ''))} 님, 안녕하세요.\n\n"
        f"{_template_body_text(classification)}\n\n"
        f"{signoff}{cfg.get('send', {}).get('from_name', '')} 드림\n"
    )
    body_html = (
        "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Malgun Gothic',sans-serif;"
        "font-size:15px;line-height:1.6;color:#222;max-width:640px\">"
        f"<p>{_addressee(parsed.get('from', ''))} 님, 안녕하세요.</p>"
        f"<p>{_template_body_text(classification)}</p>"
        f"<p style='margin-top:20px;color:#666'>{signoff.strip()}<br>"
        f"{cfg.get('send', {}).get('from_name', '')} 드림</p>"
        "</div>"
    )
    subject = parsed.get("subject", "")
    if subject and not subject.lower().startswith("re:"):
        subject = "Re: " + subject
    return {
        "to_email": _email_only(parsed.get("from", "")),
        "to_name": _name_only(parsed.get("from", "")),
        "subject": subject or "Re:",
        "body_text": body_text,
        "body_html": body_html,
        "in_reply_to": parsed.get("message_id", ""),
        "references": [parsed["message_id"]] if parsed.get("message_id") else [],
        "gmail_id": parsed.get("gmail_id", ""),
        "thread_id": parsed.get("thread_id", ""),
        "_classification": classification,
    }


def _template_body_text(classification: str) -> str:
    if classification == "UNKNOWN":
        return ("문의 내용 확인했습니다. 담당자가 회신 드릴 수 있도록 자세한 내용 한 번 더 정리해 "
                "주실 수 있을까요?")
    return ("문의해 주신 내용 확인했습니다. 관련해서 안내 도와드리겠습니다. "
            "추가로 궁금하신 부분 있으시면 회신 부탁드립니다.")


def _email_only(s: str) -> str:
    if "<" in s and ">" in s:
        return s.split("<", 1)[1].split(">", 1)[0].strip()
    return s.strip()


def _name_only(s: str) -> str:
    if "<" in s:
        return s.split("<", 1)[0].strip().strip('"')
    return ""


def _addressee(from_field: str) -> str:
    return _name_only(from_field) or _email_only(from_field).split("@", 1)[0] or "고객"


# ---------------------------------------------------------------------------
# Step 5: approval gate
# ---------------------------------------------------------------------------
def present_approval(drafts: list[dict], tiers: list[str], *,
                     auto_approve: bool = False) -> list[dict]:
    """Print compact summary table; return list of approved drafts.

    Acceptable user inputs:
        all            → approve all
        n              → approve only draft #n
        n,m,k          → approve listed
        n-m            → range
        skip / none    → approve none
    """
    print("\n┌─ 분류/회신 초안 ───────────────────────────────────────")
    for i, (d, t) in enumerate(zip(drafts, tiers), 1):
        first = (d.get("body_text") or "").splitlines()
        first_line = first[0] if first else ""
        print(f"│ [{i}] tier-{t} · {d.get('_classification','?'):<16} · {d.get('to_email','')}")
        print(f"│      Subject: {d.get('subject','')}")
        print(f"│      {first_line[:80]}")
    print("└────────────────────────────────────────────────────────\n")
    if auto_approve:
        print("[approval] --auto-approve set; approving all drafts.", file=sys.stderr)
        return list(drafts)
    print("발송 선택? all / n / n,m / n-m / skip : ", end="", flush=True)
    try:
        choice = sys.stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    return _resolve_choice(choice, drafts)


def _resolve_choice(choice: str, drafts: list[dict]) -> list[dict]:
    if choice in ("", "skip", "none", "n"):
        return []
    if choice in ("all", "a", "전부"):
        return list(drafts)
    selected: set[int] = set()
    for tok in choice.replace(" ", "").split(","):
        if "-" in tok:
            try:
                lo, hi = (int(x) for x in tok.split("-", 1))
                for i in range(lo, hi + 1):
                    selected.add(i)
            except ValueError:
                continue
        else:
            try:
                selected.add(int(tok))
            except ValueError:
                continue
    return [d for i, d in enumerate(drafts, 1) if i in selected]


# ---------------------------------------------------------------------------
# Step 6/7: dispatch + mark read
# ---------------------------------------------------------------------------
def mark_read(gmail_id: str, *, dry_run: bool) -> dict:
    if dry_run or not gmail_id:
        return {"status": "dry_run", "id": gmail_id}
    params = {
        "userId": "me",
        "id": gmail_id,
        "body": {"removeLabelIds": ["UNREAD"]},
    }
    proc = subprocess.run(
        ["gws", "gmail", "users", "messages", "modify", "--params", json.dumps(params)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        return {"status": "error", "id": gmail_id, "error": proc.stderr.strip()[:300]}
    return {"status": "ok", "id": gmail_id}


# ---------------------------------------------------------------------------
# Step 8: reference append + metrics
# ---------------------------------------------------------------------------
def maybe_append_unknown_pattern(inbox_dir: Path, parsed: dict,
                                 classification: str) -> int:
    """If classification is UNKNOWN, write a STUB pattern for human curation.
    Stays under Pin-2 1/round budget by emitting at most one stub per round.
    Returns count of patterns appended (0 or 1).
    """
    if classification != "UNKNOWN":
        return 0
    stub_id = f"unknown_{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%dt%H%M%S')}"
    body = (
        f"## Trigger keywords (TODO — human review)\n\n"
        f"_subject:_ {parsed.get('subject','')}\n\n"
        f"_first 200 chars:_ {(parsed.get('body_text','') or '')[:200]}\n\n"
        f"## Reply tone (TODO)\n\n초안 작성 후 사람이 채워주세요.\n"
    )
    return 1 if reference_store.append_pattern(inbox_dir, stub_id, body) else 0


# ---------------------------------------------------------------------------
# Calibration & round id
# ---------------------------------------------------------------------------
def _round_count(inbox_dir: Path) -> int:
    p = inbox_dir / "metrics.jsonl"
    if not p.exists():
        return 0
    return sum(1 for _ in p.open(encoding="utf-8"))


def _is_calibration(round_count: int) -> bool:
    if round_count < CALIBRATION_INITIAL_ROUNDS:
        return True
    return round_count > 0 and (round_count % CALIBRATION_PERIODIC_EVERY) == 0


def _round_id() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
def run(inbox: str, *, dry_run: bool = False, fixture: str | None = None,
        auto_approve: bool = False) -> int:
    inbox_dir = HOME / "inboxes" / inbox
    inbox_dir.mkdir(parents=True, exist_ok=True)
    reference_store.ensure_layout(inbox_dir)

    cfg = load_config(inbox_dir)
    label = cfg.get("inbox", {}).get("label", "")
    print(f"[run] inbox={inbox} label={label!r} dry_run={dry_run}", file=sys.stderr)

    if dry_run:
        fixture_path = Path(fixture) if fixture else (HOME / "assets" / "_mock_unread.json")
        if not fixture_path.exists():
            print(f"[run] mock fixture not found: {fixture_path}", file=sys.stderr)
            return 1
        messages_full = json.loads(fixture_path.read_text(encoding="utf-8"))
    else:
        if not label:
            print("[run] inbox.label required for live run; set via `support-reply config set inbox.label <name>`",
                  file=sys.stderr)
            return 1
        msgs = fetch_unread(label)
        messages_full = [fetch_message_full(m["id"]) for m in msgs]

    parsed = [parse_message(m) for m in messages_full]
    if not parsed:
        print("[run] no unread messages — nothing to do", file=sys.stderr)
        return 0

    pattern_ids = reference_store.list_pattern_ids(inbox_dir)
    compiled_md = reference_store.load_compiled(inbox_dir) if pattern_ids else ""
    classifications = [classifier.classify(p, pattern_ids, cfg=cfg, compiled_md=compiled_md)
                       for p in parsed]
    drafts = [build_draft(p, c[0], cfg) for p, c in zip(parsed, classifications)]

    round_count = _round_count(inbox_dir)
    calibration = _is_calibration(round_count)
    first_send_for_inbox = round_count == 0
    known_links_path = inbox_dir / "reference" / "links.md"
    known_links = []
    if known_links_path.exists():
        for ln in known_links_path.read_text(encoding="utf-8").splitlines():
            if "|" in ln:
                known_links.append(ln.split("|", 1)[1].strip())

    tiers: list[str] = []
    for d, (cls, conf, flags) in zip(drafts, classifications):
        td = TierDraft(body=d["body_text"], classification=cls, confidence=conf,
                       llm_flags=flags or None)
        tiers.append(classify_tier(td, known_links=known_links,
                                   calibration_mode=calibration,
                                   first_send_for_inbox=first_send_for_inbox))

    approved = present_approval(drafts, tiers, auto_approve=auto_approve)

    send_results: list[dict] = []
    tier_a_count = sum(1 for t in tiers if t == "A")
    tier_b_count = sum(1 for t in tiers if t == "B")
    tier_b_handtime_start = time.time()
    new_patterns = 0
    unknown_count = sum(1 for c, _, _ in classifications if c == "UNKNOWN")

    auto_case = str(cfg.get("learn", {}).get("auto_case", "false")).lower() in ("true", "1", "yes")
    cases_appended = 0
    for d in approved:
        res = send_backends.dispatch(d, cfg=cfg, dry_run=dry_run)
        send_results.append(res)
        if res.get("status") in ("ok", "dry_run"):
            mr = mark_read(d.get("gmail_id", ""), dry_run=dry_run)
            res["mark_read"] = mr
        for p, (cls, _, _flags) in zip(parsed, classifications):
            if p.get("gmail_id") == d.get("gmail_id"):
                new_patterns += maybe_append_unknown_pattern(inbox_dir, p, cls)
                if auto_case and not dry_run and res.get("status") == "ok" and cls != "UNKNOWN":
                    reference_store.append_case(inbox_dir, cls, {
                        "thread_id": p.get("thread_id", ""),
                        "subject": p.get("subject", ""),
                        "reply_first_line": (d.get("body_text") or "").splitlines()[:1],
                    })
                    cases_appended += 1
                break

    if new_patterns:
        reference_store.rebuild_compiled(inbox_dir)

    metrics_path = append_round(
        inbox,
        round_id=_round_id(),
        drafts=[{"approved": d["body_text"], "draft": d["body_text"]} for d in approved],
        unknown_count=unknown_count,
        new_patterns=new_patterns,
        tier_a_count=tier_a_count,
        tier_b_count=tier_b_count,
        tier_b_handtime_sec=(time.time() - tier_b_handtime_start) * (tier_b_count > 0),
        send_status=("dry_run" if dry_run else
                     "ok" if all(r.get("status") == "ok" for r in send_results)
                     else "partial" if send_results else "skipped"),
    )
    print(f"[run] done — drafts={len(drafts)} approved={len(approved)} "
          f"tier_a={tier_a_count} tier_b={tier_b_count} unknown={unknown_count} "
          f"new_patterns={new_patterns} metrics={metrics_path}", file=sys.stderr)
    print(json.dumps({"send_results": send_results}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixture", help="Path to mock fixture JSON (dry-run only)")
    ap.add_argument("--auto-approve", action="store_true")
    args = ap.parse_args()
    return run(args.inbox, dry_run=args.dry_run, fixture=args.fixture,
               auto_approve=args.auto_approve)


if __name__ == "__main__":
    sys.exit(main())
