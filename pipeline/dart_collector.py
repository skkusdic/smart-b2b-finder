import requests
import os
import time
from dotenv import load_dotenv
from pipeline.db import get_connection, init_db

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")
BASE_URL = "https://opendart.fss.or.kr/api"


def _get(endpoint: str, params: dict) -> dict:
    params["crtfc_key"] = DART_API_KEY
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
    return resp.json()


def fetch_corp_codes(year: int = 2024, limit: int = None) -> list[dict]:
    """
    해당 연도 사업보고서를 제출한 기업 목록 반환.
    DART API는 corp_code 없이 조회 시 3개월 이내만 허용하므로 분기별로 분할 요청.
    """
    # 2024년 사업보고서는 2025년 1~5월에 제출됨
    quarters = [
        (f"{year + 1}0101", f"{year + 1}0331"),
        (f"{year + 1}0401", f"{year + 1}0630"),
    ]

    seen = set()
    unique = []

    for bgn_de, end_de in quarters:
        page_no = 1
        while True:
            data = _get("list.json", {
                "pblntf_ty": "A",       # 사업보고서
                "bgn_de": bgn_de,
                "end_de": end_de,
                "page_count": 100,
                "page_no": page_no,
            })

            if data.get("status") != "000":
                break

            for c in data["list"]:
                if c["corp_code"] not in seen:
                    seen.add(c["corp_code"])
                    unique.append(c)

            total_page = (data["total_count"] + 99) // 100
            if page_no >= total_page:
                break
            page_no += 1
            time.sleep(0.1)

    return unique[:limit] if limit else unique


def fetch_financials(corp_code: str, year: int = 2024) -> dict:
    """단일 기업 재무 데이터 (매출액, R&D비) 반환."""
    for fs_div in ("CFS", "OFS"):  # 연결 → 개별 순으로 fallback
        data = _get("fnlttSinglAcnt.json", {
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # 사업보고서
            "fs_div": fs_div,
        })
        if data.get("status") == "000":
            break
    else:
        return {}

    result = {}
    for item in data.get("list", []):
        name = item.get("account_nm", "")
        raw = item.get("thstrm_amount", "").replace(",", "")
        if not raw:
            continue
        try:
            val = int(raw)
        except ValueError:
            continue

        if name == "매출액":
            result["revenue"] = val
        elif name in ("연구개발비", "경상연구개발비") and "rd_expense" not in result:
            result["rd_expense"] = val

    return result


def fetch_company_info(corp_code: str) -> dict:
    """기업 기본 정보 (종업원 수, 업종) 반환."""
    data = _get("company.json", {"corp_code": corp_code})
    if data.get("status") != "000":
        return {}
    return {
        "employees": _safe_int(data.get("emp_no")),
        "industry": data.get("induty_code"),
        "market_type": {"Y": "KOSPI", "K": "KOSDAQ"}.get(data.get("corp_cls"), "ETC"),
    }


def search_corp_by_name(corp_name: str) -> list[dict]:
    """기업명으로 DART 공시 목록에서 corp_code 검색 (실시간).
    DART list.json은 bgn_de/end_de 필수 — 최근 2년 범위로 고정.
    """
    data = _get("list.json", {
        "corp_name": corp_name,
        "pblntf_ty": "A",
        "bgn_de": "20240101",
        "end_de": "20261231",
        "page_count": 10,
        "page_no": 1,
    })
    if data.get("status") != "000":
        return []
    seen, result = set(), []
    for item in data.get("list", []):
        cc = item.get("corp_code")
        if cc and cc not in seen:
            seen.add(cc)
            result.append({"corp_code": cc, "corp_name": item.get("corp_name", "")})
    return result


def fetch_corp_realtime(corp_code: str, corp_name: str, year: int = 2024) -> dict | None:
    """DART API로 기업 재무·기본 정보를 실시간 수집해 companies 행 구조로 반환."""
    fin = fetch_financials(corp_code, year=year)
    if not fin:
        return None
    info = fetch_company_info(corp_code)
    detail = fetch_detailed_financials(corp_code, year=year)
    return {
        "corp_code":   corp_code,
        "corp_name":   corp_name,
        "market_type": info.get("market_type", "ETC"),
        "industry":    info.get("industry", ""),
        "revenue":     fin.get("revenue"),
        "rd_expense":  detail.get("rd_expense") or fin.get("rd_expense"),
        "debt_ratio":  detail.get("debt_ratio"),
        "employees":   info.get("employees"),
        "year":        year,
        "passed_filter": 0,
    }


