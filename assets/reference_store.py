#!/usr/bin/env python3
"""Compound-brain reference store (PLAN.md §5).

Per-inbox layout:
    inboxes/<inbox>/reference/
        patterns/<pattern_id>.md           # one classification pattern per file
        cases/<category>.jsonl             # one historical case per line
        links.md                           # canonical links (one per line: name|url)
        principles.md                      # tone-and-manner principles (free-form md)
        _compiled.md                       # auto-generated flat view (concat of all)
        _backups/_compiled.YYYYMMDDTHHMMSS.md   # pre-overwrite backup

Public API:
    ensure_layout(inbox_dir)
    load_compiled(inbox_dir) -> str
    list_pattern_ids(inbox_dir) -> list[str]
    append_pattern(inbox_dir, pattern_id, body_md)         # idempotent on id
    append_case(inbox_dir, category, case_dict)            # always appends jsonl
    append_link(inbox_dir, name, url)                      # idempotent on (name,url)
    rebuild_compiled(inbox_dir) -> Path                    # regenerates _compiled.md

Rules:
    - duplicate pattern_id -> skipped (returns False); never overwritten silently
    - rebuild backs up the prior _compiled.md to _backups/ before overwrite
    - all writes are atomic (write-tmp + os.replace)
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

_PATTERN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def ensure_layout(inbox_dir: Path) -> None:
    ref = inbox_dir / "reference"
    (ref / "patterns").mkdir(parents=True, exist_ok=True)
    (ref / "cases").mkdir(parents=True, exist_ok=True)
    (ref / "_backups").mkdir(parents=True, exist_ok=True)
    for stub_name, stub_body in (
        ("links.md", "# Canonical links\n\n# format: <name>|<url>\n"),
        ("principles.md", "# Tone & manner principles\n\n- 받은 메일 맥락에 맞춰 정중·구체·짧게\n- 추측 금지, 모르면 확인 후 회신\n- 불필요한 마케팅 문구 지양\n"),
    ):
        p = ref / stub_name
        if not p.exists():
            _atomic_write(p, stub_body)


def list_pattern_ids(inbox_dir: Path) -> list[str]:
    pdir = inbox_dir / "reference" / "patterns"
    if not pdir.exists():
        return []
    return sorted(p.stem for p in pdir.glob("*.md"))


def append_pattern(inbox_dir: Path, pattern_id: str, body_md: str) -> bool:
    """Returns True if newly written, False if duplicate id (no overwrite)."""
    if not _PATTERN_ID_RE.match(pattern_id):
        raise ValueError(f"invalid pattern_id (lowercase a-z0-9_-, max 64): {pattern_id!r}")
    ensure_layout(inbox_dir)
    p = inbox_dir / "reference" / "patterns" / f"{pattern_id}.md"
    if p.exists():
        return False
    header = f"# Pattern: {pattern_id}\n\n_added: {_now_iso()}_\n\n"
    _atomic_write(p, header + body_md.rstrip() + "\n")
    return True


def append_case(inbox_dir: Path, category: str, case: dict) -> Path:
    """Always appends; jsonl. Use sparingly — Pin-2 churn budget = 1/round avg."""
    ensure_layout(inbox_dir)
    safe_cat = re.sub(r"[^a-z0-9_-]", "_", category.lower())[:64] or "uncategorized"
    p = inbox_dir / "reference" / "cases" / f"{safe_cat}.jsonl"
    case_with_ts = {"_ts": _now_iso(), **case}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(case_with_ts, ensure_ascii=False) + "\n")
    return p


def append_link(inbox_dir: Path, name: str, url: str) -> bool:
    """Returns True if newly added, False if duplicate (name|url) line."""
    ensure_layout(inbox_dir)
    p = inbox_dir / "reference" / "links.md"
    line = f"{name}|{url}".strip()
    existing = p.read_text(encoding="utf-8") if p.exists() else ""
    if line in {ln.strip() for ln in existing.splitlines()}:
        return False
    new = existing.rstrip() + "\n" + line + "\n"
    _atomic_write(p, new)
    return True


def rebuild_compiled(inbox_dir: Path) -> Path:
    """Concatenate all reference files into _compiled.md (flat view)."""
    ensure_layout(inbox_dir)
    ref = inbox_dir / "reference"
    out = ref / "_compiled.md"

    if out.exists():
        bak = ref / "_backups" / f"_compiled.{_now_compact()}.md"
        bak.write_bytes(out.read_bytes())

    sections: list[str] = [
        f"# Compiled reference — {inbox_dir.name}",
        f"_generated: {_now_iso()}_",
        "",
    ]
    for fname in ("principles.md", "links.md"):
        p = ref / fname
        if p.exists():
            sections.append(f"## {fname.removesuffix('.md').title()}")
            sections.append(p.read_text(encoding="utf-8").rstrip())
            sections.append("")
    sections.append("## Patterns")
    for pid in list_pattern_ids(inbox_dir):
        body = (ref / "patterns" / f"{pid}.md").read_text(encoding="utf-8").rstrip()
        sections.append(body)
        sections.append("")
    cdir = ref / "cases"
    if any(cdir.glob("*.jsonl")):
        sections.append("## Cases (recent 10 per category)")
        for cat_path in sorted(cdir.glob("*.jsonl")):
            sections.append(f"### {cat_path.stem}")
            lines = cat_path.read_text(encoding="utf-8").splitlines()
            for ln in lines[-10:]:
                try:
                    obj = json.loads(ln)
                    sections.append(f"- {obj}")
                except json.JSONDecodeError:
                    continue
            sections.append("")
    _atomic_write(out, "\n".join(sections))
    return out


def load_compiled(inbox_dir: Path) -> str:
    p = inbox_dir / "reference" / "_compiled.md"
    if not p.exists():
        rebuild_compiled(inbox_dir)
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _now_compact() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------
def _selftest() -> int:
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        inbox = Path(td) / "selftest"
        inbox.mkdir()
        ensure_layout(inbox)
        fails = 0

        ok = append_pattern(inbox, "refund_request",
                            "## Trigger\n환불 키워드\n\n## Reply tone\n정중하게 사유 확인 요청.")
        check("first append_pattern succeeds", ok is True, locals()) or (fails := fails + 1)

        ok = append_pattern(inbox, "refund_request", "다른 본문 — 무시되어야 함")
        check("duplicate pattern_id is skipped", ok is False, locals()) or (fails := fails + 1)

        try:
            append_pattern(inbox, "BAD/ID", "x")
            check("invalid id raises", False, locals()) or (fails := fails + 1)
        except ValueError:
            check("invalid id raises", True, locals())

        case_path = append_case(inbox, "refund_request", {"thread": "abc", "outcome": "approved"})
        check("case appended", case_path.exists(), locals()) or (fails := fails + 1)

        ok = append_link(inbox, "FAQ", "https://example.com/faq")
        check("first link added", ok is True, locals()) or (fails := fails + 1)
        ok = append_link(inbox, "FAQ", "https://example.com/faq")
        check("duplicate link skipped", ok is False, locals()) or (fails := fails + 1)

        out = rebuild_compiled(inbox)
        body = out.read_text(encoding="utf-8")
        check("_compiled.md contains pattern", "Pattern: refund_request" in body, locals()) or (fails := fails + 1)
        check("_compiled.md contains link line", "FAQ|https://example.com/faq" in body, locals()) or (fails := fails + 1)
        check("_compiled.md contains case", "approved" in body, locals()) or (fails := fails + 1)

        out2 = rebuild_compiled(inbox)
        backups = list((inbox / "reference" / "_backups").glob("_compiled.*.md"))
        check("rebuild backs up prior _compiled.md", len(backups) >= 1, locals()) or (fails := fails + 1)

        return 0 if fails == 0 else 1


def check(label: str, ok: bool, _locals=None) -> bool:
    print(f"[{'OK' if ok else 'FAIL'}] {label}")
    return ok


if __name__ == "__main__":
    sys.exit(_selftest())
