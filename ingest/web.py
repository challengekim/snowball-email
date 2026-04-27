#!/usr/bin/env python3
"""Bootstrap from web pages / PDFs (per PLAN §4.2).

Each URL is fetched (HTTP) or pdftotext'd if local PDF; one summary line per
page is appended to bootstrap_pending.md for user line-by-line review.

Idempotent: same run_id resumes from last successful URL index.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import begin_run, finish_run, update_run, append_pending

HOME = Path(os.environ.get("SUPPORT_REPLY_HOME",
                           Path.home() / ".claude/skills/support-reply-public"))


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def fetch_url(url: str, timeout: int = 30) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "support-reply-public/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[web] fetch failed {url}: {e}", file=sys.stderr)
        return None


def extract_pdf(path: str) -> str | None:
    if not _have("pdftotext"):
        print("[web] pdftotext not installed — skipping PDF", file=sys.stderr)
        return None
    try:
        out = subprocess.check_output(["pdftotext", "-layout", path, "-"], timeout=120)
        return out.decode("utf-8", errors="replace")
    except subprocess.SubprocessError as e:
        print(f"[web] pdftotext failed {path}: {e}", file=sys.stderr)
        return None


def first_line_summary(text: str, max_len: int = 80) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= 10:
            return s[:max_len]
    return "(empty)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--urls", nargs="*", default=[],
                    help="URLs or local PDF paths to ingest")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.urls:
        print("[web] no URLs given — supply --urls <url1> <url2> ... or PDF paths",
              file=sys.stderr)
        return 0

    params = {"urls": args.urls, "max_pages": args.max_pages}
    run_id, run = begin_run(HOME, args.inbox, "web", params)
    print(f"[web] run_id={run_id} resume_at={run.get('cursor')!r} dry_run={args.dry_run}",
          file=sys.stderr)

    start = int(run.get("cursor") or 0)
    seen = run["items_seen"]
    appended = run["items_appended"]

    for idx, target in enumerate(args.urls[:args.max_pages]):
        if idx < start:
            continue
        seen += 1
        if args.dry_run:
            update_run(HOME, args.inbox, "web", cursor=str(idx + 1),
                       items_seen=seen, items_appended=appended)
            continue
        if target.lower().endswith(".pdf") and Path(target).exists():
            text = extract_pdf(target)
        else:
            text = fetch_url(target)
        if not text:
            update_run(HOME, args.inbox, "web", cursor=str(idx + 1),
                       items_seen=seen, items_appended=appended)
            continue
        summary = first_line_summary(text)
        append_pending(HOME, args.inbox, "web", summary, target)
        appended += 1
        update_run(HOME, args.inbox, "web", cursor=str(idx + 1),
                   items_seen=seen, items_appended=appended)

    finish_run(HOME, args.inbox, "web")
    print(f"[web] done — seen={seen} appended={appended}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
