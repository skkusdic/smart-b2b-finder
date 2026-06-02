import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()
_KEY = os.getenv("KIPRIS_API_KEY", "")

_CORP_BS_BASE = "http://plus.kipris.or.kr/openapi/rest/CorpBsApplicantService"
_TECH_URL     = "http://plus.kipris.or.kr/openapi/rest/ApplicantTechInfoService/applicantTechInfo"

# IT/소프트웨어(58,62,63) + 전자/반도체/제조(26~30) — 특허가 의미있는 업종만
KIPRIS_ELIGIBLE_PREFIXES = {"58", "62", "63", "26", "27", "28", "29", "30"}

_CPC_SECTION = {
    "A": "생활필수품/의료",
    "B": "처리·운반·포장",
    "C": "화학/야금",
    "D": "섬유/종이",
    "E": "건설/토목",
    "F": "기계/엔진",
    "G": "물리학/컴퓨팅/측정",
    "H": "전기/전자",
}


def _xml_texts(xml_str: str, tag: str) -> list[str]:
    try:
        root = ET.fromstring(xml_str)
        return [el.text for el in root.iter(tag) if el.text]
    except Exception:
        return []


def _get_patent_customer_number(bizr_no: str) -> str | None:
    """사업자등록번호 → 특허고객번호 (KIPRIS CorpBsApplicantService 3번 오퍼레이션)"""
    if not _KEY or not bizr_no:
        return None
    clean = bizr_no.replace("-", "")
    try:
        resp = requests.get(
            f"{_CORP_BS_BASE}/corpBsApplicantInfoByBizrNo",
            params={"bizrNo": clean, "accessKey": _KEY},
            timeout=10,
        )
        numbers = _xml_texts(resp.text, "ApplicantNumber")
        return numbers[0] if numbers else None
    except Exception:
        return None


def _get_tech_summary(patent_customer_number: str, corp_name: str) -> str:
    """특허고객번호 → 기술분야 요약 문자열"""
    if not _KEY or not patent_customer_number:
        return ""
    try:
        resp = requests.get(
            _TECH_URL,
            params={
                "patentCustomerNumber": patent_customer_number,
                "rightType": "1",   # 1=특허
                "accessKey": _KEY,
            },
            timeout=10,
        )
        codes   = _xml_texts(resp.text, "classificationCode")
        apps    = _xml_texts(resp.text, "applicationCaseCount")
        regs    = _xml_texts(resp.text, "registrationCaseCount")

        if not codes:
            return ""

        total_apps = sum(int(c) for c in apps if c and c.isdigit())
        total_regs = sum(int(c) for c in regs if c and c.isdigit())

        # CPC 섹션(첫 글자) 기준 기술 분야 집계
        sections: dict[str, int] = {}
        for code in codes:
            sec   = code[0].upper() if code else ""
            label = _CPC_SECTION.get(sec, "기타")
            sections[label] = sections.get(label, 0) + 1

        top = sorted(sections.items(), key=lambda x: -x[1])[:3]
        section_str = ", ".join(f"{s}({n}건)" for s, n in top)

        return (
            f"[KIPRIS 특허 데이터] {corp_name}: "
            f"특허 출원 {total_apps}건 / 등록 {total_regs}건. "
            f"주요 기술 분야: {section_str}."
        )
    except Exception:
        return ""


def fetch_kipris_context(corp_name: str, bizr_no: str, industry_code: str = "") -> str:
    """
    기업명 + 사업자번호 + 업종코드 → KIPRIS 특허 요약 문자열.

    - KIPRIS_ELIGIBLE_PREFIXES에 해당하는 업종만 조회 (나머지는 즉시 "" 반환)
    - API 오류·결과 없음 모두 "" 반환 (항상 graceful)
    """
    prefix = str(industry_code)[:2]
    if prefix not in KIPRIS_ELIGIBLE_PREFIXES:
        return ""

    if not _KEY:
        return ""

    pcn = _get_patent_customer_number(bizr_no)
    if not pcn:
        return ""

    return _get_tech_summary(pcn, corp_name)
