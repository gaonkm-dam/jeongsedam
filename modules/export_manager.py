import io
import json
import zipfile
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def create_pdf_report(policy_data: Dict[str, Any], analysis_data: Dict[str, Any]) -> bytes:
    """
    정책 보고서 PDF 생성 (한글 지원)
    """
    buffer = io.BytesIO()
    
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )
    
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "HYSMyeongJo-Medium"
    styles["Normal"].fontSize = 10
    styles["Normal"].leading = 14
    
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontName="HYSMyeongJo-Medium",
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontName="HYSMyeongJo-Medium",
        fontSize=14,
        spaceAfter=12
    )
    
    story = []
    
    story.append(Paragraph("정세담 정책 프로그램", title_style))
    story.append(Paragraph("정책 분석 및 실행 보고서", styles["Normal"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}", styles["Normal"]))
    story.append(PageBreak())
    
    story.append(Paragraph("1. 정책 개요", heading_style))
    story.append(Paragraph(f"정책명: {policy_data.get('title', '')}", styles["Normal"]))
    story.append(Paragraph(f"카테고리: {policy_data.get('category', '')}", styles["Normal"]))
    story.append(Paragraph(f"대상: {policy_data.get('target_audience', '')}", styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"설명: {policy_data.get('description', '')}", styles["Normal"]))
    story.append(PageBreak())
    
    if "policy_planning" in analysis_data:
        planning = analysis_data["policy_planning"]
        story.append(Paragraph("2. 정책 기획", heading_style))
        story.append(Paragraph(f"목표: {planning.get('objective', '')}", styles["Normal"]))
        story.append(Spacer(1, 12))
        
        strategies = planning.get("key_strategies", [])
        if strategies:
            story.append(Paragraph("핵심 전략:", styles["Normal"]))
            for idx, strategy in enumerate(strategies, 1):
                story.append(Paragraph(f"{idx}. {strategy}", styles["Normal"]))
        story.append(PageBreak())
    
    if "execution_plan" in analysis_data:
        execution = analysis_data["execution_plan"]
        story.append(Paragraph("3. 실행 계획", heading_style))
        
        action_items = execution.get("action_items", [])
        if action_items:
            story.append(Paragraph("실행 항목:", styles["Normal"]))
            for item in action_items:
                story.append(Paragraph(
                    f"• {item.get('phase', '')}: {item.get('action', '')}",
                    styles["Normal"]
                ))
        story.append(PageBreak())
    
    if "marketing_materials" in analysis_data:
        marketing = analysis_data["marketing_materials"]
        story.append(Paragraph("4. 마케팅 자료", heading_style))
        story.append(Paragraph(f"슬로건: {marketing.get('slogan', '')}", styles["Normal"]))
        story.append(Paragraph(f"태그라인: {marketing.get('tagline', '')}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"{marketing.get('elevator_pitch', '')}", styles["Normal"]))
        story.append(PageBreak())
    
    if "performance_metrics" in analysis_data:
        metrics = analysis_data["performance_metrics"]
        story.append(Paragraph("5. 성과 지표", heading_style))
        
        kpi_framework = metrics.get("kpi_framework", [])
        if kpi_framework:
            for kpi in kpi_framework:
                story.append(Paragraph(
                    f"• {kpi.get('metric', '')}: {kpi.get('measurement_method', '')}",
                    styles["Normal"]
                ))
        story.append(PageBreak())
    
    story.append(Paragraph("6. 데이터 상세", heading_style))
    json_str = json.dumps(analysis_data, ensure_ascii=False, indent=2)
    for line in json_str.split("\n")[:100]:
        clean_line = line.replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(clean_line, styles["Normal"]))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

def create_zip_export(
    policy_data: Dict[str, Any],
    analysis_data: Dict[str, Any],
    images: List[bytes] = None,
    video_prompts: List[str] = None
) -> bytes:
    """
    모든 자료를 ZIP으로 압축
    """
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "policy_info.json",
            json.dumps(policy_data, ensure_ascii=False, indent=2)
        )
        
        zf.writestr(
            "analysis_full.json",
            json.dumps(analysis_data, ensure_ascii=False, indent=2)
        )
        
        if "policy_planning" in analysis_data:
            zf.writestr(
                "01_planning.json",
                json.dumps(analysis_data["policy_planning"], ensure_ascii=False, indent=2)
            )
        
        if "execution_plan" in analysis_data:
            zf.writestr(
                "02_execution.json",
                json.dumps(analysis_data["execution_plan"], ensure_ascii=False, indent=2)
            )
        
        if "marketing_materials" in analysis_data:
            zf.writestr(
                "03_marketing.json",
                json.dumps(analysis_data["marketing_materials"], ensure_ascii=False, indent=2)
            )
        
        if "content_briefs" in analysis_data:
            briefs = analysis_data["content_briefs"]
            
            if "image_brief_1" in briefs:
                zf.writestr(
                    "04_image_brief_1.json",
                    json.dumps(briefs["image_brief_1"], ensure_ascii=False, indent=2)
                )
            
            if "image_brief_2" in briefs:
                zf.writestr(
                    "04_image_brief_2.json",
                    json.dumps(briefs["image_brief_2"], ensure_ascii=False, indent=2)
                )
            
            if "video_brief" in briefs:
                zf.writestr(
                    "05_video_brief.json",
                    json.dumps(briefs["video_brief"], ensure_ascii=False, indent=2)
                )
        
        if "performance_metrics" in analysis_data:
            zf.writestr(
                "06_kpi.json",
                json.dumps(analysis_data["performance_metrics"], ensure_ascii=False, indent=2)
            )
        
        if images:
            for idx, img_bytes in enumerate(images, 1):
                zf.writestr(f"images/image_{idx}.png", img_bytes)
        
        if video_prompts:
            for idx, prompt in enumerate(video_prompts, 1):
                zf.writestr(f"video_prompts/prompt_{idx}.txt", prompt)
        
        zf.writestr(
            "README.txt",
            f"""정세담 정책 프로그램 - 내보내기 파일

생성일시: {datetime.now().isoformat()}
정책명: {policy_data.get('title', '')}
카테고리: {policy_data.get('category', '')}

폴더 구조:
- policy_info.json: 정책 기본 정보
- analysis_full.json: 전체 분석 데이터
- 01_planning.json: 정책 기획
- 02_execution.json: 실행 계획
- 03_marketing.json: 마케팅 자료
- 04_image_brief_*.json: 이미지 제작 브리프
- 05_video_brief.json: 영상 제작 브리프
- 06_kpi.json: 성과 지표
- images/: 생성된 이미지 파일
- video_prompts/: 영상 프롬프트
"""
        )
    
    buffer.seek(0)
    return buffer.read()
