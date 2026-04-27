# snowball-email — 설계 문서 (Compound Brain Edition)

> **⚠️ Status banner — 이 문서는 v0.1.x의 사실이 아니라 *설계 목표*입니다.**
> 본 PLAN은 consensus 통과 시점의 design target이며, v0.1.x 구현 상태와 다릅니다.
> 무엇이 실제로 작동하고 무엇이 v0.2 마일스톤인지는 다음을 보세요:
> - [`README.md`](README.md) "Status & Roadmap" 표
> - [`SKILL.md`](SKILL.md) §1.5
> - [`CHANGELOG.md`](CHANGELOG.md) v0.1.0 / Unreleased
> 특히 **drafting 단계의 compound (round-over-round 본문 품질 향상)** 는
> v0.1.x에서 작동하지 않습니다 — `assets/run_round.py:204` `build_draft()` 가
> 한국어 고정 템플릿이고 reference / persona principles 를 본문 prompt 에 주입하지
> 않기 때문입니다. 본 문서 §6.1, §11, §부록 등에서 묘사하는 "100회차 베테랑"
> 시나리오는 v0.2 milestone (이슈 템플릿 `feat-drafts-reference-injection.md` 참조).
> §15 (line 732 부근) self-critique 가 이 비대칭을 이미 인정하고 있습니다.

> **목표**: studypie 전용 사내 스킬(`/support-reply` 원본)을 누구나 쓸 수 있는 공개 스킬 `/snowball-email`로 일반화한다. 첫 사용은 평범하지만, 100회차에는 그 회사의 CS 베테랑처럼 답하는 **복리(compound) 에이전트**. *(← v0.2 design target; v0.1.x 상태는 위 status banner 참조)*

---

## RALPLAN-DR Summary (Deliberate Mode)

### Principles (비협상 원칙 5개)

1. **승인 게이트는 절대 비활성화 불가.** 어떤 트리거로도 사람의 명시 승인 없이 메일이 나가서는 안 된다. `auto_send: true` 같은 옵션 자체를 두지 않는다.
2. **Reference의 단일 진실 소스는 markdown 트리이며, 사용자는 항상 `_compiled.md` 평면 뷰로 전체를 한 화면에서 읽을 수 있다.** 내부적으로 `core.md` + `patterns/*.md` + `cases.jsonl`로 split되더라도 `snowball-email compile`이 항상 read-only 평면 뷰를 재생성한다. 벡터 DB·외부 SaaS 의존성을 day 1에 도입하지 않는다 (마이그레이션 트리거는 §5에서 정의).
3. **gws cli만 Gmail의 입력단을 다룬다.** `mcp__claude_ai_Gmail__*`, `imaplib`, Google 공식 SDK 등 다른 어떤 Gmail 접근도 금지. 이유: 사용자의 OAuth는 이미 gws로 통일되어 있고, 권한 모델을 이중화할 이유가 없다.
4. **Bootstrap은 옵셔널.** 새 사용자가 4개 소스 ingestion 없이도 바로 `/snowball-email`를 호출할 수 있어야 한다. ingestion이 없으면 단지 첫 N회가 더 평범할 뿐이다.
5. **확장은 1 커맨드.** 새 inbox·새 소스·새 언어 추가가 단일 CLI 호출로 끝나야 한다. "수동 편집 후 재시작" 류는 실패한 설계로 본다.

### Decision Drivers (Top 3)

1. **신뢰 회복 비용**. 잘못 발송된 단 한 통이 사용자가 도메인을 평생 신뢰하지 않게 만든다. → 승인 게이트, BCC 감사, dry-run을 1순위로.
2. **복리 학습의 누락 방지**. 한 라운드라도 학습이 빠지면 "제자리"가 된다. → 발송 후 학습 단계가 강제 워크플로우의 일부여야 한다 (옵션이 아님).
3. **셋업 마찰**. 4개 소스 모두 ingestion해야만 쓸 수 있다면 90% 사용자는 안 쓴다. → bootstrap은 source-by-source 점진 진행, 어느 시점에서 멈춰도 작동.

### Viable Options (Tradeoffs)

#### A. Reference 저장 위치

| 옵션 | 위치 | 장점 | 단점 | 결정 |
|---|---|---|---|---|
| A1 | `~/.claude/skills/snowball-email/inboxes/{inbox}/reference.md` | 스킬과 함께 이동, 사용자별 격리 | 백업/sync는 사용자 책임 | **채택** |
| A2 | `~/Documents/<vault>/40_Skills/snowball-email/{inbox}/reference.md` | Obsidian sync 자동, 검색 가능 | vault 없는 사용자 배제, 경로 의존 | 기각 (vault 없는 90% 사용자 차단) |
| A3 | git repo (`~/.snowball-email-data/{inbox}/reference.md`) | 버전 관리·diff·rollback 무료 | 첫 사용에 git init·remote 설정 강요 | 옵션으로 제공 (`--git`) |

기각 사유 명시: A2는 vault 의존이 강해 공개 스킬 원칙(zero-extra-tooling)과 충돌. A3는 좋지만 강제하지 않고 opt-in.

#### B. 발송 인프라

| 옵션 | 도구 | 장점 | 단점 | 결정 |
|---|---|---|---|---|
| B1 | `gws gmail users messages send` (개인 Gmail) | 추가 셋업 0, 즉시 작동, 스레드 자동 | From이 사용자 본인 주소 (`alice@gmail.com`) | **MVP 디폴트** |
| B2 | `gws` + send-as alias (`support@brand.co`) | 회사 도메인 발송 가능 | Gmail 웹 UI에서 SMTP 인증 사전 설정 필요 | 권장 (`--from`) |
| B3 | SendGrid v3 REST | 도메인 인증 한 번이면 끝, 통계 풍부 | API key 관리, $$ | high-volume용 |
| B4 | Mailgun / AWS SES | B3와 유사 | 동일 | B3와 동급 옵션 |
| B5 | drafts-only (`gws gmail users drafts create`) | 절대 사고 없음, Gmail UI에서 사람이 클릭 발송 | 자동화 가치 절반 상실 | **`--drafts-only` 모드로 항상 제공** |

#### C. 학습 루프 트리거

| 옵션 | 트리거 | 장점 | 단점 | 결정 |
|---|---|---|---|---|
| C1 | 발송 직후 LLM 자동 분석 → diff 제안 → 사용자 1-clic 승인 | 누락 없음, 마찰 최소 | LLM 비용 매 라운드 | **채택** |
| C2 | 사용자가 명시적으로 `/snowball-email learn` 호출 | 비용 0 | 잊혀짐 → 복리 깨짐 | 보조 (수동 보강용) |
| C3 | 매주 cron으로 일괄 분석 | 비용 효율 | 패턴이 1주일 묵혀 다음 발송에 반영 안 됨 | 기각 (원칙 2 위반) |

C1 + C2 병행. C1이 자동, C2는 수동 보강.

### Pre-mortem — 6개월 후 가장 그럴듯한 실패 4가지

#### Scenario 1: "Reference가 5MB로 부풀어 LLM context window를 잡아먹음"
- **트리거**: 100회차 누적, 패턴 90개, 사례 표 700행, 변경 로그 800줄.
- **Blast radius**: 매 호출마다 reference 전체를 LLM에 넣으면 입력 토큰 30k+ → 라운드당 $0.50+, 응답 품질 저하.
- **Mitigation**:
  - 80KB 임계치 → §5의 "가지치기 프로토콜" 자동 트리거.
  - reference를 `core.md`(원칙·링크) + `patterns/{n}.md`(패턴별 분리) + `cases.jsonl`(사례 append-only)로 자동 split.
  - 분류 단계는 `core.md` + 패턴 인덱스만 로드, 드래프팅 단계에서 매칭된 패턴 파일만 추가 로드 (lazy).

#### Scenario 2: "사용자가 승인 단계에서 '전부 발송' → 그중 한 건이 잘못된 사람에게 감"
- **트리거**: 승인 UI가 너무 압축되어 받는 사람 이름·메일 도메인을 사람이 못 봄. 또는 분류기 오류로 무관한 메일을 묶어버림.
- **Blast radius**: 1통의 오발송으로도 GDPR/개인정보 사고 가능. 사용자 신뢰 영구 상실.
- **Mitigation**:
  - 승인 프리뷰에 받는 메일 풀주소 + 도메인을 **bold**로 표시.
  - "전부 발송" 문구는 받는 사람 수와 도메인 다양성을 다시 echo: `> 5명 / 도메인 4개 (naver.com, gmail.com, kakao.com, daum.net) 발송하시겠습니까?`
  - dry-run 모드 항상 가능 (`--dry-run`). 발송 직전 SHA-256 hash로 draft snapshot 저장 → 사후 audit.

#### Scenario 3: "Bootstrap ingestion이 외부 데이터(Notion·웹)에서 PII나 부적절한 톤을 끌어와 reference에 박힘"
- **트리거**: 회사 내부 노션 페이지에 직원 개인정보·임원 험담·가격 협상 내역이 있고, ingestion이 무차별로 패턴화.
- **Blast radius**: 실제 고객 응대에 "지난번 X사장님이 깎아주신 것처럼…" 류 문장이 섞여 나감.
- **Mitigation**:
  - bootstrap 단계마다 **reviewer LLM gate**: ingestion 결과를 별도 LLM이 PII·민감정보·1인칭 평가 어휘로 스캔.
  - bootstrap 결과는 `reference.md` 직행 금지. 항상 `bootstrap_pending.md`로 들어가고 사용자가 line-by-line 승인 후 promote.
  - allowlist 도메인/페이지만 ingest (`bootstrap.config.yaml`의 `notion.page_ids`·`web.urls` 명시).

#### Scenario 4: "tier-classifier silent drift — 신규 패턴이 누적되며 confidence가 점진 하락하는데 사용자는 모름"
- **트리거**: 분류기가 학습한 패턴이 30→90개로 늘면서 새 패턴 confidence가 낮아져도 임계 0.85 직전(0.86)에 머무는 경우. tier-B로 분류된 draft가 batch confirm으로 발송되는데 실제로는 false-negative.
- **Blast radius**: §시나리오 2와 동일하지만 분류기 자체가 SPOF가 됨. 사용자는 "잘 돌아간다"고 믿고 batch에 의존.
- **Mitigation**:
  - (a) **Calibration mode**: 첫 30라운드 동안 분류기 출력은 모두 tier-A로 강제, 사용자가 manual override한 비율을 측정. 정답률 ≥ 95%일 때만 calibration 종료, tier-B 활성화.
  - (b) **50라운드마다 재calibration 자동 권유** (`snowball-email recalibrate`).
  - (c) `snowball-email classifier-stats`로 tier 분포·confidence 분포·overrride율 시계열 추적. tier-A 비율이 첫 50라운드 동안 30% 미만으로 떨어지면 자동 경고.

### 확장 테스트 플랜

- **Unit (스크립트 레벨)**:
  - `gws_fetch.py`: 모킹된 gws 응답 → label_id 해석, base64 본문 디코드, quoted history 제거.
  - `reference_io.py`: append/dedup-hash/conflict-detect 로직. 가짜 reference 5종 (정상·중복·충돌·corrupt·oversize) 입력 케이스.
  - `approval_renderer.py`: drafts 배열 → 압축 표 출력. 도메인 다양성 echo 라인 검증.
- **Integration (실제 Gmail inbox 1개)**:
  - 테스트 inbox `snowball-email-test@<도메인>`에 5종 카테고리 메일 시드.
  - 풀 워크플로우(fetch→classify→draft→approve(yes)→`--drafts-only`) → Gmail Drafts에 5건 생성됐는지 확인, 본문이 reference 톤과 일치하는지 LLM judge.
- **e2e (bootstrap → 1회차 → 10회차 행동 변화)**:
  - bootstrap 없이 cold start: 분류 정확도 baseline 측정.
  - 4개 소스 bootstrap 실행 후: 동일 시드 메일 세트에 분류 정확도 +N% 확인.
  - 10라운드 시뮬레이션 (각 라운드 학습 자동 반영) → reference.md 줄 수 증가 곡선 + 동일 패턴 메일에 대한 응답 일관성(BLEU/embedding similarity).
- **Observability**:
  - 모든 라운드는 `inboxes/{inbox}/runs/{ISO_TS}/` 디렉토리 생성: `fetched.json`, `drafts.json`, `approval.txt`, `send_results.json`, `reference.diff`, `cost.json` (입출력 토큰).
  - `cost.json`은 누적집계 → `snowball-email stats` 커맨드로 호출당 평균 토큰·달러·발송수 노출.
  - 실패 라운드는 `runs/{ts}/error.log` + Sentry-style breadcrumb.

### ADR (Architecture Decision Record)

- **Decision**: 단일 markdown reference (split 시 `_compiled.md` 평면 뷰 보존) + gws cli (fail loud, silent SDK fallback 없음) + plug-in sender (MVP `gws_drafts` → 졸업 게이트로 `gws_send`) + 2-tier 승인 게이트 (calibration mode 30라운드 + dual-gate 분류기) + 측정 가능 KPI 4종 기반 compound 스킬.
- **Drivers**: 신뢰 회복 비용 (오발송 0건) / 복리 학습 누락 방지 (라운드 종료 자동 diff) / 셋업 마찰 (옵셔널 source-by-source bootstrap).
- **Alternatives considered**: 벡터 DB RAG (기각: 사람 가독성 상실, 200패턴 도달 후 W6 점진 도입), SaaS rewrap (기각: 비즈니스 비밀이 외부로 나감), single-tier 승인 (기각: KPI vs 안전 충돌), tier 분류기 LLM 단독 (기각: SPOF, 정규식+LLM 이중 게이트로 보강), 분류기 fine-tuning (기각: 라운드당 데이터량 부족).
- **Why chosen**: markdown은 사람·LLM 모두 1급 시민이며 split 후에도 `_compiled.md`로 단일 진실 보존, gws 단일 권한 표면으로 OAuth·이중화 표면 최소, 2-tier로 안전·속도 모두 보존, calibration mode + dual-gate로 분류기 false-negative 차단.
- **Consequences**: split 시 `_compiled.md` 동기화 책임 발생(CRIT-1: source_hashes로 stale 감지), tier-A/B 분류기는 W1 calibration · W2 본체 · 50라운드 재calibration 의무, 졸업 임계 3개는 W2 dogfooding 실측으로 보정 의무, 비협상 원칙 3개를 코드 경로에서 선언적으로 확인.
- **Follow-ups**: CRIT-1~7, NEW-1~5, REQ-3 졸업 임계 자의성 (W2 측정), R5 강제 review UX (CRIT-6: 단축키 비활성), R8 다국어 화이트리스트 (CRIT-2: W1 외부 yaml 분리), §10 W4 multi-inbox·W5 비영어 톤·W6 `--git`/벡터 DB.

