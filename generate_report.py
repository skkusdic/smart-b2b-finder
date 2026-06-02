import sys
sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

# 한글 폰트 등록
pdfmetrics.registerFont(TTFont("Malgun", "C:/Windows/Fonts/malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunBold", "C:/Windows/Fonts/malgunbd.ttf"))

# 스타일 정의
def styles():
    return {
        "title": ParagraphStyle("title", fontName="MalgunBold", fontSize=22,
                                leading=30, textColor=colors.HexColor("#1a3a5c"),
                                spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", fontName="Malgun", fontSize=11,
                                   textColor=colors.HexColor("#555555"), spaceAfter=16),
        "h1": ParagraphStyle("h1", fontName="MalgunBold", fontSize=15,
                             textColor=colors.HexColor("#1a3a5c"),
                             spaceBefore=18, spaceAfter=8,
                             borderPad=4),
        "h2": ParagraphStyle("h2", fontName="MalgunBold", fontSize=12,
                             textColor=colors.HexColor("#2e6da4"),
                             spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("body", fontName="Malgun", fontSize=10,
                               leading=16, spaceAfter=6),
        "bullet": ParagraphStyle("bullet", fontName="Malgun", fontSize=10,
                                 leading=16, leftIndent=14, spaceAfter=4),
        "code": ParagraphStyle("code", fontName="Malgun", fontSize=9,
                               leading=14, leftIndent=14, textColor=colors.HexColor("#333333"),
                               backColor=colors.HexColor("#f4f4f4"), spaceAfter=6),
        "tag_green": ParagraphStyle("tag_green", fontName="MalgunBold", fontSize=9,
                                    textColor=colors.white,
                                    backColor=colors.HexColor("#27ae60")),
        "tag_orange": ParagraphStyle("tag_orange", fontName="MalgunBold", fontSize=9,
                                     textColor=colors.white,
                                     backColor=colors.HexColor("#e67e22")),
        "tag_red": ParagraphStyle("tag_red", fontName="MalgunBold", fontSize=9,
                                  textColor=colors.white,
                                  backColor=colors.HexColor("#e74c3c")),
        "caption": ParagraphStyle("caption", fontName="Malgun", fontSize=9,
                                  textColor=colors.HexColor("#777777"), spaceAfter=4),
    }

S = styles()

def divider(color="#2e6da4", thickness=1):
    return HRFlowable(width="100%", thickness=thickness,
                      color=colors.HexColor(color), spaceAfter=8, spaceBefore=4)

def section_header(text):
    return [
        divider("#1a3a5c", 2),
        Paragraph(text, S["h1"]),
    ]

def checklist_table(rows):
    """rows: [(항목, 상태)] 상태: done / progress / pending"""
    color_map = {"done": "#27ae60", "progress": "#e67e22", "pending": "#aaaaaa"}
    label_map = {"done": "완료", "progress": "진행중", "pending": "대기"}
    data = [["항목", "상태"]]
    for item, status in rows:
        data.append([
            Paragraph(item, S["body"]),
            Paragraph(label_map[status], ParagraphStyle(
                "s", fontName="MalgunBold", fontSize=9,
                textColor=colors.white,
                backColor=colors.HexColor(color_map[status]),
                alignment=1
            ))
        ])
    t = Table(data, colWidths=[130*mm, 30*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MalgunBold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
    ]))
    return t

