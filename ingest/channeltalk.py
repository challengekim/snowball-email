#!/usr/bin/env python3
"""Bootstrap from ChannelTalk export JSON file (per PLAN §4.4).

Reads a local ChannelTalk export (JSON array of conversations), extracts each
conversation's title + first user message, and appends a candidate line to
bootstrap_pending.md for user line-by-line review.

Idempotent: same run_id resumes from last successful conversation index.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import begin_run, finish_run, update_run, append_pending

HOME = Path(os.environ.get("SNOWBALL_EMAIL_HOME",
                           Path.home() / ".claude/skills/snowball-email"))


def load_export(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[channeltalk] cannot read export {path}: {e}", file=sys.stderr)
        return []
    if isinstance(data, dict) and "conversations" in data:
        return data["conversations"]
    if isinstance(data, list):
        return data
    print(f"[channeltalk] unrecognized export shape at {path}", file=sys.stderr)
    return []


def conversation_summary(conv: dict, max_len: int = 80) -> tuple[str, str]:
    """Returns (summary, evidence_id)."""
    cid = str(conv.get("id") or conv.get("chatId") or "(noid)")
    title = (conv.get("subject") or conv.get("title") or "").strip()
    if title:
        return title[:max_len], cid
    msgs = conv.get("messages") or []
    for m in msgs[:5]:
        body = (m.get("plainText") or m.get("text") or "").strip()
        if body:
            return body[:max_len], cid
    return "(empty conversation)", cid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--export", required=False,
                    help="Path to ChannelTalk JSON export file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.export:
        print("[channeltalk] no --export <path> given — exiting (no-op)", file=sys.stderr)
        return 0

    path = Path(args.export).expanduser()
    convs = load_export(path)
    if not convs:
        return 0

    params = {"export": str(path), "total": len(convs)}
    run_id, run = begin_run(HOME, args.inbox, "channeltalk", params)
    print(f"[channeltalk] run_id={run_id} resume_at={run.get('cursor')!r} "
          f"total={len(convs)} dry_run={args.dry_run}", file=sys.stderr)

    start = int(run.get("cursor") or 0)
    seen = run["items_seen"]
    appended = run["items_appended"]

    for idx, conv in enumerate(convs):
        if idx < start:
            continue
        seen += 1
        if args.dry_run:
            update_run(HOME, args.inbox, "channeltalk", cursor=str(idx + 1),
                       items_seen=seen, items_appended=appended)
            continue
        summary, cid = conversation_summary(conv)
        append_pending(HOME, args.inbox, "channeltalk", summary, cid)
        appended += 1
        update_run(HOME, args.inbox, "channeltalk", cursor=str(idx + 1),
                   items_seen=seen, items_appended=appended)

    finish_run(HOME, args.inbox, "channeltalk")
    print(f"[channeltalk] done — seen={seen} appended={appended}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