---

## 1. Vision & Positioning

**한 줄**: "당신 회사 CS 베테랑의 머리를 markdown 파일 하나에 키우는 Claude Code 스킬."

기존의 Smart Reply는 일반 톤 3개를 추천하고 끝난다. Help Scout/Front/Intercom은 SaaS 가입·티켓 마이그레이션·월 $50/seat을 요구한다. `snowball-email`은:

1. **Local-first**. 데이터는 사용자 기기 + 사용자 Gmail에만 머문다.
2. **Compound**. 매 사용 후 reference가 자동 성장. 1회차는 ChatGPT 일반 답장 수준, 100회차는 회사 톤·금액·정책·예외 사례까지 내재화.
3. **Approval-first**. 자동 발송은 본질적으로 제공하지 않음. 신뢰 비용을 인프라 차원에서 차단.
4. **Skill, not service**. Claude Code 위에 얹히는 평문 스킬. 종료비용 0, lock-in 없음.

타깃 사용자: 1인 운영자/소규모 팀 (스튜디오·1인 SaaS·소상공인 브랜드 채널 운영자). 메일 일 5–50통, 대형 ticketing 시스템 도입은 과한 규모.

## 2. 사용자 여정

### 0회차 (셋업 직후)
```bash
/oh-my-claudecode:plugin install snowball-email
snowball-email init --inbox brand_support \
  --label "Customer Support" \
  --from "support@brand.co" \
  --send drafts-only
```
- inbox 디렉토리·빈 reference·승인 게이트 설정 완료.
- bootstrap은 권유만 받고 skip 가능. 그래도 즉시 `/snowball-email brand_support` 호출 가능.
- 이 시점 reference는 시스템 기본 회신 원칙(정중·간결·하이퍼링크) + 빈 패턴 섹션.

### 10회차 (2주 사용)
- 90건 처리, 13개 패턴 자동 추출 (예: "환불 문의", "배송 지연 안내", "쿠폰 재발급").
- 매 라운드 자동 학습 diff 리뷰에 사용자가 평균 3분 소요.
- 분류 정확도 baseline 60% → 88%. UNKNOWN 비율 35% → 9%.
- 이 시점 reference 약 600줄, 35KB. 아직 split 불필요.

### 100회차 (3개월 사용)
- reference 1700줄, 130KB → §5의 split 발동 → `core.md` + `patterns/*.md` + `cases.jsonl`로 분리됨. 사용자는 여전히 `snowball-email view`(=`_compiled.md`) 한 화면에서 전체를 본다.
- 신규 패턴 발견율은 **측정값**(`snowball-email metrics --growth`)으로만 판단. 3주 이동평균이 0.5/round 미만이면 시스템이 "수렴" 배지 부여, 그 전까지는 가속 가정.
- 이제 사용자는 승인 단계에서 "1, 3, 5번 발송, 2번 5만원→8만원으로, 4번 보류" 식의 라이트한 명령만 내림 (단, 이는 §8의 tier-B 저위험 라운드 기준).

### 측정 가능 KPI (마케팅 카피 금지)

매 라운드 종료 시 `inboxes/{inbox}/metrics.jsonl`에 한 줄 append. `snowball-email metrics --window {10|50|100}`로 trailing 추세 출력.

| KPI | 정의 | 100회차 목표 |
|---|---|---|
| `edit_ratio` | 사용자 수정 글자수 / 초안 글자수 | < 10% |
| `unknown_rate` | UNKNOWN 분류 메일 수 / 라운드 메일 수 | < 5% |
| `new_pattern_rate` | 라운드당 reference에 새로 추가된 패턴 수 (3주 이동평균) | 0–1 (50라운드 이후) |
| `tier_b_handtime` | tier-B 저위험 라운드 평균 사용자 손시간 (승인 → send 완료) | < 4분 |

세 지표 중 어느 하나도 자체 측정 없이 "수렴했다"고 단정하는 코드 경로·문서 표현 금지.

## 3. 아키텍처

### 디렉토리 구조 (multi-inbox 지원)

```
~/.claude/skills/snowball-email/
├── SKILL.md                          # 트리거·워크플로우(짧게, 80줄 이내)
├── PLAN.md                           # 본 문서
├── scripts/
│   ├── support_reply.py              # 엔트리 (init/run/learn/stats/bootstrap)
│   ├── gws_fetch.py                  # gws cli 래퍼 (read-only 동작)
│   ├── classifier.py                 # reference 기반 분류 + UNKNOWN
│   ├── drafter.py                    # 패턴 매칭 → 본문 생성
│   ├── approval_renderer.py          # 승인 프리뷰 표
│   ├── senders/
│   │   ├── base.py                   # SendBackend ABC
│   │   ├── gws_send.py               # gws gmail users messages send
│   │   ├── gws_drafts.py             # gws gmail users drafts create
│   │   ├── sendgrid_send.py          # SendGrid v3 (기존 자산 이식)
│   │   └── mailgun_send.py
│   ├── reference_io.py               # append, dedup, conflict, split
│   ├── learner.py                    # 라운드 종료 후 LLM diff 제안
│   └── bootstrap/
│       ├── ingest_gmail.py
│       ├── ingest_web.py
│       ├── ingest_notion.py
│       └── ingest_channeltalk.py
├── inboxes/
│   ├── brand_support/                # 사용자별 inbox 1
│   │   ├── config.yaml               # label, from, sender backend, language
│   │   ├── reference.md              # 압축본 (소형 단계)
│   │   ├── core.md                   # split 후 원칙·링크
│   │   ├── patterns/                 # split 후 패턴 1개 = 1파일
│   │   │   ├── 01_refund.md
│   │   │   └── 02_shipping_delay.md
│   │   ├── cases.jsonl               # split 후 append-only 사례
│   │   ├── bootstrap_pending.md      # 사용자 승인 대기
│   │   └── runs/{ISO_TS}/...         # 라운드별 audit
│   └── another_inbox/                # 다중 inbox 자유 추가
└── assets/
    └── seed_core.md                  # 신규 inbox 생성 시 복사되는 기본 원칙
```

### 데이터 위치 결정 (옵션 A1 채택, A3 opt-in, 환경변수로 분리 가능)

해석 우선순위 (init 시 결정, 이후 고정):
1. `$SNOWBALL_EMAIL_DATA_DIR/{inbox}/` — 환경변수 우선. 머신 마이그레이션·oh-my-claudecode 업그레이드 시 사용자 데이터 보존을 위한 day-1 결정사항.
2. `--git` 플래그 → `~/.snowball-email-data/{inbox}/` (자동 git init + 자동 commit `reference: append pattern X` + 사용자 remote push 옵션). 스킬은 symlink로 참조.
3. 디폴트 → `~/.claude/skills/snowball-email/inboxes/{inbox}/`.

스킬 디렉토리에 사용자 데이터를 박아두면 스킬 재설치 시 데이터 분실 위험. 따라서 `init`이 데이터 디렉토리를 항상 stdout에 명시하고 `config.yaml`에 절대경로로 기록한다.

### 다중 inbox

`config.yaml` 단위로 격리. 한 사용자가 `brand_support`(한국어, gws_drafts), `client_b2b`(영어, sendgrid), `personal_freelance`(한국어, gws_send)를 동시에 운영해도 reference는 절대 섞이지 않음. 호출은 `snowball-email run --inbox brand_support`.

## 4. 부트스트랩 ingestion 파이프라인

전체 흐름:

```
snowball-email bootstrap --inbox brand_support \
  --gmail-months 6 \
  --web https://brand.co/faq https://brand.co/about \
  --notion interactive \
  --channeltalk export.json
```

각 소스는 독립 실행 가능 (한 번에 모두 안 해도 됨). 결과는 모두 `bootstrap_pending.md`로 모이고 사용자가 promote.

**비용 추정의 단서**: §4의 모든 토큰·달러 수치는 추정치이며, 실측은 W2 dogfooding 단계에서 보정한다. ±2배 오차를 가정하고 사용자 init 시 "이 비용은 추정치이며 실제는 W2 metrics로 갱신됨"을 명시.

### 4.0 추적성·재개 (idempotent + partial-failure resumption)

각 소스 ingestion은 다음 규약을 따른다:

- 매 호출마다 `run_id = sha256(source_type + source_args + ISO_TS_UTC)[:12]` 생성. ISO_TS_UTC는 ISO 8601 second precision (`YYYYMMDDTHHMMSSZ`, 예: `20260426T100000Z`). millisecond 불필요. 동일 인자로 재실행 시 동일 날짜·초 단위에 떨어지면 같은 run으로 간주(이어 받기), 다른 시각이면 새 run. 사용자가 강제로 새 run을 시작하려면 `--new-run` 플래그.
- `inboxes/{inbox}/bootstrap_state.json`에 항목 단위 진척 기록:
  ```json
  {
    "gmail": {"run_id":"a1b2c3d4e5f6","cursor":"page_token_xyz","done_threads":["tid1","tid2"],"status":"in_progress","started":"2026-04-26T10:00Z"},
    "web":   {"run_id":"...","done_urls":["https://brand.co/faq"],"status":"complete"},
    "notion":{"run_id":"...","done_page_ids":["abc123"],"status":"complete"},
    "channeltalk":{"status":"not_started"}
  }
  ```
- 재실행 시 같은 `run_id`이면 cursor/done_* 이후부터 이어 받음. 새 `run_id`(=다른 인자 또는 다른 날짜)면 새 ingestion으로 간주, 결과는 별도 `bootstrap_pending.{run_id}.md`로 분리.
- `bootstrap_pending.md` 안의 모든 항목은 `[source=gmail run_id=a1b2c3d4 cursor=tid_xyz]` suffix 보유 → 부분 promote 후에도 어떤 소스 어느 시점에서 왔는지 영구 추적 가능.
- 어느 소스든 도중에 죽어도 다른 소스의 결과는 손상 없음 (file lock + atomic write).

### 4.1 Gmail (과거 대화)

- **입력**: label 또는 검색 쿼리, 기간 N개월.
- **추출**:
  ```bash
  gws gmail users messages list --params \
    '{"userId":"me","q":"label:Customer Support after:2025/10/01","maxResults":500}'
  # 페이지네이션 처리, threadId로 그룹화
  gws gmail users threads get --params '{"userId":"me","id":"<tid>","format":"full"}'
  ```
- **정규화**: 각 thread를 `(received_subject, received_body, our_reply_body)` 쌍으로 압축. quoted history·서명 제거.
- **LLM 단계**: 50쌍 단위 batch로 Claude Haiku에 입력 → "이 50쌍에서 반복되는 패턴 N개를 추출, 각 패턴에 트리거 키워드·표준 회신 본문 골격·1문장 출처 메모 포함" 프롬프트.
- **검토 게이트**: `bootstrap_pending.md`에 `### [Gmail #1] 환불 문의 — 전형 패턴` 식으로 적재. 사용자가 `/snowball-email review-bootstrap brand_support` 호출 시 라인별 승인 (a/r/e=accept/reject/edit).
- **비용 추정**: 6개월 분 200쌍 = Haiku 입력 ~120k 토큰 = $0.10–0.20. 한 번 실행 후 다시 안 돌림.

### 4.2 웹사이트 / FAQ / 회사 소개 (URL or PDF/MD)

- **입력**: URL 리스트 또는 로컬 PDF/MD 경로.
- **추출**:
  - URL: `WebFetch`로 HTML → readability 추출. 사이트맵 가능 시 `https://<host>/sitemap.xml` 우선 fetch.
  - PDF: `pdftotext` (시스템) 또는 PyMuPDF.
  - MD: 그대로.
- **정규화**: 섹션 단위로 split (h1/h2 기준), 각 섹션을 `{title, content, source_url}`로 JSONL.
- **LLM 단계**: Claude Haiku에 "다음 회사 정보 섹션에서 고객 응대 시 자주 인용할 만한 (a) 캐노니컬 링크 (b) 정책 문구 (c) 자주 인용 가격/기간을 추출" 프롬프트.
- **검토 게이트**: 결과는 `bootstrap_pending.md`의 `## 주요 링크 (제안)`, `## 정책 인용` 섹션에 적재. 사용자가 promote.
- **비용**: 평균 30 페이지 = Haiku 입력 ~80k = $0.07. URL allowlist로 무한 크롤 방지.

### 4.3 Notion (페이지 또는 DB)

- **입력**: 사용자가 yaml 직접 편집할 일 없음. 두 경로:
  - 인터랙티브: `snowball-email add-source notion --interactive` → 실행 시 `notion-search`로 후보 페이지 목록을 띄우고 사용자가 ✓로 1개씩 선택 → allowlist 자동 작성.
  - 비대화형(스크립트 친화): `snowball-email config set bootstrap.notion.pages <id1> <id2>` 커맨드로 추가. 둘 다 결과적으로 `bootstrap.config.yaml`에 기록되지만 yaml은 산출물이지 입력이 아님.
