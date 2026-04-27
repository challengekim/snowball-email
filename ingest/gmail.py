#!/usr/bin/env python3
"""Bootstrap from Gmail past conversations via gws cli (per PLAN §4.1).

Fetches threads matching a query (e.g., "label:support older_than:90d"),
extracts subject + first message body + final reply body, summarizes each as
a candidate pattern, and appends a one-line entry to bootstrap_pending.md
for user line-by-line review (no auto-approval per Principle 1).

Idempotent: re-running with the same run_id (incomplete run) resumes from
the last successful page cursor recorded in bootstrap_state.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (begin_run, finish_run, update_run,
                     append_pending, inbox_dir)

HOME = Path(os.environ.get("SNOWBALL_EMAIL_HOME",
                           Path.home() / ".claude/skills/snowball-email"))


def _have_gws() -> bool:
    return shutil.which("gws") is not None


def _gws(*args: str) -> dict | None:
    try:
        out = subprocess.check_output(["gws", *args], stderr=subprocess.PIPE, timeout=60)
        return json.loads(out)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"[gmail] gws call failed: {e}", file=sys.stderr)
        return None


def list_threads(query: str, page_token: str | None = None, max_results: int = 50) -> dict | None:
    params = {"userId": "me", "q": query, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    return _gws("gmail", "users", "threads", "list", "--params", json.dumps(params))


def get_thread(thread_id: str) -> dict | None:
    params = {"userId": "me", "id": thread_id, "format": "full"}
    return _gws("gmail", "users", "threads", "get", "--params", json.dumps(params))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--query", default=None,
                    help="Gmail search query; default reads from inbox config")
    ap.add_argument("--max-threads", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not _have_gws():
        print("[gmail] gws CLI not found in PATH — install Google Workspace CLI first",
              file=sys.stderr)
        return 2

    query = args.query or "label:support older_than:30d"
    params = {"query": query, "max_threads": args.max_threads}
    run_id, run = begin_run(HOME, args.inbox, "gmail", params)
    print(f"[gmail] run_id={run_id} resume_cursor={run.get('cursor')!r} "
          f"items_seen={run['items_seen']} dry_run={args.dry_run}", file=sys.stderr)

    cursor = run.get("cursor")
    seen = run["items_seen"]
    appended = run["items_appended"]

    while seen < args.max_threads:
        listing = list_threads(query, page_token=cursor, max_results=min(50, args.max_threads - seen))
        if not listing or not listing.get("threads"):
            break
        for th in listing["threads"]:
            seen += 1
            if args.dry_run:
                continue
            full = get_thread(th["id"])
            if not full:
                continue
            # Stub: real implementation parses headers + bodies + summarizes via LLM.
            subject = "(unparsed)"
            for msg in full.get("messages", [])[:1]:
                for h in msg.get("payload", {}).get("headers", []):
                    if h.get("name") == "Subject":
                        subject = h.get("value", "")[:80]
                        break
            append_pending(HOME, args.inbox, "gmail", subject, th["id"])
            appended += 1
        cursor = listing.get("nextPageToken")
        update_run(HOME, args.inbox, "gmail", cursor=cursor, items_seen=seen,
                   items_appended=appended)
        if not cursor:
            break

    finish_run(HOME, args.inbox, "gmail")
    print(f"[gmail] done — seen={seen} appended={appended}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
