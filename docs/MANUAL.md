# snowball-email — Manual / 매뉴얼

Bilingual user manual. 한국어 먼저, English follows.

---

## 한국어

### 1. 이게 뭔가요?

Gmail 라벨 1개에 들어온 문의를 받아서, 회신 초안을 자동 생성해 주는 Claude Code 스킬입니다. **모든 발송은 사용자가 명시 승인한 다음에만** 진행됩니다 (verbatim 비협상).

핵심은 **compound brain** — 매 라운드(round)마다 분류 패턴/사례/원칙이 `reference/`에 누적돼, 회를 거듭할수록 초안 품질이 복리로 향상됩니다.

### 2. 무엇을 미리 준비해야 하나요?

| 필수 | 선택 |
|---|---|
| Python 3.10 이상 | `gws` CLI (Google Workspace) — 실제 Gmail 연동 시 |
| (그게 전부) | `ANTHROPIC_API_KEY` — LLM 분류기 사용 시 |
|  | `SENDGRID_API_KEY` — SendGrid 백엔드 사용 시 |

**아무 것도 없어도 dry-run으로 시작 가능합니다.** mock fixture로 모든 단계가 동작하는지 먼저 확인할 수 있어요.

### 3. 5분 안에 시작하기

```bash
cd ~/.claude/skills/snowball-email

# (1) inbox 1개 만들기 — 대화형 7개 질문 + 3개 W2 옵션 질문
bin/snowball-email init --inbox myinbox

# (2) 아무 것도 없는 상태에서 dry-run으로 동작 확인
bin/snowball-email run --inbox myinbox --dry-run --auto-approve

# (3) 결과 확인
bin/snowball-email view --inbox myinbox     # 누적된 reference 보기
bin/snowball-email metrics --inbox myinbox  # 라운드별 KPI 표
```

### 4. 라이브 사용 (gws CLI 인증 필요)

```bash
# 발신자 정보 설정 (init에서 입력했다면 생략)
bin/snowball-email config set send.from_email "support@yourcompany.com" --inbox myinbox
bin/snowball-email config set inbox.label "고객문의" --inbox myinbox

# 라이브 라운드 실행 (대화형 승인)
bin/snowball-email run --inbox myinbox
# → 초안 표 → "발송 선택? all / n / n,m / n-m / skip :" 입력 대기
```

### 5. 부트스트랩 (선택)

빈 reference로 시작하면 첫 N회는 모든 초안이 UNKNOWN tier-A로 분류됩니다. 사전에 지식을 넣고 싶다면:

```bash
# 4개 소스 모두 dry-run 지원
bin/snowball-email bootstrap --inbox myinbox web --urls https://yourco.com/faq
bin/snowball-email bootstrap --inbox myinbox notion --page-ids <page_id> --database-ids <db_id>
bin/snowball-email bootstrap --inbox myinbox gmail --query "label:과거고객문의 older_than:90d" --max-threads 50
bin/snowball-email bootstrap --inbox myinbox channeltalk --export ./channeltalk_export.json
```

### 6. W2 옵션 (선택, 모두 opt-in)

W2 기능은 **활성화하지 않으면 W1 baseline으로 동작**합니다. 즉, API 키 없이 그대로 시작 가능.

#### 6-1. LLM 분류기 켜기