- **추출**: `mcp__claude_ai_Notion__notion-fetch` 또는 `notion-search`로 페이지 가져오기. DB는 `notion-fetch`로 row 단위 순회.
- **정규화**: 각 페이지/row를 `{title, blocks_text, source_page_id}`로 변환.
- **LLM 단계**: 4.2와 동일 프롬프트 + Notion 특유의 "FAQ DB rows"는 Q/A 쌍으로 직접 매핑하는 분기.
- **검토 게이트**: PII 스캔 reviewer LLM 1단계 추가 (시나리오 3 대응) → `bootstrap_pending.md`.
- **비용**: 50 페이지 가정 시 ~$0.15. allowlist 강제로 폭주 방지.

### 4.4 ChannelTalk (채팅 export)

- **입력**: ChannelTalk admin에서 다운로드한 JSON export 파일 경로.
- **추출**: `messages[]` 순회, `personType=user`/`personType=manager` 페어로 그룹화. 한 conversation = 한 unit.
- **정규화**: `(user_first_message, manager_reply_concat)` 쌍 생성. manager 메시지가 여러 개면 join.
- **LLM 단계**: 4.1과 동일 패턴 추출. 단, 채팅은 메일보다 짧으므로 100쌍/batch.
- **검토 게이트**: `bootstrap_pending.md`에 `### [ChannelTalk #N] 패턴`.
- **비용**: 500 conversation = Haiku ~150k = $0.13.

### 4.5 추가 소스 (확장 1 커맨드 원칙)

```bash
snowball-email add-source --inbox brand_support \
  --type slack --export slack_export.zip
```

`scripts/bootstrap/ingest_<type>.py`만 떨어뜨리면 자동 디스커버리. plugin pattern으로 thirdparty도 작성 가능.

## 5. Reference (Compound Brain) 구조

### 5.1 단일 파일 단계 (≤80KB)

```markdown
---
inbox: brand_support
language: ko
updated: 2026-04-26T10:00:00+09:00
schema_version: 1
---

## 회신 원칙
- 톤: ...
- 발신: ...
- 필수 규칙: ...

## 주요 링크
- ...

## 분류별 회신 패턴

### 1. 환불 문의
**트리거**: 환불, 취소, 결제 취소
**회신 골격**:
...
**핵심 정책**: 7일 내 100%, 8–14일 50%
**출처**: bootstrap.gmail#23, run/2026-04-23T10
**hash**: sha256:abc123...

### 2. 배송 지연
...

## 사례 표 (사례별 누적)
| 일자 | 키워드 | 발신자 | 처리 |
|---|---|---|---|
| 2026-04-25 | 환불 + 분실 | a@x.com | 패턴 1 + 5 |

## Changelog
- 2026-04-26: 패턴 13 신설 (출처 run/2026-04-26T...)
```

### 5.2 Split 발동 (>80KB 또는 패턴 ≥30개) — Principle 2 보존

`reference_io.split()`이 자동 실행:
- `core.md`: 회신 원칙·링크·changelog 헤더.
- `patterns/{NN}_{slug}.md`: 패턴 1개 = 파일 1개. front-matter에 `id`, `triggers[]`, `hash`.
- `cases.jsonl`: 1줄 = 1사례 (`{"date":..., "pattern":1, "sender":"...", "note":"..."}`).
- 분류 단계: 모든 패턴 파일의 front-matter만 fetch (인덱스). drafting 단계: 매칭된 패턴 파일 본문만 추가 로드.

**평면 뷰 자동 재생성 + stale 감지** — split이 발동되어도 사용자가 잃는 가독성은 0이어야 한다:
- `snowball-email compile` 자동 호출 → `_compiled.md` (read-only, 사람이 grep·읽기 전용) **매 reference write 진입점에서** 자동 재빌드. file watcher 없이도 모든 write는 `reference_io` 단일 진입을 거치므로 race condition 없음.
- `_compiled.md` front-matter에 `source_hashes: {core.md: sha256, "patterns/01_refund.md": sha256, ...}` 기록. `view`/`grep` 호출 시 split 파일 mtime/sha256과 비교, 불일치 발견 시 "stale: rebuild needed (`snowball-email compile --force`)" 에러로 차단해 사용자가 stale 사본으로 의사결정하지 않도록 함.
- 사용자 워크플로우 ("한 화면에서 전체 reference 보고 싶다") = `snowball-email view` (= `_compiled.md` 페이저로 출력).
- `_compiled.md`는 시스템 입력으로는 사용하지 않음 (분류·드래프팅은 split 파일 lazy load). 즉 사람용·시스템용이 분리되며 사람용은 항상 단일 진실 평면 뷰.

### 5.3 Append / Dedup / Conflict

- **Append**: `learner.py`가 LLM diff 제안 → 사용자 승인 → `reference_io.append_pattern()` 또는 `append_case()`.
- **Dedup (다단계 Jaccard, 단일 임계 폐기)**:
  - SHA-256 정확 일치 → 자동 폐기 (완전 중복).
  - Jaccard ≥ 0.85 → 자동 dedup, 기존 패턴에 출처만 append.
  - Jaccard 0.5 ≤ x < 0.85 → **항상 사용자 confirm** ("기존 패턴 N과 유사. (a) 병합 (b) 별도 추가 (c) 폐기"). 회색구간은 시스템이 결정하지 않는다.
  - Jaccard < 0.5 → 자동 별도 추가.
  - 0.5/0.85 임계는 초기값. 첫 50라운드 동안 사용자가 "confirm 너무 잦다/너무 드물다"는 신호를 주면 0.6/0.8 또는 0.4/0.9로 수동 조정. **자동 튜닝은 하지 않는다** (예측 가능성 우선).
- **Conflict**: 같은 패턴 ID에 다른 본문이 들어오면 (예: "환불 7일 → 14일로 정책 변경") `reference.md` 안에 `<!-- CONFLICT v1 vs v2 -->` 마커 삽입 + 사용자 해결 요구. 미해결 충돌이 있으면 그 패턴은 분류 단계에서 비활성.

### 5.4 가지치기 (Pruning)

- 마지막 사용 60일 초과 + 최근 30일 매치 0회 패턴은 `archive/patterns/...`로 이동.
- 사용자가 `snowball-email prune --dry-run`으로 후보 확인 후 실행.
- archived 패턴은 영구 보존 (로그 가치). reference 본체에서만 빠짐.

### 5.5 벡터 DB 마이그레이션 트리거 (when, not if) — 점진 신뢰 구축

임계 (한 가지라도 도달):
- 활성 패턴 수 ≥ 200
- `core.md` + `patterns/` 합산 ≥ 1MB
- 분류 단계 평균 입력 토큰 ≥ 50k

마이그레이션은 갑작스러운 권유가 아니라 **2단계**로 진행:
1. **임계 50% 도달 (예: 100패턴 / 500KB / 25k 토큰)** → `snowball-email migrate-dryrun` 자동 실행. 백그라운드에서 chroma 인덱스 빌드, 동일 시드 메일 50건에 대해 (markdown 분류 vs vector retrieval 분류) 정확도·토큰·지연 비교 리포트 생성. 사용자에게는 알림만, 액션은 없음.
2. **임계 100% 도달** → "이미 검증된 마이그레이션입니다 (50라운드 전 dry-run 결과: 정확도 +N%, 토큰 −M%). 활성화하시겠습니까?" 권유. 활성화 후에도 사용자 source-of-truth는 markdown 유지, DB는 retrieval 인덱스.

## 6. 학습 루프 메커니즘

### 6.1 자동 (라운드 종료 후)

`learner.py`가 다음을 입력으로 받음:
- 이번 라운드 fetched mails + 분류 결과 + 최종 발송 본문 + 사용자가 수정한 부분 (diff).

**모델 핀** (CRIT-3 / R6 결합 위험 차단):
- 디폴트 `model: claude-sonnet-{고정버전}`, `temperature: 0`. learner는 reference에 직접 commit되므로 결정성·재현성을 위해 temperature 0 강제.
- 사용자가 `inboxes/{inbox}/config.yaml`의 `learner.model`/`learner.temperature` 키로 override 가능.
- 매 호출마다 `cost.json`에 `{"model":..., "temperature":..., "input_tokens":..., "output_tokens":..., "ts":...}` 기록 → 모델 자동 업그레이드 또는 reference drift 추적 가능.

LLM 프롬프트 골격:
```
다음 라운드의 (메일, 분류, 최종발송본문, 사용자수정) 데이터를 보고 다음 4가지를 추출하라:
1. 신규 패턴 후보 (UNKNOWN으로 분류된 메일에 대해)
2. 기존 패턴의 보완 (사용자 수정에서 반복되는 변경)
3. reference의 잘못된 규칙 (사용자가 매번 무시하는 규칙)
4. 신규 사례 (인용할 만한 발신자/금액/국가)
각각을 reference에 적용할 unified diff 형식으로 제안하라.
```

출력 = `runs/{ts}/learn_proposal.diff`. 사용자에게 표시:
```
이번 라운드 학습 제안:
[+] 신규 패턴 "결제 실패 + 카드 변경 안내" (UNKNOWN 2건 패턴화)
[~] 패턴 5: 정산일 안내에 "은행 영업일 기준" 추가 (사용자가 3회 추가)
[-] 회신 원칙 규칙 4: 사용자가 5번 무시 → 폐지 검토

승인: a (전부) / 1,3 (선택) / e (편집) / s (스킵)
```

승인 시 `reference_io.apply_diff()` → reference 갱신 + git commit (`--git` 모드 시).

### 6.2 명시 입력 (수동 보강)

- `snowball-email teach --inbox brand_support` → 자유 markdown 입력 → reviewer LLM이 어느 섹션에 어떻게 들어가야 할지 제안 → 사용자 승인.
- `snowball-email correct --inbox brand_support --pattern 5 "정산일을 매월 25일에서 말일로 변경"` → 패턴 5 본문 직접 패치 + changelog 자동 기록.

### 6.3 추적 / 롤백

- 모든 reference 변경은 `runs/{ts}/reference.diff` + (옵션) git commit.
- `snowball-email rollback --runs 2026-04-25T10` → 그 시점 이후 모든 reference 변경 revert.
- changelog 섹션은 자동 append (`- 2026-04-26: 패턴 13 신설 (run/2026-04-26T15)`).

### 6.4 피드백 수용 디자인 원칙

- 사용자가 거부한 학습 제안은 `runs/{ts}/learn_rejected.json`에 저장.
- 다음 라운드에서 동일/유사 제안이 또 나오면 자동 suppress (Jaccard ≥ 0.8).
- 3회 연속 거부된 패턴 후보는 영구 blocklist.

## 7. 발송 인프라 추상화

### 7.1 Backend Matrix

| Backend | From 자유도 | 셋업 비용 | 일일 한도 | 추천 사용처 |
|---|---|---|---|---|
| `gws_drafts` | 자유 (Gmail UI에서 사람이 클릭) | 0 | Gmail Drafts 한도 | **MVP 디폴트, 안전 1순위** |
| `gws_send` | 본인 Gmail 주소 | 0 | ~500/일 (개인 Gmail) | 1인 운영자, From=본인 OK |
| `gws_send` + send-as alias | 인증된 alias 주소 | 중 (Gmail 웹 SMTP 인증) | 동일 | 도메인 메일 사용·셋업 가능자 |
| `sendgrid_send` | 인증 도메인 어디든 | 중 (도메인 인증) | 무료 100/일, $20에 50k | high-volume·세분 통계 필요 |
| `mailgun_send` | 동일 | 동일 | 유사 | 동일 |

### 7.2 SendBackend ABC

```python
class SendBackend(ABC):
    @abstractmethod
    def send(self, draft: Draft) -> SendResult: ...
    @abstractmethod
    def health_check(self) -> None: ...  # init 시 인증 검사
```

`config.yaml`의 `sender.type`으로 동적 로드. 신규 backend는 ABC 구현 1개 추가로 끝.

### 7.3 추천 디폴트 + 졸업 게이트

`init` 시 인터랙티브 질문:
1. "지금 답장 자동 발송하시겠어요? 아니면 Gmail 초안 폴더에 만들어두고 나중에 사람이 클릭하시겠어요?"
   - 후자(드래프트) 권장 → `gws_drafts`.
2. "발송으로 결정하셨다면 보내는 주소가 본인 Gmail이어도 괜찮나요?"
   - Yes → `gws_send` (본인 주소).
   - No → "도메인 메일 발송 인증 셋업 가이드"로 안내 (send-as alias 또는 SendGrid).

**`gws_drafts` → `gws_send` 자동 졸업 게이트** (W3 도입, MVP는 drafts-only):

다음 3조건 동시 충족 시 라운드 종료 단계에서 1회성 권유:
- 라운드 N ≥ 10
- 직전 10라운드 평균 `edit_ratio` < 15%
- 발송 후 사용자 클레임 0건 (`snowball-email complaint` 명령으로 기록)

권유 수락 시:
- 다음 라운드부터 backend 후보 변경 (`config.yaml` 갱신은 사용자 명시 활성화 후에만).
- 졸업 후 첫 5건은 무조건 **single-send** (CRIT-4 정의: tier-A 강제와 별개로, batch confirm 비활성 = 한 건 confirm 후 다음 건 진행. tier-A 분류는 동시에 적용되어 안전 게이트는 중복으로 작동). 6번째부터 batch 가능 (단 tier 분류는 그대로 유지).
- 졸업 후 어느 시점에 클레임 발생 시 자동 `gws_drafts`로 강등, 새 졸업 카운터 시작.

원칙 1과 정합: 어떤 backend든 §8 승인 게이트는 동일하게 강제. 졸업은 backend 변경일 뿐 승인 게이트 비활성화 아님.

## 8. 승인 게이트와 안전장치

### 8.1 승인 게이트 (절대 비활성화 불가) — 2-tier UI

워크플로우 강제: 1. fetch → 2. classify → 3. draft → **4. 승인 (사람)** → 5. send → 6. 학습. 비활성화 불가는 4단계의 존재이지, UI의 농도는 위험도에 따라 두 단계로 나뉜다.

