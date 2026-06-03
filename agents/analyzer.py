import io
import os
import re
import json
import time
import zipfile
import requests
import anthropic
import pandas as pd
from dotenv import load_dotenv
from pipeline.db import get_connection
from pipeline.kipris import fetch_kipris_context, KIPRIS_ELIGIBLE_PREFIXES

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")
DART_BASE = "https://opendart.fss.or.kr/api"

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5"

# ── 카테고리별 가중치 프로필 ──────────────────────────────────────────────────
WEIGHT_PROFILES = {
    # growth_score 제거 후 비례 재조정 (합계 1.0)
    # growth_score는 전년도 데이터 미확보로 비활성화. 추후 2023 회계연도 수집 후 복원.
    "SaaS/B2B 소프트웨어": {
        "rd_score":   0.30,
        "debt_score": 0.25,
        "rag_score":  0.45,
    },
    "AI/데이터 솔루션": {
        "rd_score":   0.55,
        "debt_score": 0.20,
        "rag_score":  0.25,
    },
    "하드웨어/IoT": {
        "rd_score":   0.30,
        "debt_score": 0.45,
        "rag_score":  0.25,
    },
    "컨설팅/서비스": {
        "rd_score":   0.15,
        "debt_score": 0.25,
        "rag_score":  0.60,
    },
    "기타": None,  # Claude가 자유 텍스트 분석 후 가중치 반환
}

# ── 정규화 ────────────────────────────────────────────────────────────────────

