---
name: support-reply-public
description: Compound-learning email reply skill for customer support, BD outreach, partnerships, recruiting, and sales — gws cli 기반 Gmail 회신 초안 생성, 4개 소스 부트스트랩 ingestion, reference 누적으로 회를 거듭할수록 초안 품질 복리 향상. init 시 persona (cs|bd|recruiting|partnerships|sales)를 골라 톤·시드 패턴을 자동 세팅. 모든 발송은 사용자 명시 승인 후 진행 (verbatim 비협상). 2-tier (A/B) 승인 게이트 + conservative bias 분류기. 다중 inbox 지원.
type: workflow
languages: [ko, en]
---

# support-reply-public

> 일반 사용자가 gws cli 기반으로 Gmail 라벨에 들어온 메일에 회신 초안을 만들고, 매 회신마다 reference를 누적해 시간이 지날수록 더 잘 답하게 되는 스킬. CS 외에 BD cold outreach, partnerships, recruiting, sales 등 모든 이메일 소통에 적용 가능.

**Persona 옵션** — `init` 시 `inbox.persona`로 한 번 선택하면 톤(`reference/principles.md`)과 시드 패턴(`reference/patterns/`)이 자동 세팅됩니다. 지원: `cs` (default) / `bd` / `recruiting` / `partnerships` / `sales` / `custom`. 인박스마다 다른 persona를 골라 multi-role 운영 가능.

## 1. 본 스킬을 언제 쓰는가 / When to invoke

- Gmail 라벨 1개에 들어오는 회신 가능한 메일을 처리할 때 (CS / BD / partnerships / recruiting / sales)
- 사용자가 "support 답장", "회신 초안", "support-reply 돌려", "BD 회신", "cold outreach 답장" 등으로 요청할 때
- 부트스트랩이 필요할 때: "support-reply 부트스트랩", "이 라벨로 첫 세팅"

## 2. 본 스킬을 쓰지 않는 경우 / When NOT to invoke

- Intercom/Front/Help Scout 등 본격 SaaS가 이미 깔린 환경 (그쪽이 멀티유저·SLA 관리·워크플로우 자동화에 더 우수)
- 회신이 아니라 신규 마케팅 메일을 발송해야 하는 경우 (별도 sender 스킬 필요)
- 답장 자체가 인간 판단의 영역이고 초안조차 위험한 경우 (법무, 환불 분쟁 escalation 등)

## 3. 8단계 워크플로우 / 8-step workflow

매 round마다 정확히 다음 순서를 따른다. 각 단계는 PLAN.md §3-9를 참조.

| Step | 작업 | 도구 | 위반 시 |
|---|---|---|---|
| 1 | **Fetch unread**: `gws gmail users threads list` (label 필터) | gws cli | 다른 Gmail 라이브러리 쓰면 SKILL 위반 |
| 2 | **Classify**: 본문을 카테고리로 분류 + tier-A/B 결정 | `approval/tier_classifier.py` | 신뢰도 < 0.85 → tier-A 강제 |
| 3 | **Draft**: reference 참조 후 초안 생성 (한국어 디폴트) | learner LLM (Sonnet) | reference 무시 시 round 무효 |
| 4 | **Approval gate**: 사용자에게 명시 승인 요청 (verbatim) | CLI 대화 | 자동 발송 절대 금지 |
| 5 | **Send**: 승인된 초안 발송 | `send/<backend>.py` | gws_drafts 디폴트 (안전) |
| 6 | **Mark read**: 원본 thread를 읽음 처리 + 라벨 정리 | `gws gmail users messages modify` | 누락 시 다음 round 중복 |
| 7 | **Reference append**: 새 패턴/사례를 reference 파일에 append | `reference/append.py` | 누락 시 compound 깨짐 |
| 8 | **Metrics log**: 1줄 JSONL을 `inboxes/<inbox>/metrics.jsonl`에 기록 | `metrics/logger.py` | 누락 시 KPI 추적 불가 |

### 승인 게이트 — 절대 비협상 / Approval gate — non-negotiable

- **모든 초안은 사용자가 "보내", "send it", "approve" 등 명시 승인을 한 후에만 발송**
- tier-A 항목은 1건씩 개별 승인 (first N round + 신뢰도 미달 + 금액 표현 + 비표준 링크 + UNKNOWN 분류)
- tier-B 항목은 N건 일괄 승인 가능 (W2 graduation gate 통과 후에만)
- **첫 30 round는 calibration mode** — 모든 draft를 tier-A로 강제 (분류기 sanity check)

