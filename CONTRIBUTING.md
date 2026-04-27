# Contributing to snowball-email

작은 스킬입니다. 거대한 프레임워크 만들 생각 없습니다. PR 환영.

## 원칙
1. **Compound 우선** — 기능 추가보다 reference 누적이 망가지지 않는지가 먼저.
2. **Persona 중립** — CS만 잘 되고 BD가 깨지면 머지 안 됩니다.
3. **승인 게이트 보존** — auto-send를 디폴트로 만드는 PR은 거절합니다.
4. **gws CLI 의존** — 다른 Gmail 라이브러리 도입 PR은 별도 이슈에서 합의 후.

## 개발 흐름
1. 이슈 먼저 (`bug_report` / `feature_request` 템플릿).
2. 브랜치 → 변경 → smoke:
   ```bash
   bin/snowball-email init --inbox devtest
   bin/snowball-email run --inbox devtest --dry-run --auto-approve
   bin/snowball-email view --inbox devtest
   bin/snowball-email metrics --inbox devtest
   ```
3. 영향 받는 문서(PLAN/README/SKILL/MANUAL) 업데이트.
4. PR — 템플릿 채우기.

## 디렉토리 구조
- `bin/snowball-email` — CLI 디스패처
- `assets/` — round 실행, 분류기
- `templates/personas/` — persona 시드 (5종)
- `templates/patterns/{cs,bd}/` — 패턴 시드
- `ingest/` — 4개 소스 ingestion
- `inboxes/` — 사용자별 런타임 (gitignore됨)

## 커밋 컨벤션
Conventional Commits. `feat:` `fix:` `docs:` `refactor:` `chore:`.

## 라이선스
MIT. 기여 시 동일 라이선스로 배포됨에 동의하는 것으로 간주.