def fetch_bizr_no(corp_code: str) -> str:
    """corp_code → 사업자등록번호 (KIPRIS 연동용)."""
    data = _get("company.json", {"corp_code": corp_code})
    if data.get("status") != "000":
        return ""
    return data.get("bizr_no", "") or ""


def _safe_int(val) -> int | None:
    try:
        return int(str(val).replace(",", ""))
    except Exception:
        return None


def fetch_detailed_financials(corp_code: str, year: int = 2025) -> dict:
    """fnlttSinglAcntAll로 R&D비 + 부채비율 수집."""
    for fs_div in ("CFS", "OFS"):
        data = _get("fnlttSinglAcntAll.json", {
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",
            "fs_div": fs_div,
        })
        if data.get("status") == "000":
            break
    else:
        return {}

    result = {}
    for item in data.get("list", []):
        name = item.get("account_nm", "")
        raw = item.get("thstrm_amount", "").replace(",", "")
        if not raw:
            continue
        try:
            val = int(raw)
        except ValueError:
            continue

        if name in ("연구개발비", "경상연구개발비") and "rd_expense" not in result:
            result["rd_expense"] = val
        elif name == "부채총계":
            result["total_debt"] = val
        elif name == "자본총계":
            result["total_equity"] = val

    if "total_debt" in result and "total_equity" in result and result["total_equity"] != 0:
        result["debt_ratio"] = round(result["total_debt"] / result["total_equity"] * 100, 2)

    return result


def update_stage1_financials(year: int = 2025):
    """1단계 통과 기업(revenue != NULL)에 대해 fnlttSinglAcntAll로 R&D비·부채비율 업데이트."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT corp_code, corp_name FROM companies WHERE year=? AND revenue IS NOT NULL",
        (year,)
    ).fetchall()
    conn.close()

    total = len(rows)
    print(f"=== fnlttSinglAcntAll 재수집 시작: {total}개 기업 ===")

    updated = 0
    failed = 0

    conn = get_connection()
    for i, (corp_code, corp_name) in enumerate(rows, 1):
        try:
            detail = fetch_detailed_financials(corp_code, year=year)
            if not detail:
                failed += 1
                continue

            conn.execute("""
                UPDATE companies
                SET rd_expense = COALESCE(?, rd_expense),
                    debt_ratio = COALESCE(?, debt_ratio)
                WHERE corp_code = ? AND year = ?
            """, (
                detail.get("rd_expense"),
                detail.get("debt_ratio"),
                corp_code,
                year,
            ))

            updated += 1
            if updated % 100 == 0:
                conn.commit()
                pct = i / total * 100
                print(f"  {i}/{total} ({pct:.0f}%) — 업데이트: {updated}개")

            time.sleep(0.5)

        except Exception as e:
            print(f"  [{corp_name}] 실패: {e}")
            failed += 1

    conn.commit()
    conn.close()
    print(f"\n완료 — 업데이트: {updated}개 / 실패: {failed}개")


def collect_all_companies(year: int = 2024, limit: int = None):
    """
    사업보고서 제출 기업 재무 데이터를 DB에 저장.

    Args:
        year:  수집 기준 회계연도 (기본 2024)
        limit: 테스트 시 숫자 지정 (예: 50). None 이면 전체.
    """
    init_db()

    print(f"=== {year}년 사업보고서 제출 기업 목록 수집 중... ===")
    corp_list = fetch_corp_codes(year=year, limit=limit)
    print(f"대상 기업: {len(corp_list)}개\n")

    conn = get_connection()
    saved = 0
    skipped = 0

    for i, corp in enumerate(corp_list, 1):
        corp_code = corp["corp_code"]
        corp_name = corp["corp_name"]

        try:
            financials = fetch_financials(corp_code, year=year)
            if not financials:
                skipped += 1
                continue

            info = fetch_company_info(corp_code)
            time.sleep(0.05)  # API 속도 제한 대응

            conn.execute("""
                INSERT OR REPLACE INTO companies
                (corp_code, corp_name, market_type, industry, revenue, rd_expense, employees, year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                corp_code,
                corp_name,
                info.get("market_type", "ETC"),
                info.get("industry"),
                financials.get("revenue"),
                financials.get("rd_expense"),
                info.get("employees"),
                year,
            ))

            saved += 1
            if saved % 50 == 0:
                conn.commit()
                print(f"  {saved}개 저장 완료...")

        except Exception as e:
            print(f"  [{corp_name}] 수집 실패: {e}")
            skipped += 1

    conn.commit()
    conn.close()
    print(f"\n수집 완료 — 저장: {saved}개 / 스킵: {skipped}개")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== 전체 수집 시작 (2025년 기준) ===")
    collect_all_companies(year=2025)
