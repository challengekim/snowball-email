# Changelog

All notable changes to **snowball-email** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The point of this file is to keep `README.md` honest. Everything in **What works**
is exercised by the code today; everything in **Known gaps** is real but not yet
wired and is tracked as v0.2 work in [`PLAN.md`](PLAN.md).

---

## [Unreleased] — v0.2 milestone (planned)

> Theme: turn the four "decorative" pieces in v0.1.x into real ones, in priority order.

### Planned
- **Reference-driven draft body.** `assets/run_round.py:204` `build_draft()` will
  consult `reference/principles.md` (persona tone) and the matching pattern from
  `reference/patterns/<class>.md` to compose the body, instead of returning a
  hardcoded Korean template. This is the change that makes "compound brain on
  drafts" actually true. ([good first issue](.github/ISSUE_TEMPLATE/feat-drafts-reference-injection.md))
- **Real `edit_ratio` capture.** Approval gate will record the user-edited body
  separately from the generated body so `metrics/logger.py:edit_ratio()` finally
  has something non-trivial to diff. The `edit%` column in `bin/snowball-email
  metrics` becomes a meaningful signal. ([good first issue](.github/ISSUE_TEMPLATE/feat-metrics-edit-capture.md))
- **`bootstrap apply` CLI.** Today the four ingest sources
  (`ingest/{gmail,web,notion,channeltalk}.py`) only append candidates to
  `bootstrap_pending.md`; promoting reviewed lines into
  `inboxes/<inbox>/reference/patterns/` is a manual copy. v0.2 adds
  `bin/snowball-email bootstrap apply --inbox <name>` to close the loop.
  ([good first issue](.github/ISSUE_TEMPLATE/feat-bootstrap-apply.md))
- **Ingest body extraction.** `ingest/gmail.py:90` and `ingest/notion.py:56`
  carry `Stub:` comments — currently only subject/title is read. v0.2 parses
  message bodies / page contents so summaries are actually useful seeds.

### Not planned for v0.2
- Mailgun / SES / SMTP send backends. Stays as `gws_drafts` / `gws_send` /
  `sendgrid` (per `config/schema.yaml`).
- Auto-approval. The skill's verbatim non-negotiable rule remains: every send
  is gated on explicit user approval.

---

## [0.1.1] — 2026-04-27

### Changed
- **README and SKILL.md aligned with the actual code.** Removed the
  "round 20 sounds like our team" / "100-round expert" framing from the hero
  and §1 because the drafter is template-only in v0.1.x. The compound-learning
  language is preserved only where it's accurate (the classification pattern
  store), with explicit pointers to v0.2 for drafting compounding.
  See: [README hero](README.md), [SKILL §1.5 Status & Roadmap](SKILL.md).
- `metrics` doc table now flags the columns that are placeholders until v0.2:
  `edit%` is structurally always `0.00` because draft and approved bodies are
  recorded as the same string in `assets/run_round.py:468`.
- Send backends doc trimmed to what `config/schema.yaml` actually accepts
  (`gws_drafts` / `gws_send` / `sendgrid`); dropped Mailgun / SMTP rows that
  were never wired.
- Safety section corrected: BCC is **off** by default (empty string), not on.
- Learning section corrected to the implemented surface
  (`classify.backend = substring | llm_anthropic`, `learn.auto_case`) instead
  of the not-yet-wired `learner.model` / `feedback_prompt` keys.
- SKILL.md frontmatter description compressed from a 5-sentence pitch to a
  one-line honest summary.

### Documented as a gap (no behavior change)
- `assets/run_round.py:204` `build_draft()` does not inject `principles.md` or
  matching patterns into the body — flagged in README and SKILL.md, scheduled
  for v0.2.
- `assets/run_round.py:468` records `draft == approved` so `edit_ratio` is
  structurally `0.00` — flagged in README §4.5 and SKILL.md §1.5.
- `bootstrap apply` command does not exist; manual copy is required after
  reviewing `bootstrap_pending.md`.

---

## [0.1.0] — initial public extraction

### What works
- Gmail thread fetch via the `gws` CLI on a single label.
- Two-tier (A/B) approval gate with conservative bias; first 30 rounds are
  forced into Tier-A calibration.
- Substring classifier (default, fully local) with optional `llm_anthropic`
  backend that falls back to substring on any error
  (missing key / network / parse).
- Per-inbox local **reference store** under `inboxes/<inbox>/reference/`
  (`principles.md`, `patterns/`, `cases/`, `_compiled.md`,
  `_changelog.md`, `_backups/`). Pattern accumulation over rounds genuinely
  raises classification accuracy (UNKNOWN rate drops as the store grows).
- Five persona seeds (`cs` / `bd` / `recruiting` / `partnerships` / `sales`)
  copied into `reference/principles.md` and pattern templates at `init`. Note:
  these influence classification, not yet draft bodies.
- `gws_drafts` (default — never auto-sends), `gws_send`, and `sendgrid` send
  backends.
- `metrics.jsonl` per-round log with `unk` / `new` / `A` / `B` / `send_status`
  fields that are real, plus `edit_ratio` field that is currently always `0.00`
  (see Known gaps).
- Multi-inbox isolation; an `init` wizard scaffolds
  `inboxes/<name>/{config.yaml,reference/,metrics.jsonl,bootstrap_pending.md}`.
- Four bootstrap ingest sources (`gmail` / `web` / `notion` / `channeltalk`)
  that append candidates to `bootstrap_pending.md` for line-by-line review.

### Known gaps (carried into v0.2)
- Drafting is template-only; reference / persona principles are not in the
  draft prompt.
- `edit_ratio` is structurally always `0.00`.
- No `bootstrap apply` command — manual copy from `bootstrap_pending.md` is
  required.
- `ingest/gmail.py` and `ingest/notion.py` parse subject/title only; bodies
  are stubbed.

---

[Unreleased]: https://github.com/challengekim/snowball-email/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/challengekim/snowball-email/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/challengekim/snowball-email/releases/tag/v0.1.0
