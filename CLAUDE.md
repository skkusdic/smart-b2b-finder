# Smart B2B Finder for Startups

> 모든 응답과 설명은 한국어로.
> 코드 변수명·함수명은 영어 snake_case. UI 텍스트는 한국어.

## 프로젝트 목적
DART 공시 재무 데이터 + Claude RAG 분석 + MILP 최적화를 결합하여
B2B 스타트업의 영업 타깃 우선순위를 자동 도출하는 Multi-Agent 시스템

## 4주 타임라인
| 주차 | 기간 | 목표 |
|------|------|------|
| 1주차 | 05/21 ~ 05/27 | DART 데이터 수집 + SQLite DB + 1차 필터링 |
| 2주차 | 05/28 ~ 06/03 | Claude RAG 분석 파이프라인 + 스코어링 |
| 3주차 | 06/18 ~ 06/24 | MILP 최적화 알고리즘 구현 |
| 4주차 | 06/25 ~ 07/01 | Streamlit UI + 배포 |

## 서비스 흐름 (아키텍처)
```
사용자 입력 (app.py)
  → 1차 룰베이스 필터링 (pipeline/filter.py)    ← 1주차
    → 2차 Claude RAG 분석 (agents/analyzer.py)  ← 2주차
      → 3차 MILP 최적화 (optimizer/milp.py)     ← 3주차
        → 결과 출력 (app.py)                    ← 4주차
```

## 기술 스택
- Frontend: Streamlit
- Backend: Python, DART API, Anthropic API
- DB: SQLite
- 최적화: PuLP (MILP)

## 환경 변수 (.env 파일에만, 절대 코드에 직접 X)
- DART_API_KEY — https://opendart.fss.or.kr
- ANTHROPIC_API_KEY — https://console.anthropic.com

## 절대 규칙
- .env는 절대 GitHub 커밋 금지
- API 키 코드 하드코딩 금지
- Claude API 호출 시 모델: claude-haiku-4-5
