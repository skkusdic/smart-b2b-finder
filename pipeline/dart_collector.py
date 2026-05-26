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

    corp_list = dart.get_corp_list()

    if limit:
        corp_list = corp_list[:limit]

    conn = get_connection()
    saved = 0
    skipped = 0

    for corp in corp_list:
        try:
            if corp.stock_code is None:
                skipped += 1
                continue

            fs = corp.extract_fs(bgn_de="20240101")
            if fs is None:
                skipped += 1
                continue

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
    try:
        return int(fs[label].iloc[-1])
    except Exception:
        return None


def _get_employees(corp) -> int:
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
