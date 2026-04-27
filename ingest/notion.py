#!/usr/bin/env python3
"""Bootstrap from Notion pages/databases via Notion MCP (per PLAN §4.3).

Stub implementation: announces target page_ids/database_ids and writes a
bootstrap_pending.md line per id. Real LLM-summarized extraction expects
mcp__claude_ai_Notion__notion-fetch to be wired by the caller.

Idempotent: same run_id resumes from last successful id index.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import begin_run, finish_run, update_run, append_pending

HOME = Path(os.environ.get("SUPPORT_REPLY_HOME",
                           Path.home() / ".claude/skills/support-reply-public"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--page-ids", nargs="*", default=[])
    ap.add_argument("--database-ids", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = [("page", pid) for pid in args.page_ids] + \
              [("database", did) for did in args.database_ids]
    if not targets:
        print("[notion] no page_ids or database_ids given — supply --page-ids ... "
              "or --database-ids ...", file=sys.stderr)
        return 0

    params = {"page_ids": args.page_ids, "database_ids": args.database_ids}
    run_id, run = begin_run(HOME, args.inbox, "notion", params)
    print(f"[notion] run_id={run_id} resume_at={run.get('cursor')!r} "
          f"dry_run={args.dry_run}", file=sys.stderr)

    start = int(run.get("cursor") or 0)
    seen = run["items_seen"]
    appended = run["items_appended"]

    for idx, (kind, ident) in enumerate(targets):
        if idx < start:
            continue
        seen += 1
        if args.dry_run:
            update_run(HOME, args.inbox, "notion", cursor=str(idx + 1),
                       items_seen=seen, items_appended=appended)
            continue
        # Stub: real implementation calls notion MCP fetch + LLM summarize.
        summary = f"({kind}) {ident}"
        append_pending(HOME, args.inbox, "notion", summary, f"{kind}:{ident}")
        appended += 1
        update_run(HOME, args.inbox, "notion", cursor=str(idx + 1),
                   items_seen=seen, items_appended=appended)

    finish_run(HOME, args.inbox, "notion")
    print(f"[notion] done — seen={seen} appended={appended}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
