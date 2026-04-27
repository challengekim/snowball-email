---
name: "feat: drafts read principles.md + matching pattern (v0.2 milestone)"
about: Make the drafter actually consult the reference store, not just classification
title: "feat(drafts): inject principles.md + matching pattern into build_draft()"
labels: ["enhancement", "good first issue", "v0.2"]
assignees: []
---

## Why this exists

`README.md`'s "Status & Roadmap" section and `SKILL.md` §1.5 explicitly say
that **drafting compounding is not wired in v0.1.x**: round 1 and round 100
produce identical bodies because the drafter never reads the reference store.
This issue tracks closing that gap.

## Where the gap is in code

`assets/run_round.py` — function `build_draft()` (currently around line 204):

```python
body_text = (
    f"{_addressee(parsed.get('from', ''))} 님, 안녕하세요.\n\n"
    f"{_template_body_text(classification)}\n\n"
    f"{signoff}{cfg.get('send', {}).get('from_name', '')} 드림\n"
)
```

The body is a hardcoded Korean template keyed only off `classification`. The
reference store **is** loaded earlier in the same file (`compiled_md =
reference_store.load_compiled(inbox_dir)` near line 410), but it's only used
by the classifier — never passed into `build_draft()`.

The five persona seeds at `templates/personas/<persona>.md` are copied into
`inboxes/<inbox>/reference/principles.md` at `init` time, so the data is
already on disk in a known location; the drafter just doesn't open it.

## Acceptance criteria

A reviewer should be able to verify all of these without asking questions.

1. `build_draft()` receives both:
   - the contents of `inboxes/<inbox>/reference/principles.md` (persona tone)
   - the matching pattern body from
     `inboxes/<inbox>/reference/patterns/<class>.md` when one exists
2. When `classify.backend = llm_anthropic` is configured and an API key is
   present, those two pieces are included in the LLM prompt that produces
   the body. When the classifier falls back to substring or no LLM key is
   configured, the function may continue to return a template-based body
   but **must** prepend a one-line note in the body source comment that
   reference injection was skipped (so it's grep-able from
   `bin/snowball-email view`).
3. A new round on the same `inbox` after editing
   `reference/principles.md` produces a **different** body for the same
   inbound email (proves the drafter actually reads it). Demonstrate with
   a snapshot test under `tests/`.
4. `metrics.jsonl` adds a `draft_used_reference: true|false` field per
   draft so the existing `bin/snowball-email metrics` view can confirm
   the drafter is consulting the store.
5. `README.md` "Status & Roadmap" row "Reply body uses reference / persona
   principles" flips from ❌ to ✅ and `CHANGELOG.md` v0.2 entry is updated.
6. `SKILL.md` §1.5 "Not wired in v0.1.x" loses the corresponding bullet.

## Out of scope (do not include in the same PR)

- Changing approval gate behavior.
- Changing `edit_ratio` capture (separate issue).
- Adding new send backends.
- Bootstrap apply command (separate issue).

## Hints

- Keep `build_draft()` deterministic when no LLM is configured — never
  silently call out to the network. The substring path should still
  produce a usable, if generic, draft.
- Persona files are minimal Markdown (`tone` / `avoid` / `example`
  sections). Just inline them verbatim into the prompt rather than
  parsing.
- Capping pattern body inclusion to ~1.5 KB keeps prompts cheap on
  classes that have accumulated many examples.
