---
name: "feat: bootstrap apply command (v0.2 milestone)"
about: Close the bootstrap loop — promote reviewed pending lines into the pattern store
title: "feat(bootstrap): add `bootstrap apply --inbox <name>` to convert pending → patterns"
labels: ["enhancement", "good first issue", "v0.2"]
assignees: []
---

## Why this exists

`README.md` "Status & Roadmap" and `SKILL.md` §1.5 disclose that the four
ingest sources (`gmail` / `web` / `notion` / `channeltalk`) only **append
candidates** to `inboxes/<inbox>/bootstrap_pending.md`. Today the user has
to manually copy approved lines into
`inboxes/<inbox>/reference/patterns/<class>.md`. This issue closes the
loop with a CLI command.

## Where the gap is in code

- `ingest/_common.py` exposes `append_pending(home, inbox, source,
  subject, ext_id)` — every ingest script writes through this.
- `bin/snowball-email` already has subcommands `init`, `config`,
  `bootstrap`, `view`, `grep`, `diff`, `metrics`, `run`. Grep for
  `bootstrap apply` / `apply_pending` returns zero matches as of
  v0.1.1.
- `assets/reference_store.py` exports `append_pattern(...)` with
  `_PATTERN_ID_RE` validation. That's the function that should
  receive the approved lines.

## Acceptance criteria

1. `bin/snowball-email bootstrap apply --inbox <name>` exists and is
   wired through the existing dispatcher.
2. Behavior:
   - Reads `inboxes/<inbox>/bootstrap_pending.md`.
   - Lines marked as approved (a clearly documented checkbox / prefix
     convention — propose one and document it in
     `docs/MANUAL.md`) are converted into pattern files via
     `reference_store.append_pattern(...)`.
   - Lines without the approved marker are left alone.
   - The command is **idempotent**: running it twice on the same file
     does not duplicate patterns. Use the existing `_PATTERN_ID_RE`
     duplicate-detection path inside `append_pattern`.
3. After successful apply, the converted lines are moved (not deleted)
   into `inboxes/<inbox>/bootstrap_pending.applied.md` with the apply
   timestamp. This preserves audit trail without re-processing them.
4. `--dry-run` flag prints the planned conversion table
   (subject → class → pattern id) without writing anything.
5. `bootstrap_state.json` records the apply run id (mirrors the
   pattern used by ingest runs).
6. README §0.5 Bootstrap section gains one line:
   `bin/snowball-email bootstrap apply --inbox <name>` after the
   review step. SKILL.md §1.5 loses the corresponding bullet.
7. CHANGELOG.md v0.2 entry checks off "`bootstrap apply` CLI".

## Out of scope (do not include in the same PR)

- Auto-approval of pending lines. Approval stays manual — this issue
  only adds the **conversion** step after the user has reviewed.
- Building a TUI for review. Plain Markdown checkboxes are fine.
- Changing how ingest sources extract data
  (`ingest/gmail.py:90` `Stub:` is its own follow-up).

## Hints

- Suggested approval marker: line begins with `- [x] ` (GitHub-style
  task list). `- [ ] ` lines are skipped. Document this in
  `docs/MANUAL.md` §Bootstrap.
- The class for each line is already encoded in
  `bootstrap_pending.md` because every ingest source writes
  `source/<source>/<subject>` — propose extending `append_pending` to
  also write a `class_hint:` field that `apply` can consume. If you'd
  rather keep `append_pending` stable, parse the class out of the
  subject heuristically and let the user override it inline.
- Re-use `assets/reference_store.append_pattern` rather than
  duplicating the file-write logic. That keeps `_PATTERN_ID_RE` and
  backup behavior consistent with the live append path used after
  approved sends.
