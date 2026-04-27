"""Shared helpers for ingest/*.py — idempotent run state per PLAN §4.0 / Architect NEW-5."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def utc_run_id() -> str:
    """ISO 8601 UTC second precision per CRIT-5: YYYYMMDDTHHMMSSZ."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def inbox_dir(home: Path, inbox: str) -> Path:
    return home / "inboxes" / inbox


def state_path(home: Path, inbox: str) -> Path:
    return inbox_dir(home, inbox) / "bootstrap_state.json"


def pending_path(home: Path, inbox: str) -> Path:
    return inbox_dir(home, inbox) / "bootstrap_pending.md"


def read_state(home: Path, inbox: str) -> dict[str, Any]:
    p = state_path(home, inbox)
    if not p.exists():
        return {"sources": {}}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"sources": {}}


def write_state(home: Path, inbox: str, state: dict[str, Any]) -> None:
    p = state_path(home, inbox)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.replace(p)


def append_pending(home: Path, inbox: str, source: str, summary: str, evidence: str) -> None:
    """Append one candidate to bootstrap_pending.md for line-by-line user review."""
    p = pending_path(home, inbox)
    p.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(evidence.encode("utf-8")).hexdigest()[:8]
    line = f"- [ ] [{source}/{digest}] {summary}\n"
    with p.open("a") as f:
        f.write(line)


def begin_run(home: Path, inbox: str, source: str, params: dict[str, Any]) -> tuple[str, dict]:
    """Start (or resume) a source run. Returns (run_id, run_state)."""
    state = read_state(home, inbox)
    src_state = state.setdefault("sources", {}).setdefault(source, {})
    # Resume if last run is incomplete; else start fresh.
    last = src_state.get("last_run")
    if last and not last.get("complete"):
        run_id = last["run_id"]
        run_state = last
    else:
        run_id = utc_run_id()
        run_state = {"run_id": run_id, "params": params, "cursor": None,
                     "items_seen": 0, "items_appended": 0, "complete": False}
        src_state["last_run"] = run_state
    write_state(home, inbox, state)
    return run_id, run_state


def update_run(home: Path, inbox: str, source: str, **fields) -> None:
    state = read_state(home, inbox)
    state.setdefault("sources", {}).setdefault(source, {}).setdefault("last_run", {}).update(fields)
    write_state(home, inbox, state)


def finish_run(home: Path, inbox: str, source: str) -> None:
    update_run(home, inbox, source, complete=True, finished_at=utc_run_id())