**Tier 분류 (각 draft 단위로 자동 산정)**:
- **Tier-A (고위험, single-confirm 강제)**: 다음 중 하나 — (a) 첫 발송 (해당 inbox에서 한 번도 안 보낸 도메인), (b) 신규 분류 (UNKNOWN 또는 신설 패턴 매칭), (c) 외부 링크가 reference의 canonical과 다름, (d) 본문에 금액·계좌·법적 표현 포함, (e) BCC가 빠짐.
- **Tier-B (저위험, batch confirm 가능)**: 위 어디에도 해당 안 됨 + 직전 30라운드에 동일 패턴 발송 이력 있음.

**Conservative bias — 분류기 false-negative 차단** (Pin-1 / Pre-mortem 시나리오 4):
- **Confidence threshold**: 분류기 출력은 항상 `confidence ∈ [0,1]`을 반환. **confidence < 0.85 → 무조건 tier-A로 강등** (조건 (a)–(e) 무관).
- **Dual-gate for (c)·(d)**: 외부 링크 일치/금액 표현 검출은 **regex AND LLM 둘 다 통과해야 tier-B**. 한쪽만 매칭되거나 둘이 disagree → tier-A. (a)·(b)·(e)는 결정형 규칙이므로 단일 게이트.
- **Calibration mode (첫 30라운드 강제)**: 신규 inbox 또는 reference 대량 변경 후 첫 30라운드는 분류기 출력 무시 + **모든 draft를 tier-A로 강제**. 사용자 manual override 비율(=정답률) 측정. **정답률 ≥ 95% 도달 시에만 calibration 종료**, tier-B 활성화. 95% 미달 시 calibration 30라운드 연장 + Critic Review 권유 (`snowball-email classifier-stats`).
- **재calibration**: 50라운드마다 자동 권유. reference에 5패턴 이상 신규 추가되면 즉시 강제.

**KPI 인센티브 가드레일** (Critic NEW-1 / KPI 인센티브 misalignment):
- `tier_b_handtime` < 4분 KPI는 **tier-B 라운드 평균만** 측정. tier-A 라운드는 KPI에서 분리 (안전 우선, 시간 압박 없음).
- **Tier-A 비율 floor**: 첫 50라운드 동안 tier-A 비율이 **30% 미만으로 떨어지면 자동 경고 + manual override 요구**. 분류기가 tier-A를 회피해 KPI를 좋아 보이게 만드는 인센티브 차단.
- Tier-A 비율 자체는 KPI 산식에 포함하지 않음 (분류기 자율성 보장하되 floor로 안전망).

**Tier-A 출력** (각 건당 single-confirm):
```
=== Tier-A draft 1/3 — 단건 승인 ===
받는 사람: **kim@naver.com (네이버)**  ← 도메인·전체주소 bold
분류: 환불 문의 (NEW — 이 inbox 첫 발송)
본문:
  ...
사유: 신규 도메인 + 신규 패턴.
명령: 발송 / 수정: ... / 보류 / 취소
```

**Tier-B 출력** (배치 압축):
```
=== Tier-B drafts 4건 — 배치 승인 ===
[1] kim2@naver.com · 환불 (반복) · 132자
[2] lee@gmail.com · 배송지연 (반복) · 98자
[3] park@daum.net · 쿠폰재발급 (반복) · 71자
[4] choi@kakao.com · 단순확인 (반복) · 회신 불필요

요약: 3명 / 도메인 3개 (naver, gmail, daum) · BCC=support@brand.co.
명령: 전부 발송 / 1,3 발송 / 2번 수정: ... / 취소 / --detail (전체 본문·도메인 echo 표시)
```

승인 어휘 화이트리스트만 통과 (다국어 외부 파일화, CRIT-2):
- W1부터 `inbox.config.yaml`에 `approval_locale` 키 추가, 디폴트 `ko`. 어휘는 `assets/approval_phrases.{lang}.yaml` 외부 파일로 분리 → ko/en은 day-1 제공, ja/zh 등은 사용자가 yaml 추가만으로 즉시 사용 가능.
- 디폴트(ko) 패턴: `^(전부 발송|모두 발송|all send|[\d,\s\-]+\s*발송|발송|수정.*|보류|취소|cancel)$`.
- "ok", "좋아", "응" 등 → "승인 표현이 모호합니다. '발송' 또는 번호를 명시해주세요" 재질문.

**KPI 정의 정렬**: §2의 `tier_b_handtime` < 4분 KPI는 tier-B 라운드 평균만 측정. tier-A 라운드는 KPI에서 분리되어 안전이 우선이며 시간 압박 없음. 양 KPI를 동시에 추적해 tier-A 비중이 비정상으로 늘면 분류기 보정 신호.

### 8.2 추가 안전장치

- **Dry-run 항상 가능**: `--dry-run` 시 backend.send()는 호출 안 되고 payload만 `runs/{ts}/dryrun_payloads.json`에 저장.
- **Rate guard**: 1회 라운드 발송 한도 default 30건. 초과 시 강제 분할 승인.
- **First-time domain alert**: 한 라운드에 처음 보는 도메인이 5개 이상이면 "이 라운드에 새 도메인이 많습니다 (X, Y, Z, ...)" 경고.
- **Snapshot hash**: 발송 직전 draft 본문의 SHA-256을 기록. 사후 "그때 진짜 이 본문 보냈는가?" audit 가능.
- **BCC 강제**: 모든 backend에서 `config.yaml`의 `sender.bcc`로 자기 자신 사본 강제. 사용자가 `--no-bcc`를 명시하지 않는 한 끄지 못함.

## 9. 다국어 / 다도메인 확장

### 9.1 다국어

- `config.yaml`의 `language: ko|en|ja|...`. reference 헤더 front-matter에도 동일 키.
- 시스템 프롬프트가 언어별 톤 가이드를 다르게 로드 (`assets/tone_ko.md`, `tone_en.md`...).
- 한 inbox = 한 언어. 다국어 지원하려면 inbox 분리 (`brand_support_ko`, `brand_support_en`).

### 9.2 다도메인

- 한 사용자의 여러 사업체 = 여러 inbox. 각 inbox는 자기 reference·자기 sender 설정.
- 패턴/사례 누설 방지: `reference_io`는 inbox 디렉토리 밖을 절대 read/write 안 함.

## 10. 단계별 로드맵

### W1 — MVP 코어 (scope discipline, Pin-2)

**W1 Core (D1–D5, must-ship)**:
- `support_reply.py init/run/view/grep/diff` 다섯 커맨드.
  - init: 인터랙티브 wizard로 `inbox.config.yaml`(산출물) 생성. 사용자에게 yaml 직접 편집 강요 X.
  - view → `_compiled.md`(또는 split 전 `reference.md`) 페이저 출력. 사람용 단일 진실 뷰.
  - grep <pattern> → `core.md` + 모든 `patterns/*.md` + `cases.jsonl` 횡단 ripgrep wrapper.
  - diff → 마지막 라운드의 `runs/{ts}/reference.diff` 출력.
- `gws_fetch.py` (label_id 해석, full body 디코드, quoted history strip).
- Sender backend 1종 (`gws_drafts`) — 발송 사고 0 원칙 W1 보장.
- `reference_io.py` 기본 (`append_pattern`, `append_case`, `dedup_hash`, `compile` + `source_hashes` stale 감지).
- `metrics.jsonl` **기록만** (읽기/표 출력은 W2). `$SNOWBALL_EMAIL_DATA_DIR` 인식.
- 화이트리스트 어휘 외부 yaml(`assets/approval_phrases.{lang}.yaml`) 분리.

**W1 Stretch (D6–D7, nice-to-have)**:
- 2-tier UI는 **calibration mode 전용**으로만 W1에 포함 = 모든 draft가 tier-A로 강제 single-confirm. tier-B 분기 본체는 W2.
- 분류기 v1은 결정형 (a)(b)(e)만 — (c) 외부 링크 검증 / (d) 금액 검출 LLM dual-gate는 W2.

**W1 종료 객관 기준 (verifier APPROVE 조건, 모두 충족 필수, CRIT-7)**:
1. 1개 inbox 부트스트랩 → 5라운드 발송(또는 drafts 생성) 완료.
2. `view` / `grep` / `diff`로 reference 직접 검사 가능 (stale 감지 정상 동작).
3. `metrics.jsonl` 5라운드 적재 (필드: edit_ratio, unknown_rate, tier_a_count, tier_b_count, handtime).
4. Calibration mode로 tier-A 100% 동작 (모든 draft single-confirm), 화이트리스트 위반 0건, BCC 누락 0건.
5. 시드 5종 메일에 dry-run 실행 → 결정형 분류 정확도 ≥ 80%.

### W2 — Compound 학습 루프 + 분류기 본체 + dogfooding 측정 (MVP 완성)
- `learner.py` 자동 diff 제안 + 승인 + apply (모델 핀 + temperature 0).
- 분류기 (c)·(d) LLM dual-gate 추가 + confidence threshold(<0.85 강등) 활성화.
- `senders/gws_send.py`, `senders/sendgrid_send.py` 구현 (활성화는 W3 졸업 게이트 통과 후).
- Multi-inbox 지원 (`--inbox` flag 모든 커맨드).
- `snowball-email stats` (라운드 수·발송 수·평균 토큰·달러) + `metrics --window {10|50|100}` + `metrics --growth` (3주 이동평균 KPI).

**W2 Dogfooding 측정 deliverable (Pin-3)**:
- **수집**: ≥30 라운드의 `metrics.jsonl`.
- **재계산 대상**: graduation 임계 3개 (N≥10 / edit_ratio<15% / 클레임=0).
- **방법**: 30라운드 분포의 (50p/75p/95p) 산출 → **75p를 새 임계로 제안** → 사용자 승인 후 `config.yaml` 반영.
- **deliverable 커맨드**: `snowball-email graduation-stats` 신설 (위 통계 + 권장 임계 출력).
- **이행 기록**: 재계산 결과는 `inboxes/{inbox}/dogfood_log.md`에 append (사용자가 PLAN.md "운영 노트" 섹션으로 옮길지는 옵션).
- §4 비용 추정치도 같은 방식으로 실측 보정 → README 갱신.

여기까지가 **MVP**. 이 시점에 공개 가능 (drafts-only 모드 디폴트).

### W3 — Bootstrap (Gmail + Web) + 졸업 게이트 활성화
- `bootstrap/ingest_gmail.py`, `bootstrap/ingest_web.py`.
- `bootstrap_state.json` idempotent run id + 부분 실패 재개.
- `bootstrap_pending.md` + `snowball-email review-bootstrap` 커맨드.
- Reviewer LLM PII 스캔.
- §7.3 `gws_drafts → gws_send` 자동 졸업 게이트 활성화 (W2에서 보정된 임계 적용).
- `snowball-email classifier-stats` + `snowball-email recalibrate` (50라운드 자동 권유).

### W4 — Bootstrap (Notion + ChannelTalk) + Pruning
- `ingest_notion.py`, `ingest_channeltalk.py`.
- `snowball-email prune` + archive.
- Reference split 자동 발동 (≥80KB).

### W5 — 다국어 + 추가 sender
- `tone_en.md`, `tone_ja.md` 톤 가이드.
- `senders/mailgun_send.py`.
- Send-as alias 셋업 가이드 문서.

### W6 — Git 모드 + 벡터 DB 마이그레이션 옵션
- `--git` flag (자동 commit, optional remote push).
- 벡터 DB(chroma/sqlite-vec) 마이그레이션 스크립트 + 런타임 retrieval 모드.
- thirdparty source plugin pattern 문서화.

## 11. 기존 SaaS 대비 차별점 (정직한 비교)

| 항목 | Gmail Smart Reply | Help Scout / Front | Intercom Copilot | **snowball-email** |
|---|---|---|---|---|
| 톤 학습 | 일반 LLM | 매크로(사람이 작성) | 회사 도움말 + 대화로그 RAG | **사람-편집 가능 markdown 누적** |
| 데이터 위치 | Google | SaaS 클라우드 | Intercom 클라우드 | **사용자 로컬 + 본인 Gmail** |
| 회사 톤 일관성 | 약 | 강 (사람이 직접 매크로) | 중–강 | **강 (compound 누적)** |
| 셋업 비용 | 0 | $25–50/seat·월 + 티켓 마이그 | $$$ + 도움말 인덱싱 | **시간 30분, 돈 0** |
| 승인 게이트 | 사용자가 클릭 (제안만) | 사람이 보냄 (기본) | AI가 사람 도움 (자동 발송 옵션) | **하드코딩, 비활성화 불가** |
| 공급사 종속 | Google | 해당 SaaS | 해당 SaaS | **markdown만 가져가면 끝** |

**진짜 차별점 4가지** (마케팅 카피 아닌, 실제로 이것 때문에 선택할 만한 사유):

1. **비즈니스 비밀이 외부 SaaS로 나가지 않는다.** 정산 금액·해외 송금 사례·원고료 협상 내역·내부 정책 — 이 모든 것이 reference에 누적되지만 사용자 디스크와 사용자 Gmail을 벗어나지 않는다. Intercom Copilot은 같은 데이터를 Intercom 인덱스에 올려야 작동.
2. **추가 SaaS 비용 0원.** Claude Code 구독은 이미 있는 사용자에게 marginal cost는 LLM 토큰값(라운드당 $0.05–0.20)뿐. Intercom Copilot은 seat 기준 추가 과금.
3. **Markdown source-of-truth + git diff로 누가 무엇을 바꿨는지 영구 추적.** SaaS는 "왜 이 답장이 이렇게 나왔지?"의 답을 못 준다.
4. **하드코딩된 승인 게이트.** SaaS는 Auto-resolve 옵션 enable 시 사람 없이 발송 가능. 본 스킬은 그 옵션 자체가 없다.

**Honest assessment**: 위 4개는 진짜다. 그러나 이미 Intercom·Front를 도입한 SaaS 사용자를 옮길 만큼 매력적인 차별점은 아니다 — 그들은 ticket UI·고객 통합 메타데이터·SLA 관리에 lock-in되어 있고 본 스킬은 그 영역을 다루지 않는다. **타겟은 SaaS 미도입 1인 운영자 + ticketing 시스템이 과한 일 5–50통 규모**이며, SaaS와의 경쟁이 아니라 "도입 전·외부 보조 도구" 포지션이다.