## 4. 디렉토리 구조 / Directory layout

```
~/.claude/skills/support-reply-public/
├── SKILL.md                         # 본 파일
├── README.md                        # 사용자 온보딩 가이드 (한/영)
├── PLAN.md                          # 설계 문서 (consensus 통과)
├── bin/support-reply                # CLI dispatcher (init/config/bootstrap/view/grep/diff/metrics/run)
├── config/schema.yaml               # config 스키마 레퍼런스
├── ingest/                          # 4개 부트스트랩 소스
│   ├── _common.py                   # 공유: utc_run_id, begin_run, append_pending
│   ├── gmail.py                     # gws cli 기반 과거 thread ingest
│   ├── web.py                       # WebFetch + pdftotext fallback
│   ├── notion.py                    # Notion MCP page/database ingest
│   └── channeltalk.py               # ChannelTalk JSON export 파서
├── approval/
│   └── tier_classifier.py           # classify_tier(draft) → 'A' | 'B'
├── metrics/
│   └── logger.py                    # round 1줄 JSONL append + edit_ratio 계산
├── templates/                       # reference seed 템플릿 (core.md, patterns/, cases/)
└── inboxes/<inbox-name>/            # 사용자별 데이터 (스킬 코어와 분리)
    ├── config.yaml                  # 사용자 inbox 설정
    ├── reference/
    │   ├── core.md                  # 톤앤매너 + 비협상 원칙
    │   ├── patterns/*.md            # 분류 패턴 (카테고리별 1파일)
    │   ├── cases/*.jsonl            # 사례 테이블 (해결 사례)
    │   ├── _compiled.md             # patterns + cases 평탄화 (view 출력용)
    │   └── _last_round_snapshot.txt # diff 베이스라인
    ├── known_links.txt              # 표준 링크 화이트리스트 (외부 링크 감지용)
    ├── bootstrap_state.json         # 부트스트랩 idempotent 상태 (run_id, cursor, items_seen)
    ├── bootstrap_pending.md         # 부트스트랩 결과 line-by-line 검토 대기
    └── metrics.jsonl                # round 1줄 KPI 기록
```

**SUPPORT_REPLY_HOME** 환경변수로 위치 override 가능. 디폴트는 `~/.claude/skills/support-reply-public/`.

## 5. 4개 소스 부트스트랩 / 4-source bootstrap

매 소스는 `python3 ingest/<source>.py --inbox <name> [--dry-run]`로 호출. 모든 후보는 `bootstrap_pending.md`에 line-by-line 추가 — **자동 승인 없음**, 사용자가 수동 체크박스로 승인 후 reference에 반영.

| Source | 입력 | 추출 도구 | 사용자 검토 |
|---|---|---|---|
| gmail | label + 검색 쿼리 (예: `label:support older_than:90d`) | `gws gmail users threads list/get` | bootstrap_pending.md 라인별 체크 |
| web | URL 목록 + PDF 경로 | WebFetch + pdftotext | 라인별 체크 |
| notion | page_ids / database_ids | Notion MCP (`notion-fetch`, `notion-search`) | 라인별 체크 |
| channeltalk | 로컬 JSON export 파일 경로 | stdlib JSON 파서 | 라인별 체크 |

**Idempotent**: 동일 `run_id` (ISO 8601 UTC sec, `YYYYMMDDTHHMMSSZ`)로 재실행 시 마지막 cursor부터 재개. 부분 실패 안전.

## 6. Compound 메커니즘 / How "compound" actually works

회를 거듭할수록 초안이 좋아지는 이유는 다음 4가지가 매 round 자동으로 작동하기 때문:

