# snowball-email

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-skill-orange)](https://docs.anthropic.com/claude/docs/claude-code)
[![Gmail via gws CLI](https://img.shields.io/badge/Gmail-gws%20CLI-red)](https://github.com/GAM-team/GAM)

> **Explicit-approval Gmail reply copilot with local memory.** gws CLI로 Gmail을 읽고, inbox별 reference 디렉토리에 분류 패턴·사례·원칙을 누적합니다. 모든 발송은 사용자 명시 승인 후에만 진행 (verbatim 비협상). 추가 SaaS 비용 0.
>
> **Explicit-approval Gmail reply copilot with local memory.** Reads Gmail through the gws CLI and accumulates classification patterns, cases, and tone notes in a per-inbox reference store. Every send happens only after explicit user approval (verbatim non-negotiable). Zero extra SaaS spend.
>
> **현재 v0.1.x에서 실제로 작동 / What works in v0.1.x today** — Gmail fetch via gws · substring + LLM 분류기 · 패턴 자동 추가로 분류 정확도 round-over-round 향상 · 2-tier 승인 게이트 · `gws_drafts` 백엔드로 안전 초안 생성 · `metrics.jsonl` 기록.
>
> **v0.2 로드맵 (PLAN.md 참조) — Roadmap (designed, not yet wired)** — reference-driven draft body (현재는 템플릿 고정) · 사용자 edit 캡처로 실 `edit_ratio` 측정 (현재는 항상 0) · `bootstrap apply` 명령으로 pending → 패턴 자동 변환 (현재는 수동 복사) · gmail/notion ingest 본문 추출 (현재는 subject만).

| Persona | Use case | Tone seed (now in `principles.md`; drafter integration in v0.2) |
|---|---|---|
| `cs` | 환불 / 문의 / 버그 리포트 회신 | 정중·구체·짧게 |
| `bd` | cold outreach 응답, 파트너 인트로 | 명확한 가치 제안, 다음 step 1개 |
| `recruiting` | 후보자 follow-up, 일정 조율 | 사람-우선, 솔직함 |
| `partnerships` | 협업 검토, MOU 핸드오프 | 사실 기반, 책임 명시 |
| `sales` | 견적 / 도입 문의 응답 | 의사결정 가속, 가격 투명성 |

`init` 시 1개를 고르거나 `custom`으로 직접 정의 — 5개 모두 [`templates/personas/`](templates/personas/)에 시드 파일이 들어있고 `principles.md`로 복사됩니다. **드래프터가 이 톤을 실제 프롬프트에 주입하는 것은 v0.2 작업.**

**전체 매뉴얼은 [`docs/MANUAL.md`](docs/MANUAL.md) (한국어 + English 동시 수록).**
**Full bilingual manual: [`docs/MANUAL.md`](docs/MANUAL.md).**

---

## Status & Roadmap (v0.1.x → v0.2)

명확하게 작동하는 것과 아직 안 된 것을 분리합니다. CHANGELOG.md와 [`PLAN.md`](PLAN.md)에 더 자세한 항목이 있습니다.

| Capability | v0.1.x (now) | v0.2 (planned) | Code pointer |
|---|---|---|---|
| Gmail fetch via gws | ✅ works | — | `assets/run_round.py` (fetch step) |
| Substring + LLM 분류기 | ✅ works | — | `classifier/` |
| Pattern store accumulation → 분류 정확도 round-over-round 향상 | ✅ works (genuine compound on classification) | — | `assets/reference_store.py` |
| 2-tier 승인 게이트 (Tier-A/B) | ✅ works | — | `assets/run_round.py` (approval gate) |
| `gws_drafts` 백엔드 (Gmail draft 생성) | ✅ works | — | `assets/sender.py` |
| `metrics.jsonl` 기록 | ✅ writes file | — | `metrics/logger.py` |
| **Reply body uses reference / persona principles** | ❌ **template-only** — `build_draft()`는 한국어 고정 템플릿. principles.md / 매칭 패턴이 본문 생성에 주입되지 않음. | ✅ wire reference + persona into draft prompt | `assets/run_round.py:204` (`build_draft`) |
| **`edit_ratio` (사용자 수정량)** | ❌ **항상 0.00** — draft와 approved가 동일 문자열로 기록됨 (capture path 없음) | ✅ approval gate에서 user edit 캡처 | `assets/run_round.py:468` |
| **`bootstrap apply` 명령** | ❌ **수동 복사** — ingest는 `bootstrap_pending.md`에 후보만 누적. 승인 후 patterns/로 옮기는 CLI 명령 없음. | ✅ `bootstrap apply --inbox <name>` | `ingest/` (gmail/web/notion/channeltalk), `bin/snowball-email` |
| **Persona tone in drafter prompt** | ⚠️ **장식적 (decorative)** — `principles.md`에는 시드되지만 드래프터가 읽지 않음 | ✅ same as drafts row above | `templates/personas/` → `reference/principles.md` |
| Gmail/Notion ingest body extraction | ⚠️ **subject only** — `ingest/gmail.py:90`, `ingest/notion.py:56`에 `Stub:` 주석. 본문 파싱 미구현. | ✅ full body parsing | `ingest/gmail.py`, `ingest/notion.py` |

> **요약**: classification에서 발생하는 compound는 진짜로 동작합니다 (UNKNOWN 비율이 round-over-round 감소). **Drafting 단계의 compound — "100번 쓰면 우리 팀 톤" — 은 v0.2 작업이며 v0.1.x에선 템플릿 고정**입니다. metrics에 찍히는 의미 있는 신호는 `unk` / `new` / `A` / `B` 4개이고 `edit%`은 v0.2까지 placeholder입니다.

> **Summary (EN)**: classification compounding is real — UNKNOWN rate drops as the pattern store grows. **Drafting compounding ("sounds like our team after 100 rounds") is v0.2 work and not wired in v0.1.x — drafts are template-fixed.** Useful metric signals today: `unk`, `new`, `A`, `B`. `edit%` stays a placeholder until v0.2.

---

## 한국어

### 핵심 가치
- gws cli (Google Workspace CLI)만 쓰므로 추가 SaaS 비용 0
- 모든 발송은 사용자 명시 승인 후 진행 — verbatim 비협상
- 분류기가 reference에서 패턴을 누적하며 round 단위로 정확도가 올라감 (UNKNOWN 비율 감소). **드래프트 본문은 v0.1.x에서 템플릿 고정** — reference-driven drafting은 v0.2.
- **W1 baseline만으로도 끝까지 동작합니다.** 추가 기능(W2)은 전부 opt-in

### 0. 설치 (Install)

**필수 (Required)**
- Python 3.9 이상 (`python3 --version`으로 확인)
- git
- macOS / Linux (Windows는 WSL 권장)

**선택 (Optional, 실제 운용 시 필요)**
- [`gws` CLI](https://github.com/GAM-team/GAM) — 실제 Gmail 연동. 없으면 mock fixture로 dry-run만 가능
- Anthropic API 키 — W2의 LLM 분류기 사용 시. 없으면 substring 분류기로 fallback (대부분 충분)

**설치 (Install)**

```bash
# Claude Code skills 디렉토리에 clone
git clone https://github.com/challengekim/snowball-email.git ~/.claude/skills/snowball-email

# 동작 확인
cd ~/.claude/skills/snowball-email
bin/snowball-email --help
```

추가로 설치할 의존성은 **없습니다** — Python 표준 라이브러리만 사용. `pip install` 불필요.

Claude Code에서는 자동으로 `/snowball-email`로 인식됩니다.

### 0.5 부트스트랩 (초기 학습 — cold-start → warm-start)

처음부터 양질의 초안을 받으려면 **첫 사용 전에 회사 자산을 reference에 시드**하세요. 4개 소스를 지원하고, 모든 소스는 `bootstrap_pending.md`에 후보를 쌓아두면 사용자가 한 줄씩 검토·승인 후에야 reference에 반영됩니다 (자동 승인 없음).

```bash
# (a) 홈페이지 / FAQ / 소개서 PDF — urllib으로 fetch, 로컬 PDF는 pdftotext
bin/snowball-email bootstrap --inbox myteam web \
  --urls https://yourcompany.com/faq https://yourcompany.com/about /path/to/deck.pdf

# (b) 과거 이메일 — gws cli로 라벨/검색어 매칭 thread 가져와 패턴 후보 추출
bin/snowball-email bootstrap --inbox myteam gmail \
  --query "label:support older_than:90d" --max-threads 50

# (c) Notion 페이지/DB — 사내 위키, FAQ, 운영 가이드
bin/snowball-email bootstrap --inbox myteam notion \
  --page-ids <page_id> --database-ids <db_id>

# (d) 채널톡 export JSON — 과거 상담 대화
bin/snowball-email bootstrap --inbox myteam channeltalk \
  --export /path/to/channeltalk-export.json
```

각 명령은 `--dry-run`을 지원해서 실제 reference 변경 없이 후보만 확인할 수 있습니다.

**검토 흐름:**
1. 위 명령들이 후보를 `inboxes/<name>/bootstrap_pending.md`에 추가합니다
2. 파일을 열어 한 줄씩 검토 — 살릴 항목은 `[x]`, 버릴 항목은 그대로 두기
3. `bin/snowball-email view --inbox myteam`으로 reference 반영 결과 확인

**중단 후 재개:** 각 inbox는 `bootstrap_state.json`으로 idempotent resume을 지원합니다. 중간에 멈춰도 같은 명령을 다시 실행하면 마지막 cursor에서 이어서 진행됩니다.

부트스트랩을 건너뛰어도 동작은 하지만, **첫 회신 품질이 평범한 수준에서 시작**합니다. 회사 자산이 있으면 시드해두는 걸 강하게 권장합니다.

### 1. 본 스킬은 무엇인가

Gmail 라벨 1개를 받아서, 매 round마다 다음 8단계를 자동으로 돕습니다:

1. **Fetch unread** — gws cli로 라벨 미읽음 thread 조회
2. **Classify** — 본문을 카테고리별로 분류 + 위험도 (tier-A / tier-B) 결정
3. **Draft** — 분류 결과를 토대로 초안 작성 (v0.1.x: 한국어 템플릿 고정 / v0.2: reference + persona principles 주입)
4. **Approval gate** — 사용자에게 "이대로 보낼까요?" 승인 요청
5. **Send** — 디폴트는 `gws_drafts` (Gmail 초안만 만들고 사용자가 수동 Send)
6. **Mark read** — 원본 thread 읽음 처리 + 라벨 정리
7. **Reference append** — 새 패턴/사례/표현을 reference 파일에 기록
8. **Metrics log** — round당 1줄 KPI를 metrics.jsonl에 기록

회를 거듭할수록 7단계의 reference가 두꺼워져 *분류 정확도*가 round 단위로 좋아집니다 (UNKNOWN 비율 감소). 본문 품질이 reference로 좋아지는 것은 v0.2 작업이며, 그 단계에서 `edit_ratio` 측정도 함께 활성화됩니다 — 자세한 현황은 [§4.5](#45-진행-상황--what-actually-compounds-today) 참고.

### 2. 5분 만에 시작

```bash
cd ~/.claude/skills/snowball-email

# (1) inbox 1개 만들기 — 대화형 질문 (W2 옵션 포함, 모두 디폴트 OFF)
bin/snowball-email init --inbox myteam

# (2) dry-run — 실제 발송 없이 초안만 확인
bin/snowball-email run --inbox myteam --dry-run --auto-approve

# (3) 누적된 reference 보기
bin/snowball-email view --inbox myteam

# (4) KPI 추이
bin/snowball-email metrics --inbox myteam --last 50
```

추가 유틸 (전체 명령은 `bin/snowball-email --help`):

```bash
bin/snowball-email grep "환불" --inbox myteam     # reference 검색
bin/snowball-email diff --inbox myteam            # 직전 round 대비 reference 변경
bin/snowball-email config get send.backend --inbox myteam
bin/snowball-email config set classify.backend llm_anthropic --inbox myteam
```

`gws` CLI나 API 키가 없어도 mock fixture로 dry-run이 동작합니다. 실제 운용은 [`docs/MANUAL.md`](docs/MANUAL.md) §4 (KO) / §4 (EN) 참고.

### 3. W2 옵션 (전부 opt-in)

| 옵션 | 디폴트 | 켜면 무엇이 달라지나 |
|---|---|---|
| `classify.backend = llm_anthropic` | `substring` | LLM 분류기 사용 (Anthropic Haiku 기본). 키 없으면 자동으로 substring fallback |
| `classify.api_key_env` | `ANTHROPIC_API_KEY` | 키를 어떤 env var에서 읽을지 |
| `learn.auto_case` | `false` | 승인+발송된 회신을 자동으로 `cases/<cls>.jsonl`에 누적 (dry-run / UNKNOWN은 제외) |

**아무 것도 켜지 않아도 W1 baseline (substring 분류기 + 수동 reference 누적)으로 정상 동작합니다.** 자세한 설정과 트레이드오프는 [`docs/MANUAL.md`](docs/MANUAL.md) §6 참고.

### 4. 다중 inbox

여러 회사 / 역할을 처리할 때 `--inbox <name>`으로 분리합니다. 각 inbox는 독립된 reference / config / metrics / bootstrap_state를 가집니다.

```bash
bin/snowball-email init --inbox partnerships
bin/snowball-email run --inbox partnerships
```

### 4.5 진행 상황 — what actually compounds today

매 round마다 `metrics.jsonl`에 1줄이 적립됩니다. `bin/snowball-email metrics --inbox myteam --last 50`으로 봅니다.

**v0.1.x에서 실제로 measure되는 신호:**

- **`unk`** (unknown_count) — 새 메일이 reference의 패턴 어느 것에도 매칭 안 된 횟수. 패턴이 누적될수록 줄어듦. *이게 v0.1의 진짜 compound 효과입니다.*
- **`new`** (new_patterns) — 이번 round에서 새로 자동 등록된 stub 패턴 수. 초기 N round 동안 많고 이후 수렴.
- **`A` / `B`** — tier-A (단일 확인) vs tier-B (일괄 승인) 분포. calibration 비중 추적.

**v0.2까지는 의미 없는 칼럼:**

- **`edit%`** — 현재 코드 (`assets/run_round.py`)는 사용자 edit를 캡처하는 단계가 없어 `edit_ratio`가 항상 `0.00`으로 기록됩니다. 의도된 임계값(>10%)이 작동하려면 승인 게이트에 edit 캡처 UI를 붙여야 하며, 이는 v0.2 마일스톤. 지금 `metrics` 표에 `edit%` 칼럼이 보이는 건 자리만 잡아둔 것 — 의사결정에 쓰지 마세요.

**진짜 compound가 작동 중인지 보는 법:**

```bash
bin/snowball-email metrics --inbox myteam --last 30
# unknown_count 평균을 round 1-10 vs round 21-30으로 비교 — 떨어지면 분류 학습이 작동.
```

**드래프트 본문 quality compound는 아직 없음.** `build_draft()`는 분류 결과만 보고 한국어 템플릿을 채우며, persona/principles/cases는 본문 생성 프롬프트에 들어가지 않습니다. v0.2에서 reference-driven drafting이 도입되면 `edit%`가 의미를 갖게 됩니다.

### 4.6 보안 (Security)

- **Gmail 토큰**: gws CLI가 OAuth 토큰을 자체적으로 관리합니다 (보통 `~/.config/gam/` 또는 `~/.gws/`). snowball-email은 토큰 파일을 *직접 읽거나 저장하지 않습니다*. gws CLI 호출만 합니다.
- **API 키**: Anthropic / SendGrid 키는 모두 **env var에서만** 읽습니다 (`classify.api_key_env`, `send.sendgrid.api_key_env`). config 파일에 키 자체를 저장하지 마세요.
- **발송 안전장치**: 디폴트 backend는 `gws_drafts` — Gmail 초안만 만들고 사용자가 Gmail UI에서 수동 Send. `gws_send` / `sendgrid`는 명시적 opt-in.
- **승인 게이트**: 모든 round에서 사용자 명시 승인 후에만 발송. 자동 승인 옵션 없음 (verbatim 비협상).
- **Audit trail**: `send.bcc`로 자기 자신을 BCC하면 발송 사본이 본인 inbox에 남음.
- **runtime 데이터**: `inboxes/<name>/`은 `.gitignore` 처리되어 있어 reference / metrics / config가 commit되지 않습니다.

### 5. 본 스킬을 쓰지 않을 경우

| 상황 | 권장 대안 |
|---|---|
| 멀티 유저 / SLA 관리 / 팀 인박스 | Intercom, Front, Help Scout |
| 신규 마케팅 메일 발송 | Mailchimp, ActiveCampaign |
| 법무·환불 분쟁 escalation | 인간 직접 처리 |
| 1일 100건 이상 회신 | 승인 게이트 강제로 throughput 제한 — SaaS가 더 빠름 |

본 스킬은 **1인 운영자가 라벨 1~3개 / 1일 5–30건 회신** 구간에 최적화돼 있습니다.
CS 외에도 BD cold outreach 응답, recruiting 후보자 follow-up, partnerships 협업 검토 같은 모든 이메일 소통에 동일하게 쓸 수 있습니다 — `init` 시 `inbox.persona`로 톤·패턴을 골라서 시작합니다.

---

## English

### Why this skill
- A plain draft on day 1, an in-house expert by reply #100
- Uses only the `gws` CLI (Google Workspace) — zero extra SaaS spend
- Every send requires explicit user approval — non-negotiable
- **W1 baseline runs end-to-end on its own.** All extras (W2) are opt-in

### 0. Install

**Required**
- Python 3.9+ (`python3 --version` to check)
- git
- macOS / Linux (Windows: use WSL)

**Optional (for real Gmail use)**
- [`gws` CLI](https://github.com/GAM-team/GAM) — actual Gmail integration. Without it, only `--dry-run` works (uses mock fixtures)
- Anthropic API key — for W2's LLM classifier. Falls back to substring matching when missing (good enough for most cases)

**Install**

```bash
# Clone into your Claude Code skills directory
git clone https://github.com/challengekim/snowball-email.git ~/.claude/skills/snowball-email

# Verify
cd ~/.claude/skills/snowball-email
bin/snowball-email --help
```

**No extra dependencies** — pure Python stdlib. No `pip install` needed.

Claude Code auto-discovers it as `/snowball-email`.

### 0.5 Bootstrap (cold-start → warm-start)

For quality drafts from day one, **seed the reference with your company's assets before the first run**. Four sources are supported. Every source appends candidates to `bootstrap_pending.md` for line-by-line user review — nothing lands in `reference/` until you approve it (no auto-approval).

```bash
# (a) Website / FAQ / decks — fetched via urllib; local PDFs via pdftotext
bin/snowball-email bootstrap --inbox myteam web \
  --urls https://yourcompany.com/faq https://yourcompany.com/about /path/to/deck.pdf

# (b) Past Gmail threads — gws cli pulls matching threads and extracts pattern candidates
bin/snowball-email bootstrap --inbox myteam gmail \
  --query "label:support older_than:90d" --max-threads 50

# (c) Notion pages / databases — internal wiki, FAQ, ops guides
bin/snowball-email bootstrap --inbox myteam notion \
  --page-ids <page_id> --database-ids <db_id>

# (d) ChannelTalk export JSON — historical chat transcripts
bin/snowball-email bootstrap --inbox myteam channeltalk \
  --export /path/to/channeltalk-export.json
```

Each command supports `--dry-run` to preview without touching the reference.

**Review flow:**
1. The commands above append candidates to `inboxes/<name>/bootstrap_pending.md`
2. Open the file and review line by line — mark items to keep with `[x]`, leave others as-is
3. Run `bin/snowball-email view --inbox myteam` to inspect the resulting reference

**Resume after interruption:** Each inbox tracks progress in `bootstrap_state.json` for idempotent resume. If you stop mid-way, re-running the same command picks up from the last successful cursor.

Skipping bootstrap still works, but **early drafts will be plain**. If you have any existing assets, seeding them is strongly recommended.

### 1. What it does

Given one Gmail label, each round walks through 8 steps:

1. **Fetch unread** — list unread threads via `gws`
2. **Classify** — bucket each message and assign tier-A / tier-B risk
3. **Draft** — write a reply from the classification result (v0.1.x: fixed Korean template; v0.2: inject reference + persona principles)
4. **Approval gate** — ask the user "send this?"
5. **Send** — default is `gws_drafts` (Gmail draft only; user clicks Send)
6. **Mark read** — mark the original thread read + clean up labels
7. **Reference append** — record new patterns / cases / phrasings
8. **Metrics log** — append a 1-line KPI row to `metrics.jsonl`

The thicker step 7 becomes, the better step 2's *classification* gets (UNKNOWN rate drops). Quality compounding for step 3 (the reply body) is a v0.2 milestone — see [§4.5](#45-what-actually-compounds-today).

### 2. Five-minute start

```bash
cd ~/.claude/skills/snowball-email

# (1) Create one inbox — interactive prompts (W2 options included, all default OFF)
bin/snowball-email init --inbox myteam

# (2) Dry-run — produce drafts without sending anything
bin/snowball-email run --inbox myteam --dry-run --auto-approve

# (3) Inspect the accumulated reference
bin/snowball-email view --inbox myteam

# (4) KPI trend
bin/snowball-email metrics --inbox myteam --last 50
```

Extra utilities (`bin/snowball-email --help` for the full list):

```bash
bin/snowball-email grep "refund" --inbox myteam   # search reference
bin/snowball-email diff --inbox myteam            # reference changes since last round
bin/snowball-email config get send.backend --inbox myteam
bin/snowball-email config set classify.backend llm_anthropic --inbox myteam
```

You don't need `gws` or any API key for dry-run — mock fixtures cover the full path. For real-world setup see [`docs/MANUAL.md`](docs/MANUAL.md) §4 (English).

### 3. W2 options (all opt-in)

| Option | Default | What turning it on does |
|---|---|---|
| `classify.backend = llm_anthropic` | `substring` | Switch to LLM classifier (Anthropic Haiku by default). Falls back to substring automatically if the key is missing or the call fails |
| `classify.api_key_env` | `ANTHROPIC_API_KEY` | Env var name the key is read from |
| `learn.auto_case` | `false` | Auto-append every approved+sent reply into `cases/<cls>.jsonl` (skipped for dry-run / UNKNOWN) |

**With nothing enabled, the skill still runs the full W1 baseline (substring classifier + manual reference appends).** See [`docs/MANUAL.md`](docs/MANUAL.md) §6 for trade-offs.

### 4. Multi-inbox

Use `--inbox <name>` to separate several companies/roles. Each inbox keeps its own reference / config / metrics / bootstrap_state.

### 4.5 What actually compounds today

Every round appends a row to `metrics.jsonl`. Inspect with `bin/snowball-email metrics --inbox myteam --last 50`.

**Signals that work in v0.1.x:**

- **`unk`** (unknown_count) — messages that matched no pattern in the reference. As patterns accumulate, this drops. *This is the genuine compound effect at v0.1.*
- **`new`** (new_patterns) — stub patterns auto-registered this round. High at first, then converges.
- **`A` / `B`** — tier-A (single confirm) vs tier-B (batch approve) split; tracks calibration phase.

**Columns that are placeholders until v0.2:**

- **`edit%`** — the current code (`assets/run_round.py`) does not capture user edits between draft generation and approval, so `edit_ratio` is structurally always `0.00`. The intended `>10%` warning never fires. Wiring real edit capture into the approval gate is a v0.2 milestone — until then this column is a placeholder. Don't make decisions from it.

**How to verify the working compound loop:**

```bash
bin/snowball-email metrics --inbox myteam --last 30
# Compare avg unknown_count for rounds 1-10 vs 21-30. A drop confirms classification learning.
```

**Reply-body quality compounding doesn't exist yet.** `build_draft()` only consults the classification result and fills a Korean template — persona/principles/cases are not passed into body generation. Once v0.2 lands the reference-driven drafter, `edit%` becomes meaningful.

### 4.6 Security

- **Gmail tokens**: gws CLI manages OAuth tokens itself (typically `~/.config/gam/` or `~/.gws/`). snowball-email *never reads or stores token files directly* — it only invokes the gws CLI.
- **API keys**: Anthropic / SendGrid keys are read **only from env vars** (`classify.api_key_env`, `send.sendgrid.api_key_env`). Never store the key itself in config files.
- **Send safety**: Default backend is `gws_drafts` — creates Gmail drafts; the user manually clicks Send in Gmail UI. `gws_send` / `sendgrid` are explicit opt-in.
- **Approval gate**: Every round requires explicit user approval before send. No auto-approval option (non-negotiable).
- **Audit trail**: Set `send.bcc` to your own address for a self-BCC copy of every send.
- **Runtime data**: `inboxes/<name>/` is gitignored — references / metrics / configs never get committed.

### 5. When NOT to use this

| Situation | Better tool |
|---|---|
| Multi-user / SLA / team inbox | Intercom, Front, Help Scout |
| Outbound marketing | Mailchimp, ActiveCampaign |
| Legal / refund escalations | Handle by hand |
| 100+ replies/day | The approval gate caps throughput — a SaaS will be faster |

Sweet spot: **a solo operator handling 1–3 labels and 5–30 replies per day.**
Beyond customer support, the same loop fits BD cold-outreach replies, recruiting candidate follow-ups, and partnerships triage — pick the right tone+patterns at `init` time via `inbox.persona`.

---

## 참고 / References

- [`docs/MANUAL.md`](docs/MANUAL.md) — 전체 매뉴얼 (KO + EN)
- [`PLAN.md`](PLAN.md) — 설계 문서 (consensus 통과)
- [`SKILL.md`](SKILL.md) — 스킬 entrypoint (8단계 워크플로우 명세)
- [`LICENSE`](LICENSE) — MIT License
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — 기여 가이드 (KO)