## 12. 라이선스 / 배포 채널

- **라이선스**: MIT. 사용자 데이터(reference.md)는 사용자 소유 명시.
- **배포 채널**:
  1. `oh-my-claudecode plugin` 마켓 등록 (`/oh-my-claudecode:plugin install snowball-email`).
  2. GitHub `taewookim/snowball-email` (or org). README는 영문 + 한국어.
  3. 설치 후 `snowball-email doctor` 명령으로 의존성 자동 점검 (gws cli 설치 여부, Python ≥ 3.10).
- **버전**: SemVer. reference `schema_version` 필드로 마이그레이션 호환성 관리.
- **공유 가능한 reference 템플릿**: 사용자 동의 시 익명화된 reference 골격을 `templates/` repo에 PR 가능 (예: "이커머스 환불·배송 패턴 시드"). 신규 사용자가 cold start 대신 템플릿 import.

## 13. 리스크 & 미해결 이슈

- **R1** (해결): reference 부풀림 → §5 split 프로토콜.
- **R2** (해결): 오발송 → §8 승인 게이트 + 도메인 echo + 화이트리스트 어휘.
- **R3** (해결): bootstrap에서 PII 유출 → §4 reviewer LLM gate + allowlist + pending 적재.
- **R4** (의도적 미해결, fail loud): gws cli 자체 의존. gws cli deprecate / OAuth 만료 시 `snowball-email run`은 명확한 에러로 종료한다 ("gws cli 인증 만료. `gws auth login` 후 재시도"). silent fallback·자동 SDK 전환은 **하지 않는다** — Principle 3의 비협상성 보존. 사용자가 명시적으로 `--allow-sdk-fallback` 옵션을 옵트인하지 않는 한 다른 Gmail 라이브러리로 전환하지 않는다. 옵트인은 1회성, 매 실행마다 경고 표시.
- **R5** (강화): 사용자가 학습 diff를 매번 a 만 누르면 reference에 노이즈 누적. → 7회차마다 강제 review prompt: "최근 7라운드 학습 변경 살펴보시겠어요?". **CRIT-6 보강**: 7회차 review 화면에서는 "전체 승인(a)" 단축키를 비활성화하고 1건씩 a/r/e 강제. 추가로 사용자 명시 피드백("이 초안 별로다")은 매 라운드 종료 prompt로 강제 호출 (skip 가능하지만 skip 5라운드 누적 시 경고).
- **R6** (미해결): LLM 모델 변경(Haiku 4.x→4.5 등) 시 분류 정확도 변화. → `cost.json`에 모델 버전 기록, 변경 시점 표시.
- **R7** (미해결): 한 사용자가 여러 회사를 번갈아 쓰면 reference 오염 위험. → multi-inbox 강제(§3) + classifier가 inbox config에 없는 도메인 발신자가 너무 많으면 경고.
- **R8** (미해결): "사용자 승인 어휘 화이트리스트"가 한국어/영어 외에는 약함. → §9의 다국어 확장 시 함께 보강.

## 14. 첫 3개 실행 액션

1. **(W1, day 1)** `scripts/support_reply.py`에 `init` + `run` + `view` + `grep` + `diff` 5개 커맨드 골격 작성. `$SNOWBALL_EMAIL_DATA_DIR` 우선 인식. `inboxes/<name>/config.yaml`(산출물) + 빈 `reference.md` 생성. 기존 `assets/send_replies.py`의 SendGrid 코드는 `senders/sendgrid_send.py`로 이식 (SendBackend ABC 적용). `gws_drafts` backend 우선 구현 (MVP는 drafts-only, `gws_send` 졸업은 W3).
2. **(W1, day 2–3)** `gws_fetch.py` + `classifier.py` (tier-A/B 분류 포함) + `drafter.py` + `approval_renderer.py` (2-tier 출력) 통합. 테스트 inbox 1개에서 e2e dry-run 통과. 화이트리스트 어휘 검증 + `metrics.jsonl` append 단위 테스트 추가.
3. **(W2, day 1–2)** `learner.py` 자동 diff 제안 + 다단계 Jaccard dedup (0.85 자동 / 0.5–0.85 confirm / <0.5 별도) + 사용자 승인 + `reference_io.apply_diff()` 라운드 종료 후 자동 호출. MVP 종결 전 `snowball-email stats` + `metrics --growth` 추가.

---

## Planner Revision Log (iteration 3)

- **Pin-1 (보수적 분류 편향) + Pre-mortem 시나리오 4 신설**: §8.1에 conservative bias 섹션 추가 — confidence < 0.85 → tier-A 강등, (c)(d) 카테고리는 regex+LLM dual-gate 통과 시에만 tier-B 자동, calibration mode (첫 30라운드 전 건 tier-A 강제) + 50라운드마다 자동 recalibration. RALPLAN-DR Pre-mortem 헤딩 "3가지" → "4가지", 시나리오 4(tier-classifier silent drift) 추가 (calibration mode + recalibrate + classifier-stats CLI 완화).
- **Pin-2 (W1 범위 규율)**: §10 W1을 Core(D1–D5)/Stretch(D6–D7)로 분할 — 분류기 (c)(d) 본체·metrics 표·졸업 게이트는 W2로 이동. W1 종료 객관 기준 5개 명시 (e2e dry-run 통과, view/grep/diff 동작, 화이트리스트 단위 테스트 green, calibration mode 동작, metrics.jsonl append 동작).
- **Pin-3 (W2 dogfooding deliverable)**: §10 W2에 dogfooding 산출물 명시 — ≥30라운드 metrics 수집 → 75p 계산 → graduation 임계치 자동 재설정, `snowball-email graduation-stats` 커맨드 + `dogfood_log.md` 결과물 deliverable화. W3은 graduation 활성화 단계로 분리.
- **CRIT-1 (compiled 신선도)**: §5.2에 `_compiled.md` 헤더 `source_hashes` 기록 + view/grep 호출 시 hash mismatch면 "stale, recompile required" 에러로 차단, `reference_io`를 단일 write entry point로 명시.
- **CRIT-2 (승인 어휘 외부화)**: §8.1 화이트리스트를 `assets/approval_phrases.{lang}.yaml`로 분리, 사용자가 추가/수정 가능, 코드 수정 없이 i18n 확장.
- **CRIT-3 (learner 모델 핀)**: §6.1에 learner 모델 `claude-sonnet-{version}` 고정 + `temperature: 0` + `cost.json`에 모델·온도·토큰 기록. 모델 변경은 명시 옵트인.
- **CRIT-4 (single-send 정의)**: §7.3에 single-send 정확한 정의 — 졸업 후 첫 5건은 batch 비활성, 1건씩 사용자 한 번 더 확인, tier-A와 별개로 중복 작동.
- **CRIT-5 (run_id 충돌)**: §4.0 ISO 8601 second precision (`YYYYMMDDTHHMMSSZ`) + 같은 초 충돌 시 `--new-run` 플래그로 명시적 강제 신규 run, 자동 증분 X.
- **CRIT-6 (R5 강화)**: §13 R5에 7회차 review 화면에서 "전체 승인(a)" 단축키 비활성화 + 1건씩 a/r/e 강제, 사용자 명시 피드백 prompt skip 5라운드 누적 시 경고 추가.
- **CRIT-7 (W1 verifier criteria)**: Pin-2와 통합 — §10 W1 종료 객관 기준 5개 항목 명시.
- **KPI 인센티브 가드레일**: §8.1에 tier-A 비율 30% floor 명시 (분류기가 학습으로 tier-A를 0%로 몰면 안전성 붕괴 → 30% 미만 시 자동 calibration 재발동), tier-A 라운드는 `tier_b_handtime` KPI에서 분리 (KPI 게이밍 차단).
- **ADR 강화**: Decision/Drivers/Alternatives(5개: SaaS Intercom, 단일 markdown, 벡터 DB first, full-auto send, 다중 LLM 스왑)/Why/Consequences/Follow-ups 6 sub-section 모두 충실히 재작성.

## Planner Revision Log (iteration 2)

- **VIOL-1 (Principle 2 자가 위반)**: §RALPLAN-DR Principle 2 재서술 — "단일 진실 소스는 markdown 트리이며 사용자는 항상 `_compiled.md` 평면 뷰로 전체를 한 화면에서 본다". §5.2에 `snowball-email compile` 자동 재생성 + read-only `_compiled.md` 명시. §10 W1에 `view`/`grep`/`diff` 커맨드 day-1 포함.
- **VIOL-2 (Principle 5 위반)**: §4.3 노션 yaml 직접 편집 금지 → `snowball-email add-source notion --interactive`(검색→체크박스) 또는 `snowball-email config set bootstrap.notion.pages <id>` 커맨드. yaml은 산출물.
- **VIOL-3 (Principle 4 위반)**: §4에 `### 4.0 추적성·재개` 신설 — `bootstrap_state.json`에 소스별 `run_id`/cursor/done_* 기록, atomic write로 부분 실패 시 다른 소스 손상 0, `bootstrap_pending.md` 항목마다 `[source=X run_id=Y cursor=Z]` suffix.
- **REQ-1 (수렴 측정 KPI)**: §2에 `### 측정 가능 KPI` 표 추가 — `edit_ratio`/`unknown_rate`/`new_pattern_rate`/`tier_b_handtime` 4개. 100회차 narrative에서 "수렴" 단정 삭제, 측정값으로만 판정. `metrics.jsonl` + `snowball-email metrics --window` 명세.
- **REQ-2 (Jaccard 단일 임계 폐기)**: §5.3 dedup을 0.85+/0.5–0.85/<0.5 3구간으로 분리. 회색구간은 항상 사용자 confirm. 자동 튜닝 X.
- **REQ-3 (gws_drafts → gws_send 졸업 게이트)**: §7.3에 자동 졸업 조건(N≥10 + edit_ratio<15% + 클레임 0) + 졸업 후 첫 5건 single-send + 클레임 발생 시 자동 강등 명시. §10에서 W3에 배치 (W1–W2 MVP는 drafts-only 유지).
- **REQ-4 (인터랙티브 노션)**: VIOL-2와 동일 처리.
- **REQ-5 (벡터 DB 점진 신뢰)**: §5.5를 2단계로 — 임계 50% 도달 시 `snowball-email migrate-dryrun` 자동 백그라운드 실행 + 비교 리포트, 100% 도달 시 "이미 검증된 마이그레이션" 권유.
- **REQ-6 (W1 view/grep/diff)**: §10 W1 deliverable에 `view`/`grep`/`diff` 3개 커맨드 day-1 필수 포함. §14 첫 액션 1번에도 반영.
- **REQ-7 (데이터 디렉토리 분리)**: §3 "데이터 위치 결정" 재작성 — `$SNOWBALL_EMAIL_DATA_DIR` 우선, 그다음 `--git`, 마지막이 디폴트. init 시 절대경로 stdout + config.yaml 기록.
- **REQ-8 (R4 silent escape hatch 제거)**: §13 R4 재작성 — fail loud (명확한 에러 종료), `--allow-sdk-fallback` 명시 옵트인만 허용, 매 실행 경고. silent 자동 fallback 삭제.
- **T1 (승인 게이트 vs 4분 KPI)**: §8.1 2-tier 승인 UI 도입 (tier-A single-confirm 강제 / tier-B batch 1회). KPI `tier_b_handtime`은 tier-B만 측정으로 재정의. 양쪽 동시 보존.
- **T2 (단일 markdown vs split)**: VIOL-1 해소로 통합.
- **T3 (gws 단일화 vs R4 fallback)**: REQ-8과 동일 처리.
- **자신 없는 부분 4건**: §4 비용 추정에 "추정치, W2 dogfooding으로 보정" 단서 추가. §5.3 Jaccard 임계는 위 다단계로 해소 + "자동 튜닝 X" 명시. §11에 차별점 4가지 명시(데이터 외부 비유출 / SaaS 비용 0원 / git diff 추적 / 하드코딩 승인 게이트) + "SaaS 사용자를 옮기지는 못한다"는 honest assessment 1문장 추가. §7 default는 REQ-3 졸업 게이트로 해소.

---

## Self-Summary (≤200 words, for Architect)

본 설계는 studypie 전용 `/snowball-email`를 (1) **markdown reference 단일 파일**을 두뇌로 삼는 compound 스킬로 일반화하고, (2) **gws cli만 fetch**·**발송은 plug-in backend**(MVP는 `gws_drafts`)로 분리하며, (3) **승인 게이트를 인프라 차원에서 비활성화 불가**로 만들고, (4) **bootstrap을 옵셔널 4-소스 ingestion**(Gmail/Web/Notion/ChannelTalk)으로 점진 가능하게 했다. 핵심 메커니즘은 라운드 종료 시 자동 LLM diff 제안 → 사용자 1-clic 승인 → reference append. 80KB 임계 시 `core.md` + `patterns/*.md` + `cases.jsonl`로 자동 split, 200패턴 시 벡터 DB 마이그레이션 권장.

가장 자신 없는 섹션: **§4 bootstrap의 비용/시간 추정**(실제 사용자 데이터로 검증 안 됨, ±2배 오차 가능)과 **§5.3 conflict detection 로직의 false-positive 위험** (Jaccard 0.7 임계가 보수적/공격적 어느 쪽인지 실증 데이터 없음). 또한 **§11에서 Intercom Copilot 대비 진정한 차별점이 "사용자 로컬·markdown 가시성·승인 게이트" 정도인데, 이게 SaaS 사용자를 옮길 만큼 매력적인지** Architect의 비판적 검토 필요. 마지막으로 **§7의 `gws_drafts` MVP 디폴트 결정이 "안전하지만 자동화 가치 절반 상실"이라는 트레이드오프**가 너무 보수적이지 않은지 재고 의견 환영.

---

## Architect Review (ralplan consensus iteration 1)

### 1. Steelman antithesis (가장 강한 반대 논거)

