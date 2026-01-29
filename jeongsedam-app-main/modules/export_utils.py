# modules/export_utils.py
import io
import json
import zipfile
from datetime import datetime

import streamlit as st

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


# =========================
# PDF (한글 절대 안 깨지는 방식)
# =========================
def make_pdf(result: dict) -> bytes:
    buffer = io.BytesIO()

    # ✅ CID 한글 폰트 (ReportLab 내장)
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "HYSMyeongJo-Medium"
    styles["Title"].fontName = "HYSMyeongJo-Medium"

    story = []

    # 표지
    story.append(Paragraph("<b>정세담 퍼포먼스 결과</b>", styles["Title"]))
    story.append(Paragraph(
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["Normal"]
    ))
    story.append(PageBreak())

    # 섹션별 출력
    for section, content in result.items():
        story.append(Paragraph(f"<b>{section.upper()}</b>", styles["Title"]))

        if isinstance(content, (dict, list)):
            text = json.dumps(content, ensure_ascii=False, indent=2)
        else:
            text = str(content)

        # JSON 그대로 출력 (깨짐 없음)
        for line in text.split("\n"):
            story.append(Paragraph(line.replace("<", "&lt;").replace(">", "&gt;"), styles["Normal"]))

        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# =========================
# ZIP (항목별 구조화)
# =========================
def make_zip(result: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        zf.writestr(
            "result_full.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )

        for k, v in result.items():
            zf.writestr(
                f"{k}/{k}.json",
                json.dumps(v, ensure_ascii=False, indent=2)
                if isinstance(v, (dict, list)) else str(v)
            )

        zf.writestr(
            "meta.txt",
            f"exported_at={datetime.now().isoformat()}"
        )

    buf.seek(0)
    return buf.read()


# =========================
# Streamlit 버튼
# =========================
def render_download_buttons(result: dict):
    if not isinstance(result, dict):
        st.warning("다운로드할 데이터가 없습니다.")
        return

    st.markdown("## ⬇️ 결과 다운로드")

    zip_bytes = make_zip(result)
    st.download_button(
        "📦 ZIP 다운로드 (전체 데이터)",
        zip_bytes,
        file_name="performance_result.zip",
        mime="application/zip",
        use_container_width=True
    )

    try:
        pdf_bytes = make_pdf(result)
        st.download_button(
            "📄 PDF 다운로드 (한글 완벽)",
            pdf_bytes,
            file_name="performance_result.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    except Exception as e:
        st.error("PDF 생성 실패")
        st.code(str(e))
