import sys
import sqlite3
import pandas as pd
from pipeline.db import get_connection

# 산업군 카테고리 → DART 업종코드 매핑 (KSIC 숫자 코드 prefix 기반)
# DART induty_code 예시: '582'(소프트웨어), '262'(반도체), '212'(의약품)
INDUSTRY_MAP = {
    "IT/소프트웨어": ["58", "62", "63"],          # 소프트웨어·정보서비스
    "제조업(전자/반도체)": ["26", "27", "28"],     # 전자부품·컴퓨터·전기장비
    "제조업(기계/자동차)": ["28", "29", "30", "31"],
    "제조업(화학/소재)": ["20", "22", "23", "24", "25"],
    "제조업(전체)": ["10", "11", "12", "13", "14", "15", "16", "17",
                    "18", "19", "20", "21", "22", "23", "24", "25",
                    "26", "27", "28", "29", "30", "31", "32", "33"],
    "바이오/헬스케어": ["21", "86", "87", "88"],   # 의약품·의료
    "금융": ["64", "65", "66"],
    "유통/물류": ["45", "46", "47", "49", "50", "51", "52"],
    "건설/부동산": ["41", "42", "43", "68"],
    "서비스업": ["69", "70", "71", "72", "73", "74", "75"],
    "전체": [],  # 빈 리스트 = 필터 없음
}


def stage1_macro_filter(
    industry_category: str = "전체",
    min_deal_size: int = 5_000_000,
    max_revenue: int | None = 1_000_000_000_000,
    min_employees: int = 10,
    max_employees: int | None = 10_000,
    year: int = 2025,
) -> pd.DataFrame:
    """
    1단계: 거시 필터 — 산업군 + 규모 기반으로 2,750개 → ~200개

    Args:
        industry_category: INDUSTRY_MAP 키 중 하나
        min_deal_size:      최소 거래 규모(원). 매출액 기준은 이 값의 10배.
        max_revenue:        매출액 상한(원). None이면 상한 없음.
        min_employees:      최소 임직원 수.
        max_employees:      최대 임직원 수. None이면 상한 없음.
        year:               수집 연도.

    Returns:
        필터 통과 기업 DataFrame
    """
    conn = get_connection()
    min_revenue = min_deal_size * 10

    query = """
        SELECT corp_code, corp_name, industry, market_type,
               revenue, rd_expense, debt_ratio, employees, year
        FROM companies
        WHERE year = ?
          AND revenue IS NOT NULL
          AND revenue >= ?
    """
    params: list = [year, min_revenue]

    if max_revenue is not None:
        query += " AND revenue <= ?"
        params.append(max_revenue)

    if min_employees > 0:
        query += " AND (employees IS NULL OR employees >= ?)"
        params.append(min_employees)

    if max_employees is not None:
        query += " AND (employees IS NULL OR employees <= ?)"
        params.append(max_employees)

    df = pd.read_sql_query(query, conn, params=params)

    # 산업군 필터 (업종코드 prefix 매칭)
    codes = INDUSTRY_MAP.get(industry_category, [])
    if codes:
        mask = df["industry"].fillna("").apply(
            lambda x: any(x.startswith(c) for c in codes)
        )
        df = df[mask]

    df = df.reset_index(drop=True)

    # passed_filter DB 갱신: 해당 연도 전체 리셋 후 통과 기업만 1로 마킹
    if len(df) > 0:
        passed_codes = df["corp_code"].tolist()
        placeholders = ",".join("?" * len(passed_codes))
        conn.execute(
            f"UPDATE companies SET passed_filter=0 WHERE year=?", (year,)
        )
        conn.execute(
            f"UPDATE companies SET passed_filter=1 WHERE year=? AND corp_code IN ({placeholders})",
            [year] + passed_codes,
        )
        conn.commit()
    conn.close()

    return df


def run_stage1(
    industry_category: str = "전체",
    min_deal_size: int = 5_000_000,
    max_revenue: int | None = 1_000_000_000_000,
    min_employees: int = 10,
    year: int = 2025,
) -> pd.DataFrame:
    """1단계 필터 실행 + 결과 출력."""
    total_conn = get_connection()
    total = total_conn.execute(
        "SELECT COUNT(*) FROM companies WHERE year=?", (year,)
    ).fetchone()[0]
    total_conn.close()

    df = stage1_macro_filter(
        industry_category=industry_category,
        min_deal_size=min_deal_size,
        max_revenue=max_revenue,
        min_employees=min_employees,
        year=year,
    )

    pct = len(df) / total * 100 if total else 0
    print(f"\n[1단계 거시 필터 결과]")
    print(f"  전체 기업:     {total}개")
    print(f"  필터 통과:     {len(df)}개 ({pct:.1f}%)")
    print(f"  제외됨:        {total - len(df)}개")
    print(f"  적용 기준:")
    print(f"    - 산업군:    {industry_category}")
    print(f"    - 최소 매출: {min_deal_size * 10:,}원 (거래 규모 {min_deal_size:,}원의 10배)")
    if max_revenue:
        print(f"    - 최대 매출: {max_revenue:,}원")
    print(f"    - 최소 인원: {min_employees}명")

    return df


def get_stage1_companies(year: int = 2025) -> pd.DataFrame:
    """
    기본 파라미터로 1단계 통과 기업 반환 (2단계 진입점).
    실제 서비스에서는 run_stage1()에 사용자 입력을 전달.
    """
    return stage1_macro_filter(year=year)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Smart B2B Finder — 1단계 거시 필터 테스트 ===")
    print()

    # 테스트 케이스 1: IT 기업, 최소 거래 500만원
    df1 = run_stage1(
        industry_category="IT/소프트웨어",
        min_deal_size=5_000_000,
        min_employees=10,
    )
    if len(df1) > 0:
        print(f"\n상위 10개 (매출 기준):")
        display = df1[["corp_name", "industry", "market_type", "revenue", "employees"]].head(10).copy()
        display["revenue"] = display["revenue"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")
        print(display.to_string(index=False))

    print()

    # 테스트 케이스 2: 전체 산업, 최소 거래 500만원
    df2 = run_stage1(
        industry_category="전체",
        min_deal_size=5_000_000,
        min_employees=10,
    )
