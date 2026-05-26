# Smart B2B Finder for Startups — 1주차 실행 가이드

**프로젝트명:** Smart B2B Finder for Startups  
**작성자:** 이정원  
**기준 일정:** 05/21 ~ 05/27 (1주차)  
**마일스톤:** 토픽 lock + 새 repo 생성 + CLAUDE.md 작성 + DART API 연동 + DB 적재

---

## 목차

1. [1주차 목표 정의](#1-1주차-목표-정의)
2. [프로젝트 폴더 구조](#2-프로젝트-폴더-구조)
3. [환경 설정](#3-환경-설정)
4. [파일별 코드 구현](#4-파일별-코드-구현)
   - [pipeline/db.py — SQLite 스키마](#41-pipelinedbpy--sqlite-스키마)
   - [pipeline/dart_collector.py — DART 수집](#42-pipelinedart_collectorpy--dart-수집)
   - [pipeline/filter.py — 1차 필터링](#43-pipelinefilterpy--1차-필터링)
   - [CLAUDE.md — 프로젝트 문서](#44-claudemd--프로젝트-문서)
5. [실행 순서](#5-실행-순서)
6. [1주차 체크리스트](#6-1주차-체크리스트)
7. [팀 프로젝트 대비 달라지는 점](#7-팀-프로젝트-대비-달라지는-점)
8. [주의사항 및 트러블슈팅](#8-주의사항-및-트러블슈팅)

---

## 1. 1주차 목표 정의

| 목표 | 설명 |
|------|------|
| **새 repo 생성** | GitHub에 `smart-b2b-finder` repo 생성 후 로컬 clone |
| **CLAUDE.md 작성** | 마일스톤 1에 명시된 필수 파일 — 프로젝트 아키텍처와 규칙 문서화 |
| **DART API 연동** | 코스피/코스닥 전체 상장사(~2500개) 재무 데이터 배치 수집 |
| **SQLite DB 적재** | 수집한 데이터를 로컬 DB에 저장 (실시간 API 호출 의존 제거) |
| **1차 룰베이스 필터링** | 최소 거래 규모 500만 원 이하 기업 등 조건 기반으로 사전 제외 |

### 왜 1주차에 DB 캐싱이 중요한가

2주차부터 Claude API로 사업보고서를 분석하는데, 2500개 기업 전부를 Claude에 넣으면:
- API 비용이 폭발적으로 증가
- 처리 시간이 몇 시간 걸림

**해결책:** 1주차에 재무 수치 기반 룰베이스 필터로 2500개 → 30~50개로 압축한 뒤, 그 소수 기업만 Claude에게 전달.

---

## 2. 프로젝트 폴더 구조

```
smart-b2b-finder/
│
├── .env                        ← API 키 저장 (절대 GitHub에 올리면 안 됨)
├── .gitignore                  ← .env, __pycache__, *.db 등 제외
├── CLAUDE.md                   ← 마일스톤 1 필수 파일
├── requirements.txt
│
├── pipeline/                   ← 1주차 핵심 구현 영역
│   ├── __init__.py
│   ├── db.py                   ← SQLite 스키마 정의 및 연결 관리
│   ├── dart_collector.py       ← DART API 호출 + 데이터 저장
│   └── filter.py               ← 1차 룰베이스 필터링 로직
│
├── agents/                     ← 2주차부터 구현
│   ├── __init__.py
│   ├── analyzer.py             ← Claude API RAG 분석 에이전트
│   └── scorer.py               ← 수주 확률 / 기대가치 스코어링
│
├── optimizer/                  ← 3주차부터 구현
│   ├── __init__.py
│   └── milp.py                 ← PuLP 기반 MILP 최적화
│
└── app.py                      ← 4주차 Streamlit UI
```

> **팀 프로젝트와의 차이:** 팀 프로젝트는 파일이 루트에 전부 있었지만, 이번엔 역할별로 폴더를 나눕니다. 규모가 커질수록 유지보수가 쉽습니다.

---

## 3. 환경 설정

### 3-1. `.env` 파일

```
DART_API_KEY=여기에_DART_발급키_입력
ANTHROPIC_API_KEY=여기에_Claude_API키_입력
```

- DART API 키 발급: https://opendart.fss.or.kr → 인증키 신청
- Anthropic API 키: https://console.anthropic.com

### 3-2. `.gitignore` 파일

```
.env
__pycache__/
*.pyc
*.db
.DS_Store
```

### 3-3. `requirements.txt`

```
streamlit
anthropic
dart-fss
python-dotenv
pulp
pandas
```

- `dart-fss`: 팀 프로젝트에서 이미 사용한 DART API 래퍼 라이브러리
- `pulp`: 3주차 MILP 최적화용 — 지금 미리 넣어두면 나중에 편함
- `pandas`: 필터링 결과 데이터프레임 처리용

### 3-4. 패키지 설치

```bash
pip install -r requirements.txt
```

---

## 4. 파일별 코드 구현

### 4-1. `pipeline/db.py` — SQLite 스키마

B2B 필터링에 필요한 **재무 지표 위주**로 컬럼을 설계합니다.  
팀 프로젝트(`data.py`)에서 SQLite를 썼던 패턴과 동일한 방식입니다.

```python
# pipeline/db.py
import sqlite3

DB_PATH = "b2b_finder.db"

def init_db():
    """DB 및 테이블 초기화 (최초 1회만 실행)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            corp_code      TEXT PRIMARY KEY,  -- DART 고유 기업코드
            corp_name      TEXT,              -- 기업명
            industry       TEXT,              -- 산업군 (DART 업종코드)
            market_type    TEXT,              -- KOSPI / KOSDAQ
            revenue        INTEGER,           -- 매출액 (원)
            rd_expense     INTEGER,           -- R&D 비용 (원)
            debt_ratio     REAL,              -- 부채비율 (%)
            employees      INTEGER,           -- 임직원 수
            year           INTEGER,           -- 데이터 기준 연도
            passed_filter  INTEGER DEFAULT 0  -- 1차 필터 통과 여부 (0/1)
        )
    """)
    conn.commit()
    conn.close()
    print("DB 초기화 완료: b2b_finder.db")

def get_connection():
    """DB 연결 반환"""
    return sqlite3.connect(DB_PATH)
```

**컬럼 설계 이유:**

| 컬럼 | 용도 |
|------|------|
| `revenue` | 기업 규모 판단 → 최소 거래 기대 금액 proxy |
| `rd_expense` | 혁신 수용도 판단 → R&D 비중 높을수록 신기술 도입 의향 높음 |
| `debt_ratio` | 재무 건전성 → 부채 많은 기업은 신규 계약 체결 여력 낮음 |
| `employees` | 기업 규모 보조 지표 |
| `passed_filter` | 1차 필터 통과 여부 저장 → 2주차에서 이 값이 1인 기업만 Claude에게 전달 |

---

### 4-2. `pipeline/dart_collector.py` — DART 수집

팀 프로젝트에서는 **특정 기업 1개**를 분석했지만, 이번엔 **전체 상장사 2500개의 재무 요약 데이터를 배치 수집**합니다.

```python
# pipeline/dart_collector.py
import dart_fss as dart
import os
from dotenv import load_dotenv
from pipeline.db import get_connection, init_db

load_dotenv()
dart.set_api_key(os.getenv("DART_API_KEY"))

def collect_all_companies(limit: int = None):
    """
    코스피/코스닥 전체 상장사 목록 + 기본 재무 데이터를 DB에 저장
    
    Args:
        limit: 테스트 시 숫자 지정 (예: 50). None이면 전체 수집.
    """
    init_db()

    # dart-fss로 전체 기업 목록 가져오기
    corp_list = dart.get_corp_list()

    # 테스트 시 limit 적용
    if limit:
        corp_list = corp_list[:limit]

    conn = get_connection()
    saved = 0
    skipped = 0

    for corp in corp_list:
        try:
            # 비상장사 제외 (stock_code가 없으면 비상장)
            if corp.stock_code is None:
                skipped += 1
                continue

            # 최근 사업보고서 재무 데이터 가져오기
            fs = corp.extract_fs(bgn_de="20240101")
            if fs is None:
                skipped += 1
                continue

            # 재무 지표 추출
            revenue    = _get_value(fs, "매출액")
            rd_expense = _get_value(fs, "연구개발비")
            employees  = _get_employees(corp)

            conn.execute("""
                INSERT OR REPLACE INTO companies
                (corp_code, corp_name, market_type, revenue, rd_expense, employees, year)
                VALUES (?, ?, ?, ?, ?, ?, 2024)
            """, (
                corp.corp_code,
                corp.corp_name,
                "LISTED",
                revenue,
                rd_expense,
                employees
            ))

            saved += 1
            if saved % 100 == 0:
                conn.commit()
                print(f"  {saved}개 저장 완료...")

        except Exception as e:
            print(f"  [{corp.corp_name}] 수집 실패: {e}")
            skipped += 1
            continue

    conn.commit()
    conn.close()
    print(f"\n수집 완료 — 저장: {saved}개 / 스킵: {skipped}개")


def _get_value(fs, label: str):
    """재무제표에서 특정 항목 값 추출. 없으면 None 반환."""
    try:
        return int(fs[label].iloc[-1])
    except Exception:
        return None


def _get_employees(corp) -> int:
    """임직원 수 추출. 없으면 None 반환."""
    try:
        return corp.employee
    except Exception:
        return None


if __name__ == "__main__":
    # 테스트: 50개만 먼저 수집
    print("=== 테스트 수집 (50개) ===")
    collect_all_companies(limit=50)

    # 정상 동작 확인 후 아래 주석 해제하여 전체 수집
    # print("=== 전체 수집 시작 ===")
    # collect_all_companies()
```

> **실행 방법:**
> ```bash
> python pipeline/dart_collector.py
> ```

---

### 4-3. `pipeline/filter.py` — 1차 필터링

제안서에 명시된 핵심: **"최소 거래 규모 500만 원 이하 기업 사전 제외"**

B2B에서 기대 계약 금액은 직접 알 수 없으므로, DART 재무 데이터로 **대리 지표(proxy)**를 사용합니다.

**필터 기준 근거:**

| 필터 조건 | 기준값 | 이유 |
|-----------|--------|------|
| 매출액 최소 | 5억 원 | 매출 5억 미만 기업은 500만 원 계약도 부담이 큰 규모 |
| 부채비율 최대 | 200% | 부채비율 200% 초과 = 재무 리스크 기업 → 신규 계약 체결 여력 낮음 |
| 임직원 최소 | 30명 | 30명 미만 = B2B 영업 타깃으로 삼기엔 조직 규모 미달 |

```python
# pipeline/filter.py
import pandas as pd
from pipeline.db import get_connection

# 1차 필터 기준값 (제안서 기반)
FILTER_RULES = {
    "min_revenue":    500_000_000,  # 매출 5억 원 미만 제외
    "max_debt_ratio": 200.0,        # 부채비율 200% 초과 제외
    "min_employees":  30,           # 임직원 30명 미만 제외
}

def apply_filter():
    """
    DB의 전체 기업에 룰베이스 필터를 적용하고 passed_filter 컬럼을 업데이트.
    1차 필터 통과 기업: passed_filter = 1
    """
    conn = get_connection()

    conn.execute("""
        UPDATE companies
        SET passed_filter = CASE
            WHEN revenue IS NULL THEN 0
            WHEN revenue < :min_revenue THEN 0
            WHEN debt_ratio IS NOT NULL AND debt_ratio > :max_debt_ratio THEN 0
            WHEN employees IS NOT NULL AND employees < :min_employees THEN 0
            ELSE 1
        END
    """, FILTER_RULES)

    conn.commit()

    # 결과 출력
    total  = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    passed = conn.execute("SELECT COUNT(*) FROM companies WHERE passed_filter = 1").fetchone()[0]

    print(f"\n1차 필터링 결과")
    print(f"  전체 기업: {total}개")
    print(f"  필터 통과: {passed}개 ({passed / total * 100:.1f}%)")
    print(f"  제외됨:    {total - passed}개")

    conn.close()
    return passed


def get_filtered_companies() -> pd.DataFrame:
    """1차 필터 통과 기업 목록을 DataFrame으로 반환 (2주차에서 사용)"""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT corp_code, corp_name, industry, revenue, rd_expense, employees
        FROM companies
        WHERE passed_filter = 1
        ORDER BY revenue DESC
    """, conn)
    conn.close()
    return df


if __name__ == "__main__":
    apply_filter()

    df = get_filtered_companies()
    print(f"\n통과 기업 상위 10개:")
    print(df.head(10).to_string(index=False))
```

> **실행 방법:**
> ```bash
> python pipeline/filter.py
> ```

---

### 4-4. `CLAUDE.md` — 프로젝트 문서

마일스톤 1에 명시된 **필수 파일**입니다.  
팀 프로젝트의 CLAUDE.md를 참고해 개인 버전으로 작성합니다.

```markdown
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
사용자 입력 (app.py)
  → 1차 룰베이스 필터링 (pipeline/filter.py)    ← 1주차
    → 2차 Claude RAG 분석 (agents/analyzer.py)  ← 2주차
      → 3차 MILP 최적화 (optimizer/milp.py)     ← 3주차
        → 결과 출력 (app.py)                    ← 4주차

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
```

---

## 5. 실행 순서

1주차 작업을 순서대로 실행하는 방법입니다.

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. DB 초기화 (테이블 생성)
python -c "from pipeline.db import init_db; init_db()"

# 3. 테스트 수집 (50개로 먼저 확인)
python pipeline/dart_collector.py

# 4. DB에 데이터 들어갔는지 확인
python -c "
from pipeline.db import get_connection
conn = get_connection()
count = conn.execute('SELECT COUNT(*) FROM companies').fetchone()[0]
print(f'저장된 기업 수: {count}개')
conn.close()
"

# 5. 정상 동작 확인 후 dart_collector.py에서 전체 수집 코드 주석 해제 후 재실행

# 6. 1차 필터링 적용
python pipeline/filter.py
```

---

## 6. 1주차 체크리스트

| 순서 | 할 일 | 확인 |
|------|--------|:----:|
| 1 | GitHub에 `smart-b2b-finder` repo 생성 | ☐ |
| 2 | 로컬에 clone + 폴더 구조 생성 | ☐ |
| 3 | `.env` 파일에 API 키 입력 | ☐ |
| 4 | `.gitignore` 작성 (`.env`, `*.db` 포함) | ☐ |
| 5 | `requirements.txt` 작성 + `pip install` | ☐ |
| 6 | `CLAUDE.md` 작성 후 commit | ☐ |
| 7 | `pipeline/db.py` 작성 → DB 초기화 확인 | ☐ |
| 8 | `pipeline/dart_collector.py` 작성 → **50개 테스트 먼저** | ☐ |
| 9 | 테스트 정상 동작 확인 후 전체 수집 실행 | ☐ |
| 10 | `pipeline/filter.py` 작성 → 필터 결과 출력 확인 | ☐ |
| 11 | 전체 GitHub push | ☐ |

**1주차 완료 기준:** DB에 ~2500개 기업 데이터가 쌓이고, 1차 필터 통과 기업이 30~100개 사이로 좁혀진 상태

---

## 7. 팀 프로젝트 대비 달라지는 점

| 항목 | 팀 프로젝트 (sdic-ai-team3) | 개인 프로젝트 (smart-b2b-finder) |
|------|----------------------------|----------------------------------|
| 분석 대상 | 기업 1개 (LG이노텍) | 전체 상장사 ~2500개 |
| DART 호출 방식 | 단일 기업 상세 분석 (실시간) | 전체 배치 수집 → SQLite 캐싱 |
| Claude 호출 시점 | 매번 실시간 | 1차 필터 통과 기업(~30개)만 선별 후 호출 |
| 최적화 레이어 | 없음 | MILP로 최적 타깃 조합 도출 (3주차) |
| 아웃풋 | 기업 분석 리포트 | 영업 우선순위 리스트 + Why-Not 리포트 |

---

## 8. 주의사항 및 트러블슈팅

### 주의사항

**1. 테스트는 반드시 50개로 먼저**  
전체 2500개 수집은 1~2시간 소요됩니다. `collect_all_companies(limit=50)`으로 먼저 동작을 확인하세요.

**2. DART API 호출 속도 제한**  
DART API는 초당 요청 수 제한이 있습니다. 에러가 발생하면 `dart_collector.py`의 loop 안에 `import time; time.sleep(0.5)` 를 추가하세요.

**3. `.env` GitHub 업로드 절대 금지**  
`.gitignore`에 `.env`가 포함되어 있는지 push 전 반드시 확인하세요.

### 자주 나오는 에러

| 에러 메시지 | 원인 | 해결 |
|-------------|------|------|
| `DART_API_KEY not found` | `.env` 파일이 없거나 키 오타 | `.env` 파일 위치와 변수명 재확인 |
| `ModuleNotFoundError: dart_fss` | 패키지 미설치 | `pip install dart-fss` |
| `sqlite3.OperationalError: no such table` | `init_db()` 미실행 | `python -c "from pipeline.db import init_db; init_db()"` 실행 |
| `extract_fs() returns None` | 해당 기업 재무 데이터 없음 | 정상 동작 — `skipped` 카운트로 집계됨 |

---

## 전체 흐름 요약

```
[1주차] DART API → SQLite (2500개 저장) → 룰베이스 필터 (30~50개로 압축)
    ↓
[2주차] Claude RAG → 사업보고서 분석 → 수주확률(P) & 기대가치(V) 스코어링
    ↓
[3주차] PuLP MILP → 제약조건(개발공수 200H, AM슬롯 5곳) → 최적 타깃 조합
    ↓
[4주차] Streamlit → 영업 우선순위 리스트 + Why-Not 리포트 + 공개 URL 배포
```
