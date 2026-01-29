import os
from typing import Dict, List

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DB_PATH = "data/policies.db"

POLICY_CATEGORIES = [
    "환경(대기/미세먼지)",
    "안전(교통/사고)",
    "ESG(순환/폐기물)",
    "교육(학교/청소년)",
    "복지(취약계층)",
    "도시(청소/질서)",
    "산업(기업/규제)",
    "문화/관광",
    "교통/주차",
    "주거/건설"
]

TARGET_AUDIENCES = {
    "시민": {
        "tone": "친근하고 이해하기 쉬운",
        "focus": "일상 생활 혜택, 실생활 변화"
    },
    "청년": {
        "tone": "트렌디하고 직관적인",
        "focus": "기회 확대, 미래 전망"
    },
    "노인": {
        "tone": "친절하고 따뜻한",
        "focus": "안전, 편의성, 접근성"
    },
    "학부모": {
        "tone": "신뢰감 있고 구체적인",
        "focus": "자녀 안전, 교육 효과"
    },
    "기업": {
        "tone": "전문적이고 효율적인",
        "focus": "비용 절감, 규제 완화, ROI"
    },
    "지자체 공무원": {
        "tone": "체계적이고 실무적인",
        "focus": "실행 가능성, 예산, 법적 근거"
    },
    "의회/의원": {
        "tone": "설득적이고 근거 중심",
        "focus": "정책 효과, 국민 체감, 성과 지표"
    }
}

VIDEO_PLATFORMS = {
    "Sora": "https://sora.openai.com",
    "Runway": "https://runwayml.com",
    "Pika": "https://pika.art",
    "Luma Dream Machine": "https://lumalabs.ai"
}

IMAGE_SIZES = ["1024x1024", "1024x1792", "1792x1024"]
VIDEO_DURATIONS = ["10초", "20초", "30초", "60초"]

CONTENT_PACKAGES = {
    "A 마케팅": ["이미지 2장", "영상 1개", "홍보 문구 3종"],
    "B 정책 설명": ["정책 요약", "PPT 구성", "FAQ"],
    "C 풀 패키지": ["이미지 4장", "영상 2개", "홍보 문구 5종", "정책 문서", "PPT", "성과 지표"]
}

DEFAULT_IMAGE_STYLE = """
Professional documentary photography, ultra-realistic, photojournalistic style.

Location: Modern South Korea (Seoul, Busan, or other major Korean cities).
Architecture: Contemporary Korean buildings, clean streets, realistic urban/suburban settings.
People: Natural Korean faces with accurate facial features, realistic expressions.
DO NOT distort faces - maintain natural human proportions and features.
Lighting: Natural daylight, soft shadows, professional photography lighting.
Color palette: Natural, slightly desaturated, clean and modern aesthetic.
Atmosphere: Authentic everyday Korean life, genuine moments.

Technical requirements:
- High resolution, sharp focus on main subjects
- Proper depth of field
- Realistic skin tones (Korean complexion)
- Natural body proportions
- Clear, undistorted facial features
- Professional color grading

Forbidden elements:
- NO text, logos, signs with readable text
- NO distorted or warped faces
- NO unrealistic proportions
- NO stock photo feel
- NO overly posed or artificial scenes
- NO generic Asian stereotypes

Style reference: Korean documentary photography, modern Korean cinema aesthetics.
"""

DEFAULT_VIDEO_STYLE = """
Cinematic documentary style, 4K quality.
Smooth camera movements, professional color grading.
Natural ambient sounds with subtle background music.
Korean language subtitles, clean sans-serif font.
Transitions: smooth cuts, no flashy effects.
Authentic South Korean locations and people.
"""