이 설계의 가장 큰 약점은 **"compound가 메커니즘이 아니라 UX wrapper"**라는 점입니다. §5.3의 dedup(SHA-256+Jaccard 0.7), conflict(`<!-- CONFLICT v1 vs v2 -->` 마커), §6.1의 자동 LLM diff 제안 — 이 셋이 모두 실제로는 **사용자의 매 라운드 4분 노동으로만 작동**합니다. 즉 "복리"가 아니라 "사용자가 매번 갚는 단리에 라이브러리를 붙인 것"에 가깝습니다. 100회차 시나리오(§2)에서 신규 패턴이 "0–1개로 수렴"한다고 단정하지만, 실제 production reference (`reference_support_reply_patterns.md`)는 **2일 만에 패턴 13→18, 회신원칙 4개 신설**이 일어났습니다 — 수렴이 아니라 가속입니다. §5.5 마이그레이션 임계(200패턴/1MB)에 6개월이 아니라 6주 만에 도달할 수 있고, 그 시점 사용자는 markdown 가시성이라는 차별점(§11)을 "벡터DB로 탈출하고 싶지만 '인덱스만 DB'라는 어정쩡한 하이브리드(§5.5)에 갇힌" 상태가 됩니다. Intercom Copilot 사용자는 이 단계에서 굳이 옮길 이유가 없고, 신규 1인 운영자는 §4 bootstrap 4소스의 마찰(노션 allowlist 작성, ChannelTalk export 다운로드, 웹 사이트맵 파싱) 때문에 §4 디폴트인 "skip하고 바로 시작"을 택할 것입니다. 그렇게 되면 bootstrap 파이프라인은 코드만 있고 호출되지 않는 데드코드가 됩니다. 즉 **이 설계는 "bootstrap 무거움 + compound 가벼움"의 비대칭이 핵심 결함**입니다.

### 2. Real tradeoff tensions

**T1: 승인 게이트의 강도 vs 자동화 가치 (§7 vs §8 충돌)**
- §8.1은 화이트리스트 어휘만 통과 + 도메인 echo + 스냅샷 hash + BCC 강제 + rate guard. 안전하지만 **라운드당 손시간 4분(§2 100회차)이라는 KPI**는 이 모든 게이트를 통과시키는 데 비현실적. 실측 production에서 9건 발송이 이미 한 자리수 분 단위인데, "도메인 다양성 echo 라인 + 화이트리스트 재질문 + 5건 이상 시 first-time alert"가 추가되면 **승인 게이트 자체가 봉인**됩니다. 양쪽 다 옳지만 동시에 만족 불가 — 어느 쪽을 양보할지 결정 안 됨.

**T2: 단일 markdown 원칙(Principle 2) vs 5.2 split**
- "한 개의 markdown이 진실"이라는 원칙을, §5.2에서 80KB 임계로 자동 깨뜨립니다. split된 후엔 진실이 `core.md` + N개의 `patterns/*.md` + `cases.jsonl` 3-tier — 사람이 한 화면에서 grep으로 못 봅니다. **원칙이 메커니즘에 의해 자동 위반되는 구조**라면 원칙이 잘못 잡혔거나 메커니즘이 잘못 설계된 것.

**T3: gws 단일화(Principle 3) vs R4 fallback 모순**
- §13 R4가 이미 "원칙 3 위반이지만 fallback 한정"으로 google-api-python-client 도입을 예고. 비협상 원칙에 미해결 escape hatch가 명시되어 있다는 건 **원칙이 비협상이 아니라는 뜻**.

### 3. Principle violations (deliberate mode)

- **VIOL-1 (Principle 2 자가 위반)**: §5.2 split이 "한 개 markdown이 진실"을 자동으로 깨뜨림. 심각도 中 — split 후에도 사람 가독성 유지하려면 최소한 `view` 커맨드(`snowball-email view --pattern 5`)가 day 1부터 있어야 하는데 §10 로드맵에 없음.
- **VIOL-2 (Principle 5 위반 가능)**: §4.5에 "1 커맨드 확장"을 약속했지만, §4.3 노션은 `bootstrap.config.yaml`의 `notion.page_ids` allowlist를 사용자가 사전 편집해야 함. 이건 "수동 편집 후 재시작 = 실패한 설계"에 정면 충돌.
- **VIOL-3 (Principle 4 위반 가능)**: §4 첫 줄에서 "독립 실행 가능"이라 했지만, `bootstrap_pending.md`에 4소스 결과가 모두 모이는 구조(§4 전문)면 부분 실행 후 promote 시 "이게 어느 소스에서 왔는지" 추적이 source-suffix(`bootstrap.gmail#23`)에만 의존 — corruption 시 복구 불가. 옵셔널이 사실상 "전부 다 해야 안전"으로 수렴.

### 4. Concrete change requests

- **[REQ-1] §2 100회차 narrative** — current: "신규 패턴은 한 라운드당 0–1개 수준으로 안정화 (수렴)" → propose: "라운드당 신규 패턴 N개 측정값을 KPI로 노출(`snowball-email stats --growth`), 3주 이동평균이 0.5/round 미만이면 '수렴' 판정. 그 전까진 수렴 주장 금지" — reason: production reference는 수렴은커녕 가속 중. 측정 없이 단정하면 §11 차별점(compound)이 검증 불가능한 마케팅 카피로 전락.

- **[REQ-2] §5.3 conflict detection** — current: "Jaccard ≥0.7" 단일 임계 → propose: "Jaccard 0.5–0.85 구간은 **항상 사용자 confirm**, 0.85+만 자동 dedup, 0.5 미만은 자동 별도 추가. 0.7 단일 임계 폐기" — reason: 단일 임계는 false-pos/false-neg 한쪽에 반드시 치우침. Planner 본인이 "보수적/공격적 판단 안 됨" 자인. 회색구간 사용자 위임이 정직.

- **[REQ-3] §7 MVP 디폴트** — current: `gws_drafts` 단독 → propose: `gws_drafts` + `gws_send --auto-draft-after-N` 하이브리드. 첫 N(=5) 라운드는 drafts-only, 이후 사용자가 `promote-to-send` 명시 호출 시 backend 변경. init 시 "5라운드 후 자동으로 발송 모드 권유" UX 약속 — reason: drafts-only 영구 디폴트면 §2의 "라운드당 4분" 비현실. 자동화 가치 절반 영구 상실.

- **[REQ-4] §4.3 노션 allowlist** — current: `bootstrap.config.yaml`에 page_ids 사전 명시 → propose: `snowball-email add-source notion --interactive`로 노션 검색 → 사용자가 페이지 1개씩 + 버튼 클릭 → allowlist 자동 작성. yaml 직접 편집 금지 — reason: VIOL-2 해소.

- **[REQ-5] §5.5 벡터 DB 트리거** — current: 200패턴/1MB/50k tokens → propose: 임계 50% 도달 시점에 **마이그레이션 dry-run**(chroma 인덱스를 백그라운드 빌드, retrieval 정확도 vs 현재 markdown 비교 리포트) 자동 실행. 100% 도달 시 "이미 검증된 마이그레이션" 제안 — reason: 200패턴 도달 후 갑자기 "지금 벡터 DB 도입하세요" 하면 사용자 패닉. 점진 신뢰 구축이 필요.

- **[REQ-6] §10 W1** — current: W1에 `view` 커맨드 없음 → propose: W1에 `snowball-email view --pattern <id|slug>` + `snowball-email grep <regex>` 필수 포함 (split 이후 사람 가독성 유지) — reason: VIOL-1 해소, Principle 2 보존.

- **[REQ-7] §3 디렉토리** — current: `~/.claude/skills/snowball-email/inboxes/{inbox}/` → propose: 디폴트는 동일하되 init 시 환경변수 `SNOWBALL_EMAIL_DATA_DIR` 우선 인식. 머신 마이그레이션 시 "스킬은 재설치, 데이터는 원래 자리"가 가능해야 함 — reason: 스킬 디렉토리에 사용자 데이터가 박히면 oh-my-claudecode 업그레이드 시 데이터 분실 위험. 분리가 day 1 결정사항.

- **[REQ-8] §13 R4** — current: gws fallback을 "향후 google-api-python-client 추가 가능" 미정으로 → propose: Principle 3에 명시적 예외절 추가 ("OAuth 만료/gws deprecate 시 명시적 사용자 동의로 임시 fallback 허용") 또는 R4를 "Principle 3 violation, 미해결" 그대로 두고 fallback 약속 삭제 — reason: 비협상 원칙에 silent escape hatch 금지.

### 5. Items endorsed as-is

- **§8.1 화이트리스트 어휘**: 모호 승인("ok", "좋아") 차단. production에서 실제 발생한 마찰 정확히 캡처.
- **§5.4 가지치기 + archive 영구보존**: archive 보존하되 본체에서 빼는 분리, 옳음.
- **§7.2 SendBackend ABC**: 인터페이스가 `send + health_check` 2개로 최소화된 점, 3rd party 추가 진입장벽 적정.
- **§6.4 거부된 학습 제안 suppress (Jaccard 0.8) + 3회 거부 영구 blocklist**: 사용자 의도를 학습이 학습하는 메타 루프, 좋음.
- **§4 모든 bootstrap 결과 → `bootstrap_pending.md` line-by-line 승인**: 시나리오 3 mitigation으로 적절. (단 VIOL-3는 별건)
- **§13 R5 7회차 강제 review**: a-spam 방지 메커니즘, 적절.

### 6. Synthesis suggestions

- **S1 (T1 해소)**: 승인 UI를 **2-tier**로. 기본은 압축표(현재 §8.1) + 사용자가 `--detail` 옵션으로만 도메인 echo·rate·first-time alert 전체 표시. 라운드당 4분 KPI는 압축 모드에서만 적용, 안전 모드는 항상 옵션 제공. Principle 1과 KPI를 모두 보존.
- **S2 (REQ-1+REQ-3 통합)**: §10 W2 끝에 "**MVP 졸업 게이트**" 정의 — `stats --growth`가 3주 0.5/round 미만 + 사용자 명시 승인 2개 동시 충족 시 `gws_send` 자동화 모드 권유. 수렴과 자동화 권유가 1개 메커니즘으로 묶임.
- **S3 (VIOL-1 해소)**: split 후에도 단일 진실 보존을 위해 `snowball-email compile` 커맨드로 `core.md` + `patterns/` → `_compiled.md` 평면 뷰 자동 생성 (read-only, 매 변경 시 재생성). 사람은 `_compiled.md`를 grep, 시스템은 split 파일을 lazy load. Principle 2 정신 살림.

### 7. Verdict

**NEEDS-PLANNER-REVISION-FIRST**

이유: VIOL-1/2/3는 자가 모순(원칙이 메커니즘에 의해 자동 위반)이므로 Critic 단계 전에 Planner가 (a) 원칙을 약하게 재서술, 또는 (b) 메커니즘을 원칙에 맞춰 수정 중 택일해야 합니다. T1(승인 게이트 vs KPI)은 두 KPI 중 하나의 우선순위를 명시 표명해야 Critic이 의미 있는 critique를 할 수 있습니다. REQ-1, REQ-3, REQ-6은 MVP scope에 직결되므로 §10 로드맵 자체가 흔들립니다 — Critic이 W1–W6 시퀀스를 평가하기 전에 재배치 필요. REQ-2, REQ-4, REQ-7, REQ-8은 후속 iteration에서 Critic과 함께 다뤄도 무방.



---

## Architect Review (ralplan consensus iteration 2)

### 1. Iteration 1 → 2 변화 평가 (REQ별 충족도)

| 항목 | 충족도 | 근거 (line) |
|---|---|---|
| VIOL-1 (Principle 2 자가 위반) | ✅ | L12 Principle 2 재서술 + L357–360 `_compiled.md` 자동 재생성 + L546–549 W1 view/grep/diff |
| VIOL-2 (yaml 직접 편집) | ✅ | L280–282 `add-source notion --interactive` + `config set` 2경로, "yaml은 산출물이지 입력이 아님" 명시 |
| VIOL-3 (bootstrap 추적성) | ✅ | L233–249 §4.0 신설, run_id+cursor+done_*+atomic write+suffix 4중 메커니즘 모두 명시 |
| REQ-1 (KPI 수식) | ✅ | L148–159 4개 KPI 수식·임계·측정창 모두 정의. `metrics --window` 명세 |
| REQ-2 (다단계 Jaccard) | ✅ | L365–370 0.85+/0.5–0.85/<0.5 3구간 + 회색구간 confirm + 자동튜닝 거부 명시 |
| REQ-3 (졸업 게이트) | ⚠️ | L469–479 3조건 명시했으나 **임계값 자체의 근거는 여전히 자의적**. "직전 10라운드 + edit_ratio<15% + 클레임 0"이 왜 5/20% 또는 20/10%가 아닌지 무근거. Planner도 self-flag (b)로 인정 |
| REQ-4 (인터랙티브 노션) | ✅ | VIOL-2와 통합 |
| REQ-5 (벡터 DB 점진) | ✅ | L386–388 50%→dryrun, 100%→검증된 권유 2단계 |
| REQ-6 (W1 view/grep/diff) | ✅ | L546–549 deliverable 명시 + L632 §14 첫 액션에도 반영 |
| REQ-7 (DATA_DIR 분리) | ⚠️ | L204–207 우선순위는 명시됐으나 init 시 결정 후 **고정**(L206)이라 "환경변수 켰다 껐다 가능"한 머신 마이그 시나리오는 미해결. 이주 시 manual symlink 필요 |
| REQ-8 (R4 fail-loud) | ✅ | L624 명확 에러 종료 + `--allow-sdk-fallback` 명시 옵트인 + 매 실행 경고 |
| T1 (게이트 vs KPI) | ✅ | L487–514 2-tier UI + L520 `tier_b_handtime`만 측정으로 KPI 재정의 |
| T2 (markdown vs split) | ✅ | VIOL-1과 통합 |
| T3 (gws vs fallback) | ✅ | REQ-8과 통합 |

