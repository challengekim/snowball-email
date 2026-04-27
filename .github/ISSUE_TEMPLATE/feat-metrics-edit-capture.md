---
name: "feat: capture user edits so edit_ratio is real (v0.2 milestone)"
about: Make the metrics column 'edit%' actually measure something
title: "feat(metrics): capture approved-vs-draft diff so edit_ratio stops being 0.00"
labels: ["enhancement", "good first issue", "v0.2"]
assignees: []
---

## Why this exists

`README.md` "Status & Roadmap" and `SKILL.md` §1.5 disclose that the
`edit%` column emitted by `bin/snowball-email metrics` is structurally
always `0.00` in v0.1.x. This issue closes that.

## Where the gap is in code

`assets/run_round.py`, around line 468, when calling `append_round`:

```python
append_round(
    inbox_dir,
    round_id=round_id,
    drafts=[{"approved": d["body_text"], "draft": d["body_text"]} for d in approved],
    ...
)
```

`approved["body_text"]` is fed into both fields. `metrics/logger.py`
implements `edit_ratio()` correctly with `difflib.SequenceMatcher`, but
because it always sees `approved == draft`, it always returns `0.0`.

## Acceptance criteria

1. The approval gate path stores **two strings** per draft: the body
   the drafter generated (`draft`) and the body the user actually
   approved/edited (`approved`). They must remain distinct strings even
   when the user makes no edits — at minimum, distinct objects with
   the same value, never aliased.
2. When the user edits the draft before approving, the post-edit body
   replaces `approved`, leaving `draft` unchanged.
3. `metrics/logger.py:edit_ratio()` returns a non-zero value when an
   edit occurred. Add a test under `tests/` exercising:
   - identical strings → `0.0`
   - one-word substitution → small positive value
   - significant rewrite → value > 0.10 (matches the existing KPI
     threshold in `bin/snowball-email metrics`)
4. `bin/snowball-email metrics` `edit%` column reflects the new value
   without any further code changes (the renderer already uses the
   logger output).
5. README §4.5 "Columns that are placeholders until v0.2" loses the
   `edit%` bullet. SKILL.md §1.5 loses the `edit_ratio` bullet.
6. CHANGELOG.md v0.2 entry checks off "Real `edit_ratio` capture".

## Out of scope (do not include in the same PR)

- Changing how the drafter produces `draft` (separate issue).
- Adding new metrics columns. Just make the existing one truthful.
- Persisting raw drafts to disk for audit (a thoughtful follow-up but
  not required for this issue).

## Hints

- The minimal change is in `assets/run_round.py`: keep
  `approved["draft_body_text"]` (set once when the draft is generated)
  and `approved["body_text"]` (mutated by the approval gate when the
  user edits). Then pass them as the two distinct fields.
- Watch the approval prompt path: any place the user replies "edit:
  ..." must update only the approved body, never the draft body.
- The file `metrics/logger.py:edit_ratio` already does the right
  thing — do **not** rewrite it. The fix is upstream.
