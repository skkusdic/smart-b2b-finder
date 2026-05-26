import pandas as pd
from pipeline.db import get_connection

FILTER_RULES = {
    "min_revenue":    500_000_000,  # 매출 5억 원 미만 제외
    "max_debt_ratio": 200.0,        # 부채비율 200% 초과 제외
    "min_employees":  30,           # 임직원 30명 미만 제외
}

def apply_filter():
    """
    DB의 전체 기업에 룰베이스 필터를 적용하고 passed_filter 컬럼을 업데이트.
    통과 기업: passed_filter = 1
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
