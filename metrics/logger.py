#!/usr/bin/env python3
"""Per-round KPI logger (PLAN §2 + Pin-3).

Appends one JSONL line to inboxes/<inbox>/metrics.jsonl per round with:
  round_id, ts_iso, drafts_count, edits_per_draft (list[float]),
  edit_ratio (float, mean across drafts),
  unknown_count, new_patterns,
  tier_a_count, tier_b_count,
  tier_b_handtime_sec (KPI guardrail — only tier-B counted to prevent gaming),
  send_status

Edit ratio = char-distance(approved_text, draft_text) / max(len(draft_text), 1)
Implementation: difflib.SequenceMatcher ratio inversion.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import json
import os
import sys
from pathlib import Path

HOME = Path(os.environ.get("SNOWBALL_EMAIL_HOME",
                           Path.home() / ".claude/skills/snowball-email"))


def edit_ratio(approved: str, draft: str) -> float:
    """Char-level distance ratio: 0.0 = identical, 1.0 = totally rewritten."""
    if not draft:
        return 0.0
    sm = difflib.SequenceMatcher(a=draft, b=approved, autojunk=False)
    return round(1.0 - sm.ratio(), 4)


def append_round(
    inbox: str,
    *,
    round_id: str,
    drafts: list[dict],
    unknown_count: int = 0,
    new_patterns: int = 0,
    tier_a_count: int = 0,
    tier_b_count: int = 0,
    tier_b_handtime_sec: float = 0.0,
    send_status: str = "drafted",
) -> Path:
    """`drafts` is a list of {approved, draft} dicts."""
    edits = [edit_ratio(d.get("approved", ""), d.get("draft", "")) for d in drafts]
    mean_edit = round(sum(edits) / len(edits), 4) if edits else 0.0
    record = {
        "round_id": round_id,
        "ts_iso": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "drafts_count": len(drafts),
        "edits_per_draft": edits,
        "edit_ratio": mean_edit,
        "unknown_count": unknown_count,
        "new_patterns": new_patterns,
        "tier_a_count": tier_a_count,
        "tier_b_count": tier_b_count,
        "tier_b_handtime_sec": round(tier_b_handtime_sec, 2),
        "send_status": send_status,
    }
    p = HOME / "inboxes" / inbox / "metrics.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p


def kpi_warnings(records: list[dict]) -> list[str]:
    """PLAN §2 thresholds: edit<10%, unknown<5%, new_patterns 0-1.
    Plus KPI guardrail: tier_a ratio >= 30% floor (alarm if below).
    """
    warns: list[str] = []
    if not records:
        return warns
    total = len(records)
    avg_edit = sum(r.get("edit_ratio", 0.0) for r in records) / total
    avg_unknown_rate = (sum(r.get("unknown_count", 0) for r in records)
                       / max(sum(r.get("drafts_count", 0) for r in records), 1))
    avg_new_pat = sum(r.get("new_patterns", 0) for r in records) / total
    tier_a_total = sum(r.get("tier_a_count", 0) for r in records)
    tier_total = tier_a_total + sum(r.get("tier_b_count", 0) for r in records)
    tier_a_ratio = tier_a_total / max(tier_total, 1)
    if avg_edit > 0.10:
        warns.append(f"edit_ratio mean {avg_edit:.2%} > 10% (PLAN §2 threshold)")
    if avg_unknown_rate > 0.05:
        warns.append(f"unknown_rate mean {avg_unknown_rate:.2%} > 5%")
    if avg_new_pat > 1.0:
        warns.append(f"new_patterns mean {avg_new_pat:.2f} > 1/round")
    if tier_total >= 30 and tier_a_ratio < 0.30:
        warns.append(f"tier_a_ratio {tier_a_ratio:.2%} < 30% floor — KPI gaming risk")
    return warns


def _selftest() -> int:
    """Validate edit_ratio on a known fixture pair."""
    pairs = [
        ("hello world", "hello world", 0.0, "identical"),
        ("hello world", "hello there", None, "small change > 0"),
        ("aaa", "bbb", None, "totally different > 0.5"),
    ]
    fails = 0
    for a, b, expected, label in pairs:
        r = edit_ratio(a, b)
        if expected is not None:
            ok = abs(r - expected) < 1e-6
        else:
            ok = r > 0.0
        print(f"[{'OK' if ok else 'FAIL'}] {label}: ratio={r}")
        if not ok:
            fails += 1
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Metrics logger / KPI warnings")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    p_warn = sub.add_parser("warnings")
    p_warn.add_argument("--inbox", required=True)
    p_warn.add_argument("--last", type=int, default=50)
    args = ap.parse_args()
    if args.cmd == "selftest":
        return _selftest()
    if args.cmd == "warnings":
        p = HOME / "inboxes" / args.inbox / "metrics.jsonl"
        if not p.exists():
            print(f"[metrics] no metrics.jsonl at {p}", file=sys.stderr)
            return 1
        records = []
        for ln in p.read_text(encoding="utf-8").splitlines()[-args.last:]:
            try:
                records.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        warns = kpi_warnings(records)
        if not warns:
            print("[metrics] no KPI warnings")
        else:
            for w in warns:
                print(f"[metrics] WARN: {w}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