1. **Reference append (Step 7)** — 매 회신 후 새 패턴/사례/표현을 patterns/*.md, cases/*.jsonl에 append. 다음 round에서 LLM이 참조.
2. **2-tier 승인 게이트** — 위험 영역(tier-A)은 항상 사용자 승인, 안전 영역(tier-B)은 graduation 후 일괄. 승인 비율 자체가 학습 신호.
3. **Metrics 기반 자가 진단** — `support-reply metrics`로 edit_ratio·unknown_rate·new_pattern_rate 추세 확인. PLAN §2 KPI threshold 위반 시 경고.
4. **View/grep/diff CLI** — `support-reply view`로 누적된 reference 평탄 출력, `grep`으로 특정 패턴 검색, `diff`로 round 간 변경 가시화.

KPI 측정은 `metrics.jsonl`에 round당 1줄 누적. 가짜 KPI 게임 방지를 위해 tier-A 비율 30% 하한 + tier-B-only handtime만 측정.

## 7. CLI 진입점 / CLI entry points

```bash
# 최초 1회
support-reply init                          # 인터랙티브 wizard (yaml 노출 X)
support-reply bootstrap gmail --inbox support
support-reply bootstrap web --inbox support
support-reply bootstrap notion --inbox support
support-reply bootstrap channeltalk --inbox support

# 매일 사용
support-reply run --inbox support           # 1 round (fetch → classify → draft → approve → send → log)
support-reply run --inbox support --dry-run # 발송 없이 초안만 보기

# Compound 가시화
support-reply view --inbox support          # _compiled.md 출력
support-reply grep '환불' --inbox support   # reference 검색
support-reply diff --inbox support          # 직전 round 대비 reference 변경
support-reply metrics --inbox support --last 50  # 최근 50 round KPI 추이

# 설정
support-reply config get send.backend
support-reply config set send.backend gws_send
```

## 8. 발송 backend / Send backends

| Backend | 동작 | 사용자 요건 |
|---|---|---|
| `gws_drafts` (MVP 디폴트) | Gmail 초안 생성, 사용자 수동 Send | gws 인증만 |
| `gws_send` (W3+, graduation gate 통과 후) | gws cli로 직접 발송 | from_email이 gws 계정 또는 verified send-as alias |
| `sendgrid` | SendGrid v3 REST | API key |
| `mailgun` | Mailgun REST | API key + domain |
| `smtp` | 일반 SMTP | host/port/user/pass |

**디폴트는 항상 `gws_drafts`** — 절대 자동 발송 안 함. 사용자가 Gmail UI에서 Send 누름. graduation gate (PLAN §6.3): N≥10 round, edit_ratio<15%, claims=0 통과 시 `gws_send` 권장.

## 9. 다중 inbox 지원 / Multi-inbox

한 사용자가 여러 회사/역할을 처리하려면 `--inbox <name>`으로 분리. 각 inbox는 독립된 reference, config, metrics, bootstrap_state를 가짐. 디폴트 inbox 이름은 `default`.

## 10. 안전장치 / Safety rails

- 모든 초안 발송은 사용자 명시 승인 (verbatim 비협상)
- 첫 5 round + 매 30 round calibration: 모든 draft tier-A 강제
- 분류 신뢰도 < 0.85 → tier-A 강제 (conservative bias)
- 새 외부 링크 (known_links.txt에 없음) → tier-A
- 금액 표현 (regex 매치) → tier-A
- UNKNOWN 분류 → tier-A
- BCC self (감사 trail) 디폴트 ON
- threading 헤더 (In-Reply-To/References) 항상 보존

## 11. 학습/프롬프트 / Learning & prompt strategy

- learner 모델: 디폴트 `claude-sonnet-4-6`, `config set learner.model`로 변경 가능
- 매 round 끝에 사용자에게 "이 초안 별로다?" feedback 1회 prompt (config로 끌 수 있음, 5회 누적 skip 시 경고)
- 사용자 수동 edit이 발생한 경우 edit_ratio 기록, 임계값 초과 시 `bootstrap_pending.md`에 새 후보 자동 추가

## 12. 부트스트랩 안 해도 동작 / Bootstrap is optional

부트스트랩 0건 상태에서도 reference는 `templates/`에 들어있는 seed (core.md, 빈 patterns/, 빈 cases/)로 동작. 다만 첫 N round의 초안 품질은 낮을 수밖에 없으므로, 가능한 4개 소스 중 1개 이상을 권장.

## 13. 기존 SaaS와의 차별점 / Difference from Intercom/Front

- **Compound**: SaaS 매크로/saved reply는 정적, 본 스킬은 매 round reference가 진화
- **승인 게이트 강제**: SaaS의 자동 응답이 위험한 영역 (한국어 뉘앙스, 환불, 법무) 보호
- **로컬 ownership**: reference가 사용자 파일 시스템에 있음, vendor lock-in 없음
- **gws cli 단일 의존**: 추가 SaaS 비용 0

PLAN.md §11 비교표 참조.

## 14. 종료 조건 / Exit & cancel

- `Ctrl+C` 또는 사용자 "stop" → 현재 round 안전 종료, state 보존
- 부트스트랩 중 인증 실패 → 즉시 stop, `bootstrap_state.json`에 마지막 cursor 보존, 다음 실행 시 재개
- 모든 KPI threshold 위반 → 경고만 띄우고 사용자 판단에 위임 (자동 차단 안 함)