기본은 `substring` (무료, 오프라인). 더 높은 분류 정확도가 필요하면:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
bin/snowball-email config set classify.backend llm_anthropic --inbox myinbox
```

라운드당 LLM 호출 1회 추가됨. 키 없거나 호출 실패 시 자동으로 substring으로 fallback (라운드 실패하지 않음).

#### 6-2. 자동 case 누적

승인+발송된 round마다 `reference/cases/<classification>.jsonl`에 1줄 추가:

```bash
bin/snowball-email config set learn.auto_case true --inbox myinbox
```

dry-run 또는 UNKNOWN 분류는 누적되지 않습니다.

### 7. 다중 inbox

회사가 여러 개거나 라벨이 여러 개면 그냥 `--inbox <이름>` 다르게 지정:

```bash
bin/snowball-email init --inbox companyA
bin/snowball-email init --inbox companyB
bin/snowball-email run --inbox companyA --dry-run --auto-approve
bin/snowball-email run --inbox companyB --dry-run --auto-approve
```

각 inbox는 `inboxes/<name>/`에 완전히 격리됩니다 (config, reference, metrics).

### 8. 명령 레퍼런스

| 명령 | 설명 |
|---|---|
| `init [--inbox X]` | 대화형 설정 wizard |
| `config get|set <key> [value] [--inbox X]` | flat key 읽기/쓰기 (`inbox.label`, `send.backend` 등) |
| `bootstrap [--inbox X] [--dry-run] <gmail|web|notion|channeltalk> [...]` | 부트스트랩 ingest |
| `view [--inbox X]` | `_compiled.md` (누적 reference 평면 뷰) 출력 |
| `grep <pattern> [--inbox X]` | reference 안에서 정규식 검색 |
| `diff [--inbox X]` | 직전 round 대비 reference 변경분 |
| `metrics [--inbox X] [--last N]` | KPI 표 (drafts/edit%/unk/new/A/B/send) + summary |
| `run [--inbox X] [--dry-run] [--fixture P] [--auto-approve]` | 한 라운드 실행 |

### 9. 2-tier 승인 게이트

모든 초안은 자동으로 tier-A 또는 tier-B로 분류됩니다.

- **tier-A (단일 확인 필요)**: calibration 모드 (첫 30 round + 50 round마다 1회), `UNKNOWN` 분류, confidence < 0.85, 본문에 금액 표현+LLM 동의(dual-gate), 외부 비공식 링크+LLM 동의, 이 inbox의 첫 발송
- **tier-B (일괄 승인 가능)**: 위 어디에도 해당 안 됨

보수적 편향 — 애매하면 tier-A.

### 10. 파일 위치

```
~/.claude/skills/snowball-email/
├── bin/snowball-email              # CLI entrypoint
├── assets/                         # 핵심 모듈 (run_round, classify, send_backends, reference_store)
├── ingest/                         # 4개 부트스트랩 ingester
├── inboxes/<name>/
│   ├── config.yaml                 # 이 inbox 설정 (flat YAML)
│   ├── metrics.jsonl               # 라운드별 KPI (1라운드 1줄)
│   └── reference/
│       ├── patterns/<id>.md        # 분류 패턴 (idempotent)
│       ├── cases/<cat>.jsonl       # 사례 (auto_case=true 시 자동 누적)
│       ├── links.md                # 정규 링크
│       ├── principles.md           # 톤앤매너 원칙
│       ├── _compiled.md            # 자동 재빌드되는 평면 뷰
│       └── _backups/               # _compiled 타임스탬프 백업
└── docs/MANUAL.md                  # 이 문서
```

### 11. 자주 묻는 것

**Q. gws CLI 없으면 절대 못 쓰나요?**
A. dry-run은 mock fixture로 동작하므로 학습/테스트는 가능. 라이브 사용은 `gws` (또는 SendGrid) 인증이 필요합니다.

**Q. 데이터가 외부로 나가나요?**
A. 기본 substring 분류기는 100% 로컬. `classify.backend=llm_anthropic` 켰을 때만 메일 본문 일부(최대 3000자)와 reference 일부(4000자)가 Anthropic API로 전송됩니다.

**Q. 잘못 보낸 회신을 되돌릴 수 있나요?**
A. 발송 자체는 비가역. 단, 기본 백엔드 `gws_drafts`는 발송이 아니라 **드래프트만 생성**하므로 사용자가 Gmail에서 한 번 더 검토 후 보냅니다 (graduation backend `gws_send`는 진짜 발송).

**Q. reference가 너무 커지면?**
A. `_compiled.md` 재빌드 시 `cases`는 카테고리당 최근 10건만 포함. `patterns`는 모두 포함. 100라운드 이상 사용 시 PLAN §5에 정의된 카테고리 분리 전략(W3) 권장.

### 12. 역할별 사용법 (CS / BD / recruiting / partnerships / sales)

`init` 시 `inbox.persona`로 한 번만 고르면 톤(`reference/principles.md`)과 시드 패턴(`reference/patterns/*.md`)이 자동 세팅됩니다. 같은 8단계 루프가 모든 역할에 그대로 동작합니다.

| Persona | 라벨 예시 | 자동 시드 패턴 | 핵심 톤 |
|---|---|---|---|
| `cs` (default) | `support`, `help` | refund / shipping / technical / bug / feature | 정중·간결, 사과 짧게 해결책 명확 |
| `bd` | `bd_outbound`, `intros` | cold_outreach / partnership / intro / pricing / follow_up | 가치 1줄 + CTA 1개, 자랑 금지 |
| `recruiting` | `talent`, `hiring` | (직접 추가) | 후보자 시간 존중, 역할/연봉 범위 노출, opt-out 명시 |
| `partnerships` | `partners` | (직접 추가) | 양측 이익 1문장, 다음 액션 1개 |
| `sales` | `sales`, `leads` | (직접 추가) | 문제→해결→다음 액션, follow-up은 새 정보 들고 |

여러 inbox 동시 운영도 지원합니다 — CS 인박스에서 환불 처리하고 BD 인박스에서 cold outreach 답신하는 흐름이 같은 명령(`run --inbox <name>`)으로 분리됩니다.

---

## English

### 1. What is this?

A Claude Code skill that drafts replies to Gmail messages tagged with one specific label. **Every send goes out only after explicit user approval** (verbatim non-negotiable).

The core idea is the **compound brain** — every round appends classification patterns, cases, and principles to `reference/`, so draft quality compounds over time.

### 2. What do you need?

| Required | Optional |
|---|---|
| Python 3.10+ | `gws` CLI (Google Workspace) for live Gmail |
| (that's it) | `ANTHROPIC_API_KEY` for the LLM classifier |
|  | `SENDGRID_API_KEY` for the SendGrid backend |

**You can start with nothing in dry-run.** Mock fixtures exercise the full pipeline.

### 3. 5-minute quick start

```bash
cd ~/.claude/skills/snowball-email

# 1. Create one inbox via wizard (7 base + 3 W2 prompts)
bin/snowball-email init --inbox myinbox

# 2. Dry-run to see the loop
bin/snowball-email run --inbox myinbox --dry-run --auto-approve

# 3. Inspect
bin/snowball-email view --inbox myinbox      # accumulated reference
bin/snowball-email metrics --inbox myinbox   # KPI table
```

### 4. Going live (requires gws CLI auth)

```bash
bin/snowball-email config set send.from_email "support@yourco.com" --inbox myinbox
bin/snowball-email config set inbox.label "Customer Inquiries" --inbox myinbox

bin/snowball-email run --inbox myinbox
# → draft table → "Pick to send: all / n / n,m / n-m / skip:"
```

### 5. Bootstrap (optional)

Empty reference means the first N drafts will all be UNKNOWN tier-A. Pre-seed knowledge with:

```bash
bin/snowball-email bootstrap --inbox myinbox web --urls https://yourco.com/faq
bin/snowball-email bootstrap --inbox myinbox notion --page-ids <page_id> --database-ids <db_id>
bin/snowball-email bootstrap --inbox myinbox gmail --query "label:past-tickets older_than:90d" --max-threads 50
bin/snowball-email bootstrap --inbox myinbox channeltalk --export ./export.json
```

All four ingesters support `--dry-run`.

### 6. W2 options (all opt-in)

W2 features default to OFF. The skill **runs at W1 baseline if you turn nothing on**. No API key needed to start.

#### 6-1. Enable the LLM classifier

Default is `substring` (free, offline). For higher accuracy:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
bin/snowball-email config set classify.backend llm_anthropic --inbox myinbox
```

Adds one LLM call per round. Falls back to substring on missing key or any HTTP failure (round never fails for classifier reasons).

#### 6-2. Auto-case accumulation

Append one case row per approved+sent draft to `reference/cases/<classification>.jsonl`:

```bash
bin/snowball-email config set learn.auto_case true --inbox myinbox
```

Dry-runs and UNKNOWN classifications are skipped.

### 7. Multiple inboxes

```bash
bin/snowball-email init --inbox companyA
bin/snowball-email init --inbox companyB
bin/snowball-email run --inbox companyA --dry-run --auto-approve
```

Each inbox is fully isolated under `inboxes/<name>/` (config, reference, metrics).

### 8. Command reference

| Command | Purpose |
|---|---|
| `init [--inbox X]` | Interactive setup wizard |
| `config get\|set <key> [value] [--inbox X]` | Read/write flat config (`inbox.label`, `send.backend`, ...) |
| `bootstrap [--inbox X] [--dry-run] <gmail\|web\|notion\|channeltalk> [...]` | Bootstrap ingest |
| `view [--inbox X]` | Print `_compiled.md` |
| `grep <pattern> [--inbox X]` | Regex search inside reference |
| `diff [--inbox X]` | Show changes vs. last round |
| `metrics [--inbox X] [--last N]` | KPI table (drafts/edit%/unk/new/A/B/send) + summary |
| `run [--inbox X] [--dry-run] [--fixture P] [--auto-approve]` | Run one round |

### 9. Two-tier approval gate

Every draft is classified A or B.

- **tier-A (single confirm)**: calibration mode (first 30 rounds + every 50), `UNKNOWN` classification, confidence < 0.85, body contains money + LLM agrees (dual-gate), external non-canonical link + LLM agrees, first send for inbox
- **tier-B (batch confirm OK)**: none of the above

Conservative bias — when in doubt, A.

### 10. Layout

```
~/.claude/skills/snowball-email/
├── bin/snowball-email
├── assets/                         # core modules
├── ingest/                         # 4 bootstrap ingesters
├── inboxes/<name>/
│   ├── config.yaml
│   ├── metrics.jsonl
│   └── reference/
│       ├── patterns/<id>.md
│       ├── cases/<cat>.jsonl
│       ├── links.md
│       ├── principles.md
│       ├── _compiled.md
│       └── _backups/
└── docs/MANUAL.md
```

### 11. FAQ

**Q. Can I use this without `gws` CLI?**
A. Dry-run uses mock fixtures, so you can test/learn. Live use needs `gws` (or SendGrid) auth.

**Q. Does any data leave my machine?**
A. The default substring classifier is 100% local. Only when you set `classify.backend=llm_anthropic` do up to 3000 chars of mail body + 4000 chars of reference get sent to the Anthropic API.

**Q. Can I undo a sent reply?**
A. No — sending is irreversible. But the default backend `gws_drafts` only **creates a draft**; you review one more time inside Gmail before sending. The graduation backend `gws_send` actually sends.

**Q. What if reference grows huge?**
A. `_compiled.md` rebuild keeps only the last 10 cases per category; patterns are full. Past 100 rounds, plan to apply the per-category split strategy from PLAN §5 (W3).

### 12. Personas (CS / BD / recruiting / partnerships / sales)

Pick `inbox.persona` once during `init` and the wizard seeds the tone (`reference/principles.md`) and pattern files (`reference/patterns/*.md`). The same 8-step round runs for every role.

| Persona | Example labels | Auto-seeded patterns | Tone gist |
|---|---|---|---|
| `cs` (default) | `support`, `help` | refund / shipping / technical / bug / feature | Polite, concise; short apology, clear fix |
| `bd` | `bd_outbound`, `intros` | cold_outreach / partnership / intro / pricing / follow_up | One-line value + one CTA, no bragging |
| `recruiting` | `talent`, `hiring` | (add your own) | Respect candidate's time, surface role/comp band, explicit opt-out |
| `partnerships` | `partners` | (add your own) | One-sentence mutual benefit, one next action |
| `sales` | `sales`, `leads` | (add your own) | Problem → solution → next step; follow-ups carry new info only |

Multiple inboxes run side by side — handle CS refunds in one inbox and BD outreach in another, isolated by the same `run --inbox <name>` flag.