def info_table(rows):
    """rows: [(key, value)]"""
    data = [[Paragraph(f"<b>{k}</b>", S["body"]),
             Paragraph(v, S["body"])] for k, v in rows]
    t = Table(data, colWidths=[45*mm, 115*mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#f0f4f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t

def arch_table():
    data = [
        ["단계", "모듈", "역할", "주차"],
        ["사용자 입력", "app.py", "산업군, 리소스 제약, 타깃 명단 입력", "4주차"],
        ["1차 거시 필터", "pipeline/filter.py", "산업군 + 최소 거래 규모 → ~200개", "1주차"],
        ["2차 재무 필터", "pipeline/filter.py", "R&D 비중 + 재무 건전성 → ~30개", "2주차 전"],
        ["3차 Claude RAG", "agents/analyzer.py", "Pain point 매칭 + 혁신수용도 라벨링", "2주차"],
        ["MILP 최적화", "optimizer/milp.py", "제약 조건 내 기대가치 최대화 → Top 3", "3주차"],
        ["결과 출력", "app.py", "우선순위 리스트 + Why-Not 리포트", "4주차"],
    ]
    t = Table(data, colWidths=[30*mm, 38*mm, 72*mm, 18*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MalgunBold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Malgun"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build_pdf(path):
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )

    story = []

    # ── 표지 ──────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("Smart B2B Finder for Startups", S["title"]))
    story.append(Paragraph("1주차 진행 현황 보고서", S["subtitle"]))
    story.append(info_table([
        ("작성자", "이정원"),
        ("작성일", datetime.now().strftime("%Y-%m-%d")),
        ("현재 주차", "1주차 (05/21 ~ 05/27)"),
        ("GitHub", "https://github.com/skkusdic/smart-b2b-finder"),
        ("로컬 경로", "C:/Users/lexy/Desktop/SDIC/smart-b2b-finder"),
    ]))
    story.append(Spacer(1, 6*mm))

    # ── 1. 프로젝트 개요 ──────────────────────────────────
    story += section_header("1. 프로젝트 개요")
    story.append(Paragraph(
        "DART 공시 재무 데이터 + Claude RAG 분석 + MILP 최적화를 결합하여 "
        "B2B 스타트업의 영업 타깃 우선순위를 자동 도출하는 Multi-Agent 시스템.",
        S["body"]
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("4주 타임라인", S["h2"]))
    timeline = [
        ["주차", "기간", "목표", "상태"],
        ["1주차", "05/21~05/27", "DART 수집 + SQLite DB + 1차 필터링", "진행중"],
        ["2주차", "05/28~06/03", "Claude RAG 분석 파이프라인 + 스코어링", "대기"],
        ["3주차", "06/18~06/24", "MILP 최적화 알고리즘 구현", "대기"],
        ["4주차", "06/25~07/01", "Streamlit UI + 배포", "대기"],
    ]
    tl = Table(timeline, colWidths=[18*mm, 28*mm, 94*mm, 18*mm])
    tl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MalgunBold"),
        ("FONTNAME", (0, 1), (-1, -1), "Malgun"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#fff3cd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tl)
    story.append(Spacer(1, 4*mm))

    # ── 2. 시스템 아키텍처 ────────────────────────────────
    story += section_header("2. 시스템 아키텍처 (필터링 파이프라인)")
    story.append(Paragraph(
        "깔때기(Funnel) 방식으로 3단계에 걸쳐 2500개 상장사를 Top 3으로 압축합니다. "
        "1차·2차는 SQL 기반 오프라인 필터, 3차는 Claude API 실시간 분석입니다.",
        S["body"]
    ))
    story.append(Spacer(1, 2*mm))
    story.append(arch_table())
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "※ 현재 filter.py의 하드코딩 기준(매출 5억/부채비율 200%/임직원 30명)은 "
        "임시 설계이며, 2주차 전에 '산업군 + R&D 비중' 기반으로 재설계 예정.",
        S["caption"]
    ))

    # ── 3. 폴더 구조 ──────────────────────────────────────
    story += section_header("3. 프로젝트 폴더 구조")
    story.append(Paragraph(
        "smart-b2b-finder/<br/>"
        "├── .env &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← API 키 (GitHub 업로드 금지)<br/>"
        "├── .gitignore<br/>"
        "├── CLAUDE.md &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← 프로젝트 규칙 문서<br/>"
        "├── requirements.txt<br/>"
        "├── pipeline/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← 1주차 핵심<br/>"
        "│&nbsp;&nbsp;&nbsp;├── db.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← SQLite 스키마<br/>"
        "│&nbsp;&nbsp;&nbsp;├── dart_collector.py ← DART API 수집<br/>"
        "│&nbsp;&nbsp;&nbsp;└── filter.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← 1차 룰베이스 필터<br/>"
        "├── agents/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← 2주차 구현 예정<br/>"
        "├── optimizer/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← 3주차 구현 예정<br/>"
        "└── app.py &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "← 4주차 Streamlit UI",
        S["code"]
    ))

    # ── 4. 1주차 작업 내역 ────────────────────────────────
    story += section_header("4. 1주차 작업 내역 (체크리스트)")
    story.append(checklist_table([
        ("GitHub repo 생성 (skkusdic/smart-b2b-finder)", "done"),
        ("로컬 폴더 구조 생성 및 remote 연결", "done"),
        (".env 파일 생성 (DART / Anthropic API 키 입력)", "done"),
        (".gitignore 작성 (.env, *.db 포함)", "done"),
        ("requirements.txt 작성 + pip install (pulp 포함)", "done"),
        ("CLAUDE.md 작성 후 GitHub commit", "done"),
        ("pipeline/db.py — SQLite 스키마 설계 및 초기화 확인", "done"),
        ("pipeline/dart_collector.py — DART API 직접 호출 방식으로 재설계", "done"),
        ("50개 테스트 수집 → 44개 저장 정상 확인", "done"),
        ("전체 ~2500개 기업 수집 실행 (백그라운드 진행중)", "progress"),
        ("pipeline/filter.py — 1차 필터링 실행 및 결과 확인", "pending"),
        ("전체 GitHub push (최종)", "pending"),
    ]))
    story.append(Spacer(1, 3*mm))

    # ── 5. 주요 기술 결정 사항 ────────────────────────────
    story += section_header("5. 주요 기술 결정 사항")

    story.append(Paragraph("5-1. DART 수집 방식 변경", S["h2"]))
    story.append(Paragraph(
        "초기 dart-fss 라이브러리의 <b>get_corp_list()</b> 방식은 상장폐지 기업이 포함되어 "
        "전체 스킵(0개 저장) 문제가 발생했습니다. "
        "DART Open API의 <b>공시 목록(list.json)</b>을 직접 호출하는 방식으로 재설계하여 "
        "2024년 사업보고서를 실제로 제출한 현존 상장사만 수집하도록 수정했습니다.",
        S["body"]
    ))
    story.append(Paragraph("변경 전 → 후", S["caption"]))
    story.append(Paragraph(
        "변경 전: dart.get_corp_list()[:50] → stock_code 필터 → extract_fs() → 0개 저장<br/>"
        "변경 후: DART list.json(사업보고서 공시) → fnlttSinglAcnt.json → company.json → 44/50개 저장",
        S["code"]
    ))

    story.append(Paragraph("5-2. DART API 3개월 제한 대응", S["h2"]))
    story.append(Paragraph(
        "공시 목록 조회 시 corp_code 없이 검색하면 <b>3개월 이내</b>만 허용됩니다. "
        "2024년 사업보고서(2025년 1~4월 제출)를 모두 수집하기 위해 "
        "<b>분기별 분할 요청</b>(1~3월 / 4~6월)으로 해결했습니다.",
        S["body"]
    ))

    story.append(Paragraph("5-3. 1차 필터링 설계 재검토 필요", S["h2"]))
    story.append(Paragraph(
        "현재 filter.py는 매출 5억 / 부채비율 200% / 임직원 30명을 하드코딩했으나, "
        "제안서 원문에는 구체적 수치가 명시되어 있지 않습니다. "
        "제안서의 핵심 전략('깔때기 필터링')과 rough 노트('R&D 투자 증가' 기준)를 반영하여 "
        "2주차 전 아래와 같이 재설계 예정입니다.",
        S["body"]
    ))
    filter_plan = [
        ["단계", "기준", "목표 결과"],
        ["1단계 (거시)", "산업군 매칭 + 사용자 입력 최소 거래 규모", "~200개"],
        ["2단계 (재무)", "R&D 비중 + 재무 건전성 (낮은 하한)", "~30개"],
        ["3단계 (Claude)", "Pain point 매칭 + 혁신수용도 판단", "Top 3~10개"],
    ]
    fp = Table(filter_plan, colWidths=[28*mm, 100*mm, 30*mm])
    fp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e6da4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MalgunBold"),
        ("FONTNAME", (0, 1), (-1, -1), "Malgun"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8f9fa"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(fp)

    # ── 6. Input / Output 설계 현황 ───────────────────────
    story += section_header("6. Input / Output 설계 현황")

    story.append(Paragraph("확정된 Input 항목", S["h2"]))
    story.append(Paragraph("· 산업 카테고리 (예: SaaS, 로보틱스)", S["bullet"]))
    story.append(Paragraph("· 핵심 기술 키워드 (예: 인터페이스 디자인)", S["bullet"]))
    story.append(Paragraph("· 주요 제공 가치 (예: 인건비 절감, 생산 속도 향상)", S["bullet"]))
    story.append(Paragraph("· 최소 거래 규모 필터 (사용자 입력값, 하드코딩 X)", S["bullet"]))
    story.append(Paragraph("· 리소스 제약 조건 — AM 슬롯 수, 개발 가용 시간 (MILP용)", S["bullet"]))
    story.append(Paragraph("· 공략 타깃 리스트 또는 신규 시장 탐색 키워드 (모드 선택)", S["bullet"]))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("확정된 Output 항목", S["h2"]))
    story.append(Paragraph("· 맞춤형 영업 우선순위 리스트 — 기대가치 Top 3 기업", S["bullet"]))
    story.append(Paragraph("· 고객 성향 라벨링 — 혁신수용자 / 실용주의자", S["bullet"]))
    story.append(Paragraph("· 맞춤형 제안서 초안 및 레퍼런스 가이드", S["bullet"]))
    story.append(Paragraph("· Why-Not 리포트 — 탈락 기업 배제 사유 설명 (XAI)", S["bullet"]))

    # ── 7. 환경 설정 ──────────────────────────────────────
    story += section_header("7. 환경 설정")
    story.append(info_table([
        ("Python", "3.11"),
        ("주요 패키지", "dart-fss, anthropic, streamlit, pulp, pandas, python-dotenv, reportlab"),
        ("DB", "SQLite (b2b_finder.db) — .gitignore로 GitHub 업로드 제외"),
        ("API 키", ".env 파일 관리 — DART_API_KEY, ANTHROPIC_API_KEY"),
        ("Claude 모델", "claude-haiku-4-5 (API 호출 시 고정)"),
    ]))

    # ── 8. 다음 단계 ──────────────────────────────────────
    story += section_header("8. 다음 단계 (1주차 완료 후)")
    story.append(Paragraph("· 전체 수집 완료 확인 → DB 적재 기업 수 확인", S["bullet"]))
    story.append(Paragraph("· filter.py 재설계 (산업군 + R&D 비중 기반 3단계 깔때기)", S["bullet"]))
    story.append(Paragraph("· 필터링 결과 확인 → 통과 기업 수 30~100개 목표", S["bullet"]))
    story.append(Paragraph("· 최종 GitHub push 후 1주차 마무리", S["bullet"]))
    story.append(Paragraph("· 2주차: Claude RAG 분석 파이프라인 + 스코어링 설계 시작", S["bullet"]))
    story.append(Spacer(1, 6*mm))
    story.append(divider("#1a3a5c", 1))
    story.append(Paragraph(
        f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        "Smart B2B Finder for Startups — SKKU SDIC 개인 프로젝트",
        S["caption"]
    ))

    doc.build(story)
    print(f"PDF 생성 완료: {path}")


if __name__ == "__main__":
    output_path = "C:/Users/lexy/Desktop/SDIC/smart-b2b-finder/1주차_진행현황_보고서.pdf"
    build_pdf(output_path)