def _normalize(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """
    백분위 → 0~10점 변환.
    유효값이 2개 미만이면 전체 5.0(중간값) 반환.
    """
    valid = series.dropna()
    if len(valid) < 2:
        return pd.Series(5.0, index=series.index)
    rank = series.rank(pct=True, na_option="keep")
    if not higher_is_better:
        rank = 1 - rank
    return (rank * 10).fillna(5.0).round(2)


def compute_numeric_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    수치 지표를 업종별 백분위로 정규화해 rd_score, debt_score, growth_score 컬럼 추가.
    - rd_expense NULL → 0으로 간주 (R&D 미공시 = R&D 없음)
    - 자본잠식(debt_ratio <= 0) → debt_score = 0 고정
    - 성장률: DB 단일 연도라 중간값 5.0 대입
    """
    df = df.copy()

    # R&D 비율 (NULL → 0 처리 후 업종별 정규화)
    df["rd_ratio"] = df["rd_expense"].fillna(0) / df["revenue"]
    df["rd_score"] = df.groupby("industry")["rd_ratio"].transform(
        lambda s: _normalize(s)
    )

    # 부채비율 정규화 (낮을수록 좋음, NULL → 5.0)
    df["debt_score"] = df.groupby("industry")["debt_ratio"].transform(
        lambda s: _normalize(s, higher_is_better=False)
    )
    # 자본잠식 기업 0점 고정
    df.loc[df["debt_ratio"].notna() & (df["debt_ratio"] <= 0), "debt_score"] = 0.0

    return df


# ── 가중치 결정 ───────────────────────────────────────────────────────────────

def get_weights(product_category: str, product_description: str) -> dict:
    """
    정의된 카테고리 → 프로필 반환.
    '기타' → Claude가 제품 설명 분석 후 가중치 JSON 반환.
    """
    if product_category in WEIGHT_PROFILES and WEIGHT_PROFILES[product_category] is not None:
        return WEIGHT_PROFILES[product_category]

    prompt = f"""다음 B2B 제품 설명을 읽고 영업 타깃 스코어링에 쓸 가중치를 JSON으로만 반환해라.
합계는 반드시 1.0이어야 한다. 설명 없이 JSON만 출력.

제품 설명: {product_description}

반환 형식:
{{"rd_score": 0.X, "debt_score": 0.X, "rag_score": 0.X}}"""

    try:
        resp = claude.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(resp.content[0].text.strip())
    except Exception:
        return {"rd_score": 0.33, "debt_score": 0.33, "rag_score": 0.34}


# ── DART 사업보고서 텍스트 수집 ───────────────────────────────────────────────

def _get_rcept_no(corp_code: str, year: int = 2025) -> str | None:
    """corp_code로 해당 회계연도 사업보고서 접수번호 조회.
    사업보고서(11011)는 회계연도 다음 해 1~6월에 제출되므로 year+1 범위를 검색.
    """
    submit_year = year + 1
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "pblntf_ty": "A",
        "bgn_de": f"{submit_year}0101",
        "end_de": f"{submit_year}0630",
        "page_count": 10,
    }
    data = requests.get(f"{DART_BASE}/list.json", params=params, timeout=10).json()
    if data.get("status") != "000":
        return None
    for item in data.get("list", []):
        if item.get("report_nm", "").startswith("사업보고서"):
            return item["rcept_no"]
    return None


def _get_business_text(rcept_no: str) -> str:
    """
    document.json으로 ZIP 다운로드 → '사업의 내용' XML 추출.
    DART document.json은 JSON이 아닌 ZIP 바이너리를 반환함.
    """
    params = {"crtfc_key": DART_API_KEY, "rcept_no": rcept_no}
    try:
        resp = requests.get(f"{DART_BASE}/document.json", params=params, timeout=30)
        if resp.status_code != 200 or len(resp.content) < 100:
            return ""

        z = zipfile.ZipFile(io.BytesIO(resp.content))
        names = z.namelist()

        # '사업의 내용' 관련 파일 우선 탐색
        target = next(
            (n for n in names if any(kw in n for kw in ["사업", "biz", "business", "II."])),
            None,
        )
        # 못 찾으면 가장 큰 XML 파일 (본문일 가능성 높음)
        if not target:
            xml_files = [n for n in names if n.lower().endswith(".xml")]
            target = max(xml_files, key=lambda n: z.getinfo(n).file_size, default=None)

        if not target:
            return ""

        raw = z.read(target).decode("utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:6000]

    except Exception:
        return ""


def fetch_business_text(corp_code: str, year: int = 2025) -> str:
    """
    corp_code → 사업의 내용 텍스트 반환.
    DB 캐시 우선 → 없으면 DART API 조회 후 DB에 저장.
    """
    conn = get_connection()
    cached = conn.execute(
        "SELECT business_text FROM companies WHERE corp_code=? AND year=?",
        (corp_code, year),
    ).fetchone()
    conn.close()

    if cached and cached[0]:
        return cached[0]

    rcept_no = _get_rcept_no(corp_code, year)
    text = _get_business_text(rcept_no) if rcept_no else ""

    try:
        conn = get_connection()
        conn.execute(
            "UPDATE companies SET business_text=? WHERE corp_code=? AND year=?",
            (text or None, corp_code, year),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return text


# ── Claude RAG 채점 ───────────────────────────────────────────────────────────

RAG_CRITERIA = [
    ("problem_fit",          "문제 일치도",         "우리 제품이 해결하는 문제를 이 기업이 직접 언급하는가"),
    ("digital_willingness",  "디지털 전환 의지",    "AI 도입, 자동화 추진, 디지털 전환 등 기술 투자 의지가 있는가"),
    ("investment_direction", "신사업 투자 방향",    "신사업 방향이 우리 제품 영역과 겹치는가"),
    ("external_adoption",    "외부 솔루션 도입 이력", "외부 솔루션 도입, 파트너십, 기술 구매 이력이 있는가"),
    ("decision_structure",   "의사결정 구조",       "빠른 의사결정 구조 또는 혁신 친화적 경영 기조인가"),
]


def score_rag_single(
    corp_name: str,
    business_text: str,
    product_description: str,
    product_category: str = "기타",
    industry_code: str = "",
    revenue: int = 0,
    rd_expense: int | None = None,
    kipris_context: str = "",
) -> dict | None:
    """
    단일 기업 RAG 채점.

    Step 1 — 업종 적합성 gate: 실제로 product_category 영역 기업인지 판단.
              부적합 판정 시 None 반환 → run_stage2에서 즉시 제외.
    Step 2 — 5개 항목 0~10점 채점 (gate 통과한 경우만).

    사업보고서 원문이 없는 경우 Claude 자체 기업 지식 + 재무 프로필로 판단.
    반환: {"is_valid": bool, "problem_fit": {...}, ...} or None
    """
    criteria_text = "\n".join(
        f"- {key} ({label}): {desc}" for key, label, desc in RAG_CRITERIA
    )

    rd_info = f"{rd_expense:,}원 (매출의 {rd_expense/revenue*100:.1f}%)" if rd_expense and revenue else "미공시"
    financial_context = f"매출: {revenue:,}원 | R&D비: {rd_info} | KSIC 업종코드: {industry_code}"

    if business_text:
        knowledge_section = f"[{corp_name} 사업보고서 - 사업의 내용]\n{business_text}"
        if kipris_context:
            knowledge_section += f"\n\n{kipris_context}"
    elif kipris_context:
        knowledge_section = (
            f"[{corp_name} 기업 정보 — DART 사업보고서 미제공]\n"
            f"{financial_context}\n\n"
            f"{kipris_context}"
        )
    else:
        knowledge_section = (
            f"[{corp_name} 기업 정보 — 사업보고서 원문 미제공]\n"
            f"{financial_context}\n"
            f"당신이 알고 있는 이 기업에 대한 지식을 활용하세요.\n"
            f"모르는 기업이라면 업종코드와 재무 프로필만으로 판단하세요."
        )

    prompt = f"""당신은 B2B 영업 전략 전문가입니다.
아래 기업을 두 단계로 분석하세요.

[우리 제품 카테고리]
{product_category}

[우리 제품 설명]
{product_description}

{knowledge_section}

## Step 1 — 업종 적합성 게이트
이 기업이 '{product_category}' 제품의 잠재 구매자가 될 수 있는가?
기본값은 true. 음식점·학원·병원처럼 완전히 무관한 업종이거나
이 제품을 구매할 이유가 전혀 없는 경우에만 false.
동종업계(예: IT 기업이 SaaS 구매)도 외부 솔루션 도입 가능성 있으면 true.

## Step 2 — 항목 채점 (is_valid true/false 무관, 항상 진행, 각 0~10점)
{criteria_text}
is_valid=false여도 채점을 진행하라. 어떤 항목이 부적합의 원인인지 보여주는 것이 목적이다.

JSON 형식으로만 응답. 설명 없이 JSON만 출력:
{{
  "is_valid": true 또는 false,
  "invalid_reason": "부적합 사유 (is_valid=false일 때만, 그 외 빈 문자열)",
  "main_products": "이 기업의 주력 제품·서비스 2~3개 (1~2문장, 한국어, 사업보고서 기반)",
  "key_partners": "주요 고객사·파트너사 (확인 가능한 경우, 없으면 공시에서 확인 불가)",
  "collaboration_signal": "positive 또는 cautious 또는 negative",
  "collaboration_reason": "외부 솔루션 협력 가능성 판단 근거 한 줄 (한국어)",
  "problem_fit":          {{"score": 정수, "reason": "한 줄 근거"}},
  "digital_willingness":  {{"score": 정수, "reason": "한 줄 근거"}},
  "investment_direction": {{"score": 정수, "reason": "한 줄 근거"}},
  "external_adoption":    {{"score": 정수, "reason": "한 줄 근거"}},
  "decision_structure":   {{"score": 정수, "reason": "한 줄 근거"}}
}}"""

    try:
        resp = claude.messages.create(
            model=MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```.*$", "", raw, flags=re.DOTALL)
        result = json.loads(raw.strip())
        return result
    except json.JSONDecodeError:
        result = {key: {"score": 5, "reason": "파싱 실패"} for key, *_ in RAG_CRITERIA}
        result["is_valid"] = True
        return result
    except anthropic.BadRequestError as e:
        # 크레딧 부족 등 API 400 에러는 위로 올려서 app.py에서 처리
        if "credit" in str(e).lower() or "billing" in str(e).lower():
            raise RuntimeError(f"CREDIT_EXHAUSTED:{e}") from e
        result = {key: {"score": 5, "reason": "API 오류"} for key, *_ in RAG_CRITERIA}
        result["is_valid"] = True
        return result
    except Exception:
        result = {key: {"score": 5, "reason": "API 오류"} for key, *_ in RAG_CRITERIA}
        result["is_valid"] = True
        return result


# ── 2단계 메인 파이프라인 ─────────────────────────────────────────────────────

def run_stage2(
    stage1_df: pd.DataFrame,
    product_category: str,
    product_description: str,
    top_n: int = 30,
    year: int = 2025,
) -> pd.DataFrame:
    """
    2단계 Claude RAG 스코어링.

    Args:
        stage1_df:           1단계 통과 기업 DataFrame
        product_category:    WEIGHT_PROFILES 키 중 하나 ('기타' 가능)
        product_description: 사용자 제품 자유 텍스트
        top_n:               반환할 상위 기업 수 (기본 30)
        year:                사업보고서 기준 연도

    Returns:
        상위 top_n개 기업 + 점수 컬럼 포함 DataFrame
    """
    print(f"\n[2단계 RAG 스코어링 시작] 대상: {len(stage1_df)}개")

    # 1. 수치 점수 계산
    df = compute_numeric_scores(stage1_df)

    # 2. 가중치 결정
    weights = get_weights(product_category, product_description)
    print(f"  적용 가중치: {weights}")

    # 3. Claude RAG 채점 (기업별 순차 호출)
    rag_results = []
    excluded = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        corp_code = row["corp_code"]
        corp_name = row["corp_name"]

        print(f"  [{i}/{len(df)}] {corp_name} RAG 채점 중...", end=" ")
        biz_text = fetch_business_text(corp_code, year=year)

        # KIPRIS fallback: 사업보고서 없음 + IT/제조 업종
        kipris_context = ""
        industry_prefix = str(row.get("industry", ""))[:2]
        if not biz_text and industry_prefix in KIPRIS_ELIGIBLE_PREFIXES:
            from pipeline.dart_collector import fetch_bizr_no
            bizr_no = fetch_bizr_no(corp_code)
            if bizr_no:
                kipris_context = fetch_kipris_context(corp_name, bizr_no, str(row.get("industry", "")))
                if kipris_context:
                    print(f"[KIPRIS] ", end=" ")

        rag = score_rag_single(
            corp_name, biz_text, product_description, product_category,
            industry_code=str(row.get("industry", "")),
            revenue=int(row.get("revenue") or 0),
            rd_expense=int(row["rd_expense"]) if (row.get("rd_expense") and not pd.isna(row["rd_expense"])) else None,
            kipris_context=kipris_context,
        )

        if rag is None:
            print("❌ 업종 부적합 — 제외")
            excluded.append(corp_name)
            continue

        rag_score = sum(v["score"] for k, v in rag.items()
                        if isinstance(v, dict) and "score" in v) / len(RAG_CRITERIA)
        print(f"✅ rag_score={rag_score:.1f}")
        rag_results.append({
            "corp_code": corp_code,
            "rag_score": round(rag_score, 2),
            "rag_detail": json.dumps(rag, ensure_ascii=False),
        })
        time.sleep(0.3)

    if excluded:
        print(f"\n  업종 부적합 제외: {len(excluded)}개 — {', '.join(excluded)}")

    rag_df = pd.DataFrame(rag_results) if rag_results else pd.DataFrame(columns=["corp_code", "rag_score", "rag_detail"])
    df = df.merge(rag_df, on="corp_code", how="inner")  # inner join으로 제외된 기업 자동 탈락

    # 4. 종합 점수 계산 (0~100점)
    df["total_score"] = (
        df["rd_score"]   * weights["rd_score"] +
        df["debt_score"] * weights["debt_score"] +
        df["rag_score"]  * weights["rag_score"]
    ) * 10

    # 5. 상위 top_n개 추출
    result = df.nlargest(top_n, "total_score").reset_index(drop=True)

    # 6. DB 저장 (동일 corp_code+year+product_description 조합은 덮어쓰기)
    _save_stage2_results(result, product_description, product_category, year)

    print(f"\n[2단계 완료] 상위 {len(result)}개 선별")
    print(result[["corp_name", "industry", "rd_score", "debt_score",
                  "rag_score", "total_score"]].head(10).to_string(index=False))

    return result


def _save_stage2_results(
    df: pd.DataFrame,
    product_description: str,
    product_category: str,
    year: int,
) -> None:
    """2단계 결과를 analysis_results 테이블에 저장 (upsert)."""
    from pipeline.db import init_db
    init_db()

    conn = get_connection()
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO analysis_results
                (corp_code, year, product_description, product_category,
                 rd_score, debt_score, rag_score, total_score, rag_detail, is_valid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(corp_code, year, product_description)
            DO UPDATE SET
                product_category = excluded.product_category,
                rd_score         = excluded.rd_score,
                debt_score       = excluded.debt_score,
                rag_score        = excluded.rag_score,
                total_score      = excluded.total_score,
                rag_detail       = excluded.rag_detail,
                analyzed_at      = CURRENT_TIMESTAMP
        """, (
            row["corp_code"],
            year,
            product_description,
            product_category,
            row.get("rd_score"),
            row.get("debt_score"),
            row.get("rag_score"),
            row.get("total_score"),
            row.get("rag_detail"),
        ))
    conn.commit()
    conn.close()
    print(f"  → analysis_results 저장 완료: {len(df)}개")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    from pipeline.filter import stage1_macro_filter

    print("=== 2단계 RAG 스코어링 테스트 (IT 기업 8개 — gate 검증 포함) ===")
    df1 = stage1_macro_filter(industry_category="IT/소프트웨어", min_deal_size=5_000_000)
    print(f"1단계 통과: {len(df1)}개 → 테스트용 8개만 사용\n")

    # 야놀자·젝시믹스 포함해서 gate가 제대로 걸러내는지 확인
    targets = ["야놀자", "젝시믹스", "카카오", "엔씨소프트", "더존비즈온", "와이즈에이아이", "비바리퍼블리카", "이노그리드"]
    test_df = df1[df1["corp_name"].isin(targets)].copy()
    if len(test_df) < 3:
        test_df = df1.head(8)

    result = run_stage2(
        stage1_df=test_df,
        product_category="AI/데이터 솔루션",
        product_description="기업 내부 데이터를 분석하여 의사결정을 자동화하는 AI 플랫폼. 비정형 데이터 처리 및 실시간 인사이트 제공.",
        top_n=8,
    )
    print("\n[최종 선별 결과]")
    print(result[["corp_name", "rd_score", "debt_score", "rag_score", "total_score"]].to_string(index=False))
