import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5"

DOC_TYPES = {
    "cold_email": "콜드 메일",
    "proposal":   "제안서 1-pager",
    "briefing":   "미팅 브리핑",
}

RECIPIENT_ROLES = ["대표이사", "CTO / 기술책임자", "구매팀장", "IT 담당자"]

_RAG_LABEL = {
    "problem_fit":          "문제 일치도",
    "digital_willingness":  "디지털 전환 의지",
    "investment_direction": "신사업 투자 방향",
    "external_adoption":    "외부 솔루션 도입 이력",
    "decision_structure":   "의사결정 구조",
}


def generate_report(
    corp_name: str,
    revenue: int,
    employees: int,
    industry: str,
    market_type: str,
    total_score: float,
    rd_score: float,
    debt_score: float,
    rag_score: float,
    rag_detail: dict,
    product_description: str,
    product_category: str,
    doc_type: str,
    recipient_role: str,
    emphasis: str = "",
) -> str:
    """Claude를 사용해 영업 문서를 생성합니다."""
    rev_str = (f"{revenue // 100_000_000:,}억 원" if revenue >= 100_000_000
               else (f"{revenue:,}원" if revenue else "-"))
    emp_str = f"{employees:,}명" if employees else "미공시"

    rag_lines = "\n".join(
        f"- {_RAG_LABEL.get(k, k)}: {v.get('score', 0)}/10 — {v.get('reason', '')}"
        for k, v in rag_detail.items()
        if isinstance(v, dict) and "score" in v
    )

    prompts = {
        "cold_email": f"""당신은 B2B 영업 전문가입니다. 다음 정보를 바탕으로 콜드 메일을 작성하세요.

[타깃 기업]
기업명: {corp_name} | 업종: {industry} | 시장: {market_type}
매출: {rev_str} | 임직원: {emp_str} | 수신자: {recipient_role}

[RAG 분석 (종합 {total_score:.1f}점)]
{rag_lines}

[우리 제품]
카테고리: {product_category}
설명: {product_description}
강조 포인트: {emphasis or "없음"}

지시사항:
1. 제목 1줄 (구체적이고 관심을 끄는)
2. 본문 150~200자 한국어
   - {corp_name} 맞춤 오프닝 (RAG 근거 활용)
   - 문제 제기 → 솔루션 한 줄 → 기대 효과
   - CTA: "15분 짧은 미팅을 요청드립니다"
3. **, *, #, [] 등 마크다운 기호 절대 사용 금지 — 순수 텍스트만 작성
형식: 제목: [제목]\n\n[본문]""",

        "proposal": f"""당신은 B2B 영업 전문가입니다. 제안서 1-pager 아웃라인을 작성하세요.

[타깃 기업]
기업명: {corp_name} | 업종: {industry}
매출: {rev_str} | 임직원: {emp_str} | 수신자: {recipient_role}

[RAG 분석]
{rag_lines}

[우리 제품]
{product_category}: {product_description}
강조 포인트: {emphasis or "없음"}

형식 (마크다운):
## 1. 문제 정의
(2~3줄 — {corp_name} 맞춤, investment_direction + problem_fit 근거)

## 2. 우리 솔루션
(3~4줄 — product_description 요약, {corp_name} 특화)

## 3. 왜 지금인가
(2줄 — digital_willingness 근거 활용)

## 4. 기대 효과
(수치 포함 2~3줄)

## 5. 다음 단계
(파일럿 / 데모 / 견적 중 적합한 1개 제안)""",

        "briefing": f"""당신은 B2B 영업 전문가입니다. 영업 담당자용 미팅 브리핑을 작성하세요.

[타깃 기업]
기업명: {corp_name} | 업종: {industry} | 시장: {market_type}
매출: {rev_str} | 임직원: {emp_str} | 수신자: {recipient_role}

[스코어 요약]
종합: {total_score:.1f}점 | R&D: {rd_score:.1f}/10 | 재무안정성: {debt_score:.1f}/10

[RAG 분석]
{rag_lines}

[우리 제품]
{product_category}: {product_description}

형식 (마크다운):
## 기업 한줄 요약
(매출·인원·핵심 사업 1줄)

## 핵심 기회
(decision_structure + external_adoption 기반 2~3줄)

## 예상 반론 & 답변
- "반론 1" → 답변
- "반론 2" → 답변
- "반론 3" → 답변

## 재무 주의 포인트
(debt_score {debt_score:.1f}점 기반 계약 구조 제안 1~2줄)""",
    }

    prompt = prompts.get(doc_type, prompts["cold_email"])

    try:
        resp = claude.messages.create(
            model=MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except anthropic.BadRequestError as e:
        if "credit" in str(e).lower() or "billing" in str(e).lower():
            raise RuntimeError(f"CREDIT_EXHAUSTED:{e}") from e
        raise
