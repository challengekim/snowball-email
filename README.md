# support-reply-public

> 이메일 회신 초안을 만들고, 매 회신마다 reference가 누적되어 시간이 지날수록 **복리로 더 잘 답하게 되는** 스킬.
> Compound-learning email support skill — drafts compound in quality round over round.

**전체 매뉴얼은 [`docs/MANUAL.md`](docs/MANUAL.md) (한국어 + English 동시 수록).**
**Full bilingual manual: [`docs/MANUAL.md`](docs/MANUAL.md).**

---

## 한국어

### 핵심 가치
- 처음 쓸 때는 평범한 초안이지만, 100번째 사용에선 그 비즈니스 전문가 수준의 초안
- gws cli (Google Workspace CLI)만 쓰므로 추가 SaaS 비용 0
- 모든 발송은 사용자 명시 승인 후 진행 — verbatim 비협상
- **W1 baseline만으로도 끝까지 동작합니다.** 추가 기능(W2)은 전부 opt-in

### 1. 본 스킬은 무엇인가

Gmail 라벨 1개를 받아서, 매 round마다 다음 8단계를 자동으로 돕습니다:

1. **Fetch unread** — gws cli로 라벨 미읽음 thread 조회
2. **Classify** — 본문을 카테고리별로 분류 + 위험도 (tier-A / tier-B) 결정
3. **Draft** — 누적된 reference (patterns, cases, core 톤앤매너) 참조해 초안 작성
4. **Approval gate** — 사용자에게 "이대로 보낼까요?" 승인 요청
5. **Send** — 디폴트는 `gws_drafts` (Gmail 초안만 만들고 사용자가 수동 Send)
6. **Mark read** — 원본 thread 읽음 처리 + 라벨 정리
7. **Reference append** — 새 패턴/사례/표현을 reference 파일에 기록
8. **Metrics log** — round당 1줄 KPI를 metrics.jsonl에 기록

회를 거듭할수록 7단계의 reference가 두꺼워져 3단계 초안 품질이 복리로 향상됩니다.

### 2. 5분 만에 시작

```bash
cd ~/.claude/skills/support-reply-public

# (1) inbox 1개 만들기 — 대화형 질문 (W2 옵션 포함, 모두 디폴트 OFF)
bin/support-reply init --inbox myteam

# (2) dry-run — 실제 발송 없이 초안만 확인
bin/support-reply run --inbox myteam --dry-run --auto-approve

# (3) 누적된 reference 보기
bin/support-reply view --inbox myteam

# (4) KPI 추이
bin/support-reply metrics --inbox myteam --last 50
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
bin/support-reply init --inbox partnerships
bin/support-reply run --inbox partnerships
```

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

### 1. What it does

Given one Gmail label, each round walks through 8 steps:

1. **Fetch unread** — list unread threads via `gws`
2. **Classify** — bucket each message and assign tier-A / tier-B risk
3. **Draft** — use the accumulated `reference/` (patterns, cases, tone) to write a reply
4. **Approval gate** — ask the user "send this?"
5. **Send** — default is `gws_drafts` (Gmail draft only; user clicks Send)
6. **Mark read** — mark the original thread read + clean up labels
7. **Reference append** — record new patterns / cases / phrasings
8. **Metrics log** — append a 1-line KPI row to `metrics.jsonl`

The thicker step 7 becomes, the better step 3's drafts get — that's the compounding loop.

### 2. Five-minute start

```bash
cd ~/.claude/skills/support-reply-public

# (1) Create one inbox — interactive prompts (W2 options included, all default OFF)
bin/support-reply init --inbox myteam

# (2) Dry-run — produce drafts without sending anything
bin/support-reply run --inbox myteam --dry-run --auto-approve

# (3) Inspect the accumulated reference
bin/support-reply view --inbox myteam

# (4) KPI trend
bin/support-reply metrics --inbox myteam --last 50
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
- 라이선스: 사용자 개인 도구 — 외부 배포 시 PLAN §12 참조