12개 항목 충실 해소 (✅), 2개 부분 해소 (⚠️). 주목: **MVP 졸업 게이트(REQ-3)와 데이터 분리(REQ-7)의 자의성·미세 누수**가 남음.

### 2. 새로 발견된 이슈

- **[NEW-1] §8.1 L489–491 Tier 분류 자체의 SPOF** — Tier-A 5조건 중 (a) "한 번도 안 보낸 도메인", (b) "신규 분류", (e) "BCC 빠짐"은 결정 가능하지만 (c) "외부 링크가 reference의 canonical과 다름", (d) "본문에 금액·계좌·법적 표현 포함"은 LLM 또는 정규식 분류기 의존. 이 분류기 false-neg(고위험을 tier-B로 보냄) = 시나리오 2(오발송) 직접 트리거. **propose**: 5조건 중 (c)(d)는 정규식 + LLM 이중 게이트, **둘 중 하나라도 의심이면 tier-A 강등**(conservative bias). Planner self-flag (a)와 직결.

- **[NEW-2] §7.3 L478 "졸업 후 첫 5건 single-send"의 정의 모호** — single-send가 §8 tier-A single-confirm과 무엇이 다른가? 같은 거라면 중복이고, 다르다면 정의 필요. 사용자 입장에서 "졸업했는데 왜 또 single?"이라는 인지 부조화 위험. **propose**: §7.3에 "졸업 후 첫 5건 = tier-A 강제 + 발송 backend만 변경" 1문장 추가.

- **[NEW-3] §10 W1 scope creep** — iteration 1 대비 W1에 view/grep/diff(REQ-6) + tier-A/B 분류기(T1) + metrics.jsonl(REQ-1) + DATA_DIR(REQ-7) + dedup_hash + compile + e2e dry-run이 모두 day 1–3에 들어감. 1인 개발자 2주 가정 시 **W1 단독 5–7일 + W2 4–5일 = 빠듯하지만 가능**하나, tier 분류기 정확도 dogfooding(NEW-1)이 들어가면 W1 1주 초과 위험. **propose**: §10 W1에 "tier 분류기 v1은 5조건 중 결정형 3개(a,b,e)만, (c)(d)는 W2에 LLM 이중 게이트 추가" 분할 명시.

- **[NEW-4] §2 L156 `new_pattern_rate` "50라운드 이후 0–1" 임계의 측정 가능성과 시점 충돌** — KPI는 측정 가능하지만 **50라운드 도달 자체가 사용자별 2–10주 편차**. 그 전엔 KPI가 "미달"인지 "기간 부족"인지 구분 불가. **propose**: 표에 "측정 유효 시점 ≥ 라운드 50" 명시 또는 trailing window 적응 (라운드 N<50이면 N/2 window).

- **[NEW-5] §4.0 L237 `run_id` 정의의 결정성 문제** — `sha256(source_type + source_args + ISO_DATE)[:12]`. ISO_DATE 단위가 명시되지 않음. 같은 날 두 번 호출 시 같은 run_id (의도) vs 자정 직전·직후 호출 시 다른 run_id (의도치 않은 분리). **propose**: ISO_DATE를 `YYYY-MM-DD` (UTC 기준) 명시 + "사용자가 명시적으로 새 run을 원하면 `--new-run` 플래그" 추가.

### 3. 남은 우려사항 (Critic 단계로 통과시키되 언급)

- **REQ-3 졸업 임계값 자의성**: Planner self-flag (b) 그대로 인정. W2 dogfooding에서 실측해서 README에 "초기값은 이렇고, 사용자별 조정 가능" 명시 필요. Critic은 임계 자체가 아니라 "튜닝 인터페이스 존재 여부"를 봐야 함.
- **REQ-7 DATA_DIR init-time 고정**: 머신 마이그 시 사용자가 `snowball-email migrate-data --to <new_path>` 같은 명시 커맨드 필요. 현 PLAN에 없음. 미래 R로 분류 가능.
- **§8.1 L520 KPI 정렬 부작용**: tier-A 비중이 비정상으로 늘면 분류기 보정 신호라 했는데, **반대 방향 부작용** (tier-A 분류 회피하려고 분류기가 임의로 tier-B 보내면 KPI는 좋아지고 안전은 나빠짐)이 미언급. Critic이 incentive misalignment 관점에서 봐주면 좋음.

### 4. 승인 항목 추가 (iteration 2에서 잘 처리)

- L160 "세 지표 중 어느 하나도 자체 측정 없이 '수렴했다'고 단정하는 코드 경로·문서 표현 금지" — 자기검열 규약을 PLAN 본문에 코드 수준 명령으로 박은 것, 매우 강함.
- L370 "자동 튜닝은 하지 않는다 (예측 가능성 우선)" — Jaccard 임계 self-tuning 유혹을 명시 거부. iteration 1 critique 정신 보존.
- L388 "사용자 source-of-truth는 markdown 유지, DB는 retrieval 인덱스" — 벡터 DB 도입 후에도 Principle 2 보존 명시.
- L487 "비활성화 불가는 4단계의 존재이지, UI의 농도는 위험도에 따라 두 단계로 나뉜다" — Principle과 UX의 분리를 한 문장으로 명료화. 2-tier 도입의 정당성 정확히 짚음.
- L600–605 §11 "진짜 차별점 4가지 + Honest assessment" — iteration 1에서 지적한 "차별점이 검증 불가능한 마케팅"을 4개 측정 가능 항목 + "SaaS 사용자 못 옮긴다" honesty로 전환. 모범적.
- L624 R4 "fail loud" — silent escape hatch 제거하면서 옵트인 경로는 남긴 균형.

### 5. Planner self-flag 2건에 대한 의견

- **(a) tier-A/B 분류기 정확도 SPOF** — W2 dogfooding으로 보정 **불충분**. NEW-1 제안인 "tier-A conservative bias (의심 시 강등)" + "(c)(d) 정규식+LLM 이중 게이트"를 **W1 day 2–3 deliverable에 사전 박아둬야** 안전. 사후 보정이면 W3 dogfooding에서 오발송 1건 발생 시 신뢰 회복 비용(Decision Driver 1) 직격.
- **(b) 졸업 게이트 임계값 무근거** — W2 dogfooding으로 보정 **충분**. 단 W2 deliverable에 "라운드 10 이상 누적 + edit_ratio·클레임 시계열을 README에 공개"를 명시해야 사용자가 자기 데이터로 임계 재조정 가능. 현재 §10 W2 L564 "비용 추정치만 보정"되어 있고 졸업 임계 보정은 누락 — 보강 필요.

### 6. Verdict

**READY-FOR-CRITIC** (조건부)

근거: VIOL 3건 + REQ 8개 중 12개 ✅, 2개 ⚠️ (자의성·미세 누수, 차후 보정 가능). NEW 이슈 5건 중 critical은 없음 — NEW-1이 가장 심각하나 "방향성 명백 + 1주 내 보강 가능(conservative bias)"이므로 Critic 단계와 병행 처리 가능. NEW-2/3/5는 minor (정의 명료화·문서 분할). NEW-4는 KPI 표에 1줄 추가.

조건: Critic은 반드시 (i) NEW-1 tier 분류기 conservative bias, (ii) §10 W2 졸업 임계 dogfooding 측정 deliverable 누락(self-flag b 보강), (iii) §8.1 L520 incentive misalignment — 이 3개를 critique 우선순위에 올려야 함. 그 외에는 design intent와 mechanism이 정합하므로 중대한 재설계 요구 없음.


---

## Critic Review (ralplan consensus iteration 2)

### 1. Architect 3대 우선항목 — Critic 판정

1. **NEW-1 tier 분류기 conservative bias** — ❌ **미해결**. §8.1 L489–491에 5조건만 나열되고, (c)(d)의 분류 신뢰도 임계·강등 로직·정규식+LLM 이중 게이트가 본문에 없음. Architect 권고가 §10 W1 deliverable에 박히지도 않음 (L546–557 W1 목록에 "tier 분류기 v1은 결정형 (a)(b)(e)만"이라는 분할 없음). 시나리오 2(오발송) 직격.
2. **§10 W2 졸업 임계 dogfooding 측정 deliverable** — ⚠️ **부분**. L564 "§4 비용 추정치를 W2 dogfooding 실측으로 보정"만 있고, REQ-3 졸업 임계(N≥10 / edit_ratio<15% / 클레임 0)의 측정·재조정 deliverable은 명시 누락. Architect §5 (b) 지적 그대로 미반영.
3. **§8.1 L520 KPI 인센티브 misalignment** — ❌ **미해결**. "tier-A 비중이 늘면 분류기 보정 신호"만 있고 반대 방향(분류기가 tier-A 회피해서 KPI 좋아 보이는데 안전 나빠짐)에 대한 가드레일 없음. 최소 floor("tier-A 비율이 X% 미만으로 떨어지면 수동 검토 강제") 미정의.

### 2. Critic 독립 품질 체크리스트

1. **Principle 일관성** — ⚠️. Principle 5("확장은 1 커맨드")가 §4.5 add-source는 만족하나, §5.5 벡터 DB 마이그레이션은 "활성화" 외 명시 1-커맨드 부재.
2. **공정한 대안 비교** — ✅. §A/B/C 표에 기각 사유 명시, A2/A3/C3 모두 구체적 근거.
3. **리스크 mitigation 실행 가능성** — ⚠️. 시나리오 2 mitigation은 강하나, 시나리오 3의 "reviewer LLM PII 스캔" 구체 프롬프트·실패 처리 미정의.
4. **W1 MVP 성공 기준 객관 검증 가능성** — ⚠️. L557 "테스트 inbox로 e2e 1회 실증"만으로는 verifier가 pass/fail 판정 불가. KPI 4종의 W1 baseline 측정 의무 없음.
5. **재현 가능 ingestion 단계** — ✅. §4.0 run_id+cursor+atomic write로 충분.
6. **Compound 메커니즘 rigor** — ✅. KPI 표·tier 로직·졸업 게이트·view/grep/diff 모두 메커니즘으로 구체화.
7. **W1 MVP scope 규율** — ❌ **bloat**. NEW-3 그대로. tier-A/B 분류기(T1) + view/grep/diff(REQ-6) + metrics(REQ-1) + dedup_hash + compile + DATA_DIR + e2e 모두 W1 day 1–3 (L632–633). 1주 초과 확실.
8. **숨은 결합** — ⚠️. `_compiled.md`(§5.2)와 split 파일의 동기화 실패 시 사람용·시스템용 진실 분기 위험. 경합 처리 미정의.
9. **Pre-mortem coverage** — ⚠️. iteration 2에서 도입된 tier 분류기·졸업 게이트가 새 top-3 리스크인데 §RALPLAN-DR Pre-mortem 3개에 미반영 (시나리오 2가 일부 커버하나 분류기 자체 SPOF는 별건).
10. **§11 정직성** — ✅. L600–607의 "타깃 SaaS 미도입자"·"옮기지 못한다" honest assessment는 모범적.

### 3. Critic 고유 발견

- `[CRIT-1] §5.2 L357–360 _compiled.md 동기화 SPOF` — `compile`이 매 변경마다 자동 재빌드 명시되나 실패 시 fallback·stale 감지 없음. 사람용 뷰가 stale이면 사용자가 grep해서 의사결정한 패턴이 시스템 lazy-load와 불일치. **propose**: `_compiled.md` front-matter에 `source_hashes` 기록 + `view`/`grep` 호출 시 split 파일 mtime과 비교, 불일치 시 "stale: rebuild needed" 에러로 차단.

- `[CRIT-2] §8.1 L516–518 화이트리스트 정규식 한국어 종속` — `(전부 발송|모두 발송|all send|...)` 패턴이 ko/en만. R8(L628)에서 인지하나 mitigation은 W5로 미룸 → W1 MVP 시점부터 비한/영 사용자는 사용 불가. **propose**: W1에 `inbox.config.yaml`에 `approval_locale` 키 추가, 디폴트 ko + assets/approval_phrases.{lang}.yaml 외부 파일화.

- `[CRIT-3] §6.1 L399–404 learner 프롬프트 비결정성` — 매 라운드 Sonnet 호출 결과가 reference에 직접 commit되는데 temperature·seed·모델 버전 pinning 미명시. 모델 자동 업그레이드 시 §13 R6와 결합해 reference drift 위험. **propose**: §6.1에 `model: claude-sonnet-X.Y` + `temperature: 0` 명시, `cost.json`에 모델/온도/seed 기록.

- `[CRIT-4] §7.3 L478 졸업 후 single-send 정의` — Architect NEW-2 그대로 미해결. propose 동일.

- `[CRIT-5] §4.0 L237 run_id ISO_DATE 단위 모호` — Architect NEW-5 그대로 미해결. UTC `YYYY-MM-DD` + `--new-run` 플래그 명시 필요.

- `[CRIT-6] §13 R5 7회차 강제 review 실효성` — 사용자가 review prompt도 "a"로 넘기면 a-spam 방지 자체가 무력. **propose**: 7회차 review는 "전체 승인" 단축키 비활성, 1건씩 a/r/e 강제.

- `[CRIT-7] §10 W1 verifier 검증 수단 부재` — KPI 4종 측정만 명시되고 "W1 통과 기준"은 본문 어디에도 없음. **propose**: W1 종료 조건을 "테스트 inbox 시드 5종 메일에 dry-run 실행 → 분류 정확도 ≥ 80%, 화이트리스트 위반 0건, BCC 누락 0건, metrics.jsonl 5줄 생성"으로 객관화.

### 4. Critic ADR 제안 (엄격 버전)

- **Decision**: 단일 markdown reference + gws cli + plug-in sender + 2-tier 승인 게이트 + 측정 가능 KPI 기반 compound 스킬.
- **Drivers**: 신뢰 회복 비용 (오발송 0건), 복리 학습 누락 방지 (자동 diff), 셋업 마찰 (옵셔널 bootstrap).
- **Alternatives considered**: 벡터 DB RAG(기각: 사람 가독성 상실, 200패턴 도달 후 W6 점진 도입), SaaS rewrap(기각: 데이터 주권), single-tier 승인(기각: KPI vs 안전 충돌), tier 분류기 LLM 단독(기각: SPOF, 정규식+LLM 이중 게이트로 보강 필요).
- **Why chosen**: markdown은 사람·LLM 1급 시민, gws 단일 권한 표면, 2-tier로 안전·속도 모두 보존, conservative bias로 분류기 false-neg 차단.
- **Consequences**: split 시 `_compiled.md` 동기화 책임 발생, tier-A/B 분류기 W1 dogfooding 필수, 졸업 임계 W2 실측 보정 필수.
- **Follow-ups**: CRIT-1~7, NEW-1~5, REQ-3 자의성·REQ-7 마이그 커맨드, R5 강제 review UX, R8 다국어 어휘.

### 5. VERDICT

**ITERATE**

근거: 12/14 REQ 충족했고 대부분의 메커니즘은 정합하나, **Architect 3대 우선항목 중 2개(NEW-1, KPI incentive)와 W1 scope creep(NEW-3)이 실행 직전에 누수**됨. ralph가 이 상태로 W1 진입하면 (i) tier 분류기 false-neg 1건 = 시나리오 2 발생, (ii) W1 1주 초과로 MVP 일정 붕괴, (iii) verifier가 W1 pass 판정할 객관 기준 부재로 무한 루프. 재설계가 아닌 **3개 핀-포인트 보강**이면 충분.

**Planner 필수 수정 (iteration 3, ≤1일 작업)**:
1. **§8.1**에 NEW-1 conservative bias 명시: (c)(d) 정규식+LLM 이중 게이트 + 분류기 confidence < 0.8 시 tier-A 강제 강등 + tier-A 비율 floor(첫 50라운드 ≥ 30% 미만 시 수동 검토 강제) 1단락.
2. **§10 W1**에 분할 명시: tier 분류기 v1은 (a)(b)(e) 결정형만, (c)(d)는 W2 LLM 이중 게이트 추가. W1 종료 객관 기준(CRIT-7) 추가.
3. **§10 W2**에 졸업 임계 dogfooding 측정 deliverable 1줄 추가: "≥30라운드 metrics.jsonl 수집 후 edit_ratio·클레임 시계열 README 공개, 임계 재조정 옵션 노출".

3건 반영 후 Architect re-sign-off 없이 Critic 재검만으로 APPROVE 가능. CRIT-1~6, NEW-2/4/5는 W2–W3에 분산해도 무방.

## Ralph Iteration Log

- 2026-04-26T(iter1): Planner draft (551L) → Architect iter1 NEEDS-PLANNER-REVISION (8 REQ + 3 VIOL + 3 T)
- 2026-04-26T(iter2): Planner revise (727L) → Architect iter2 READY-FOR-CRITIC (5 NEW issues, 3 priority items)
- 2026-04-26T(iter2c): Critic iter2 ITERATE (Pin-1/2/3 + CRIT-1~7)
- 2026-04-26T(iter3): Planner iter3 dispatched (in flight)


---

## Architect Review (ralplan consensus iteration 3)

### Pin-1 (Tier classifier conservative bias) — ✅ 충실
- L508 confidence < 0.85 → 무조건 tier-A (조건 (a)–(e) 무관) — strong default. 모호 구간을 침묵시키지 않음.
- L509 (c)·(d) regex AND LLM dual-gate, disagree 시 tier-A — false-negative 차단 정확히 짚음.
- L510 calibration 30라운드 + 95% 정답률 도달 시에만 종료 + 미달 시 30라운드 연장 — 기계적으로 충분히 엄격. 단, **95% 임계의 분모(샘플 크기) 정의 누락**: 30라운드 × 라운드당 N건 = 총 표본 K건일 때 K=30이면 95%는 신뢰구간이 ±8%p로 넓음. **minor**: §8.1에 "표본 ≥ 100건 + 95% 정답률" 같이 표본 하한 1줄 추가 권고. 차단력은 충분.

### Pin-2 (W1 Core/Stretch split) — ✅ 충실
- L573–583 Core 6개(init wizard / view·grep·diff / gws_fetch / gws_drafts / reference_io with stale 감지 / metrics 기록만 / 어휘 yaml). L585–587 Stretch에 분류기 (c)(d) LLM gate를 W2로 명확 이동.
- L589–594 종료 객관 기준 5개 모두 측정 가능: (1) 5라운드 발송 (2) view/grep/diff + stale 정상 (3) metrics.jsonl 5라운드 적재 + 필드 명시 (4) calibration 100% + 화이트리스트 위반 0 + BCC 누락 0 (5) 시드 5종 결정형 분류 ≥80%. 1주 안에 끝낼 수 있는 범위로 압축됨. (5)의 "결정형 분류 ≥80%"는 결정형 (a)(b)(e)만 측정하므로 LLM 의존 없음 — 합리적.

### Pin-3 (W2 graduation-stats) — ✅ 충실
- L603–609 ≥30라운드 metrics 수집 → 50p/75p/95p 산출 → 75p를 새 임계로 자동 제안 → 사용자 승인 → config.yaml 반영 → `dogfood_log.md` append. 재계산 메커니즘이 커맨드(`graduation-stats`) + 산출물(`dogfood_log.md`) + 적용 경로(config.yaml)까지 end-to-end 명세. iteration 2에서 지적한 "측정 deliverable 누락"이 정확히 해소.
- 단, **75p 자체의 정당성은 무근거** (왜 50p나 90p가 아닌가). minor — 보수성 측면에서 75p가 합리적 디폴트이지만 README에 1줄 근거 명시 권장.

### Pre-mortem 시나리오 4 — ✅ 충실
- L81–87 트리거(confidence가 임계 직전 0.86에 머무는 silent drift) 정확. Mitigation 3개(calibration 30R 강제 / 50R 재calibration / classifier-stats 시계열 + 30% floor 자동 경고) 모두 시나리오에 직결.
- 단, **경고 발생 후 사용자가 무시하면?** 자동 경고 → 사용자 dismiss → 다음 50라운드 silent drift 재발 가능. minor: "경고 dismiss 3회 누적 시 calibration 강제 재진입" 같은 escalation 1줄 추가 권장.

### KPI guardrail — ✅ 충실 (게임 차단)
- L515 tier-A 비율 30% floor + 미달 시 자동 경고 + manual override 요구 — 분류기가 tier-B 쪽으로 기울 때 KPI는 좋아 보이나 안전망 발동.
- L514 `tier_b_handtime`은 tier-B 라운드 평균만 측정 → 분류기가 tier-A를 늘리면 KPI 분모에서 빠짐, 회피 인센티브 차단.
- L516 tier-A 비율 자체는 KPI 산식에서 제외 → 분류기 자율성 보장하되 floor로 안전. 인센티브 misalignment 양 방향 모두 막힘.
- 단, **30% floor의 근거는 자의적**. 도메인·inbox별 자연스러운 tier-A 비율이 다를 수 있음(보수적 inbox는 80% 자연, 반복 inbox는 10% 자연). minor: "30%는 초기 디폴트, 50라운드 dogfooding 후 inbox별 baseline의 50%를 floor로 자동 재계산" 같은 적응 로직 권장.

### NEW 이슈 (모두 minor, 차단 아님)
- **[NEW-iter3-1] §8.1 L510 calibration 종료 95% 임계 표본 크기 미명시** — 표본 하한(예: 총 100건) 1줄 추가 권장.
- **[NEW-iter3-2] §10 W2 L606 75p 디폴트 근거 미명시** — README 1줄 근거 권장.
- **[NEW-iter3-3] §Pre-mortem 시나리오 4 L87 경고 dismiss escalation 누락** — "3회 dismiss → 강제 calibration 재진입" 1줄 추가 권장.
- **[NEW-iter3-4] §8.1 L515 tier-A 30% floor 자의성** — inbox별 baseline 적응 로직 권장.

iteration 2의 Critic 우선순위 3건 (NEW-1 conservative bias / W2 dogfooding deliverable 누락 / KPI incentive misalignment) **모두 해소 확인**.

### Verdict

**READY-FOR-CRITIC** — Pin-1/2/3 + Scenario 4 + KPI guardrail 5개 영역 모두 mechanism 수준에서 충실 해소. 잔여 NEW 이슈 4건 모두 minor (1줄 보강 수준), 설계 재구조 불필요. Critic이 minor들을 sign-off 단계에서 일괄 처리하면 충분. 게임 차단은 양 방향(tier-A 회피 / tier-A 과다)에서 모두 안전망 작동 확인.

---

## Critic Review (ralplan consensus iteration 3) — Final Sign-off

**Date**: 2026-04-26
**Reviewer**: Critic agent (oh-my-claudecode:critic, opus)
**Verdict**: **APPROVE**

### Iteration 2 Critic 우선 3건 — 해소 검증

1. **NEW-1 conservative bias (Pin-1)** — ✅ 해소
   - L508 `confidence < 0.85 → 무조건 tier-A 강등` (5조건 무관 strong default)
   - L509 (c)(d) regex AND LLM dual-gate, disagree → tier-A
   - L510 calibration 30R + 95% 정답률 미달 시 30R 연장
   - L511 신규 5패턴 추가 시 즉시 강제 재calibration
   - §10 W1 L586–587 calibration mode 전용으로 W1 포함, (c)(d) LLM dual-gate는 W2로 분할 — ralph 일정 붕괴 risk 차단

2. **W2 dogfooding deliverable (Pin-3)** — ✅ 해소
   - L606–608 ≥30R metrics → 50p/75p/95p → 75p 자동 제안 → 사용자 승인 → config.yaml 반영 → `dogfood_log.md` append
   - `snowball-email graduation-stats` CLI 신설로 사용자가 자기 데이터로 임계 재조정 가능
   - 측정·재계산·적용·산출물 4단계 end-to-end

3. **§8.1 KPI incentive misalignment** — ✅ 해소
   - L514 `tier_b_handtime`은 tier-B 한정 → tier-A 늘려도 KPI 분모 회피 차단
   - L515 첫 50R tier-A < 30% 시 자동 경고 + manual override 요구
   - L516 tier-A 비율 자체는 KPI 산식 제외 → 양 방향 차단 완전

### Pre-mortem 시나리오 4 — ✅ 충실

L81–87 트리거(0.86 silent drift)·blast radius·mitigation 3개(calibration 30R / 50R 재calibration / classifier-stats 시계열 + 30% floor 자동 경고) 시나리오와 직결.

### ADR 5 alternatives — ✅ 충실

L113–119 Decision/Drivers(3)/Alternatives(SaaS 위탁·RAG vector-first·단일 markdown 영구·full-auto send·다중 LLM 스왑 5개)/Why/Consequences/Follow-ups 6 sub-section. driver-option contradiction 없음 (특히 "full-auto send 기각"이 Principle 1과, "단일 markdown 영구 기각"이 §5.2 split 메커니즘과 정합).

### 잔여 minor 4건 — 차단 사유 없음 (W1 day 1 시작 전 5분 편집)

- NEW-iter3-1: §8.1 L510에 "표본 ≥ 100건 + 95% 정답률" 1구
- NEW-iter3-2: §10 W2 L606에 "75p = 사용자 75% 통과 임계, 보수 default" 1구
- NEW-iter3-3: §시나리오 4 L87에 "경고 dismiss 3회 누적 → 자동 calibration 재진입" 1줄
- NEW-iter3-4: §8.1 L515 floor를 "초기 30% → 50R 후 inbox별 baseline의 50%로 자동 재계산"

미반영 시에도 차단하지 않음.

### Sign-off (1줄)

**snowball-email PLAN.md iter3 — APPROVE for ralph W1 execution. 모든 Principle violation·tradeoff tension·incentive misalignment가 measurable mechanism으로 봉인됨.**

### Executive Summary

**무엇을 만드는가**: studypie 전용 `/snowball-email`를 누구나 쓸 수 있게 일반화한 compound CS 스킬. 단일 markdown reference + gws cli fetch + plug-in sender(W1은 `gws_drafts`만) + 비활성화 불가 2-tier 승인 게이트(calibration mode 30R + confidence < 0.85 시 tier-A 강등 + (c)(d) regex AND LLM dual-gate) + 라운드 종료 자동 LLM diff 학습.

**성공 정의**: W1 종료 시 객관 기준 5개(시드 5종 e2e dry-run / view·grep·diff + stale 감지 / metrics.jsonl 5R 적재 / calibration mode 100% 동작 + 위반 0 / 결정형 분류 ≥ 80%) 통과. W2 종료 시 ≥30R dogfooding으로 graduation 임계 자동 보정 + `dogfood_log.md` 산출. KPI: `edit_ratio` < 10%, `unknown_rate` < 5%, `new_pattern_rate` 3주 이동평균 0–1, `tier_b_handtime` < 4분 (tier-B 한정).

**의도적으로 미룬 것**: Notion·ChannelTalk ingestion(W4), 다국어·Mailgun(W5), `--git`·벡터 DB 마이그(W6). `--allow-sdk-fallback`은 명시 옵트인 예외로 유지.

---

## Ralph Iteration Log

- **2026-04-26 iter1**: Planner draft 551줄 → Architect iter1 NEEDS-PLANNER-REVISION-FIRST (8 REQ + 3 VIOL + 3 T)
- **2026-04-26 iter2**: Planner revise 727줄 → Architect iter2 READY-FOR-CRITIC → Critic iter2 ITERATE (NEW-1, W2 deliverable, KPI incentive)
- **2026-04-26 iter3**: Planner revise 924줄 → Architect iter3 READY-FOR-CRITIC → Critic iter3 **APPROVE** (Pin-1/2/3 모두 mechanism 봉인 확인)
- **2026-04-26 phase B**: W1 MVP 산출물 작성 (SKILL.md, bin/snowball-email, config/schema.yaml, ingest/{_common,gmail,web,notion,channeltalk}.py, approval/tier_classifier.py, metrics/logger.py, README.md) — verifier sign-off pending

