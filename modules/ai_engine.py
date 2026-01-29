import os
import json
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=api_key)

def parse_json_response(text: str) -> Optional[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except:
        return None

def generate_policy_analysis(
    title: str,
    category: str,
    target_audience: str,
    description: str,
    keywords: str = "",
    constraints: str = "",
    model: str = "gpt-4o"
) -> Tuple[Optional[Dict], str]:
    
    prompt = f"""
당신은 정세담 정책 자동화 시스템의 AI입니다.
정책의 기획부터 실행, 홍보, 성과관리까지 전체 프로세스를 설계합니다.

[입력 정보]
정책 제목: {title}
정책 카테고리: {category}
대상: {target_audience}
정책 설명: {description}
강조 키워드: {keywords}
제약 조건: {constraints}

[출력 규칙]
- 반드시 JSON 형식으로만 출력
- 한국 현실에 맞는 실행 가능한 내용
- 과장 금지, 측정 가능한 지표 사용
- 대상에 맞는 톤과 메시지

[JSON 스키마]
{{
  "policy_planning": {{
    "objective": "정책 목표 (3-5문장)",
    "target_analysis": "대상 분석 (니즈, 특성, 접근법 3-5문장)",
    "key_strategies": ["핵심 전략 5-8개"],
    "expected_outcomes": ["기대 효과 5-7개"],
    "timeline": {{
      "preparation": "준비 단계 내용",
      "pilot": "시범 운영 내용",
      "expansion": "확대 적용 내용"
    }}
  }},
  
  "execution_plan": {{
    "action_items": [
      {{
        "phase": "단계명",
        "action": "실행 내용",
        "responsible": "담당 주체",
        "timeline": "소요 기간"
      }}
    ],
    "resources_needed": {{
      "budget_range": "예산 범위 (구체적 금액 대신 범주)",
      "personnel": "필요 인력",
      "infrastructure": "필요 인프라"
    }},
    "risk_management": [
      {{
        "risk": "리스크 항목",
        "impact": "영향도",
        "mitigation": "완화 방안"
      }}
    ]
  }},
  
  "communication_strategy": {{
    "key_messages": ["핵심 메시지 5-8개"],
    "channels": [
      {{
        "channel": "채널명",
        "content_type": "콘텐츠 형식",
        "frequency": "발행 주기"
      }}
    ],
    "target_specific_messages": {{
      "citizens": "시민 대상 메시지",
      "youth": "청년 대상 메시지",
      "elderly": "노인 대상 메시지",
      "parents": "학부모 대상 메시지"
    }}
  }},
  
  "content_briefs": {{
    "image_brief_1": {{
      "concept": "이미지 컨셉 (5-7문장)",
      "scene_description": "장면 상세 묘사 (10-15문장)",
      "visual_style": "비주얼 스타일 (촬영 기법, 조명, 색감)",
      "key_message": "전달할 핵심 메시지"
    }},
    "image_brief_2": {{
      "concept": "이미지 컨셉 (5-7문장)",
      "scene_description": "장면 상세 묘사 (10-15문장)",
      "visual_style": "비주얼 스타일 (촬영 기법, 조명, 색감)",
      "key_message": "전달할 핵심 메시지"
    }},
    "video_brief": {{
      "duration": "영상 길이",
      "narrative_arc": "스토리 구조 (5-8문장)",
      "scenes": [
        {{
          "timestamp": "시간대",
          "scene": "장면 내용",
          "visuals": "비주얼 요소",
          "audio": "오디오 (내레이션/음악/효과음)",
          "message": "전달 메시지"
        }}
      ],
      "style_guide": "영상 스타일 가이드",
      "call_to_action": "행동 유도 문구"
    }}
  }},
  
  "marketing_materials": {{
    "slogan": "슬로건 (20-30자)",
    "tagline": "태그라인 (40-60자)",
    "elevator_pitch": "엘리베이터 피치 (150-200자)",
    "press_release": "보도자료 형식 (300-500자)",
    "social_media_posts": [
      {{
        "platform": "플랫폼",
        "content": "게시물 내용",
        "hashtags": ["해시태그"]
      }}
    ],
    "faq": [
      {{
        "question": "자주 묻는 질문",
        "answer": "답변"
      }}
    ]
  }},
  
  "performance_metrics": {{
    "kpi_framework": [
      {{
        "category": "지표 카테고리",
        "metric": "측정 항목",
        "measurement_method": "측정 방법",
        "target_range": "목표 범위 (구간/추이)",
        "data_source": "데이터 출처"
      }}
    ],
    "success_criteria": ["성공 기준 5-7개"],
    "monitoring_plan": {{
      "daily": "일간 모니터링 항목",
      "weekly": "주간 모니터링 항목",
      "monthly": "월간 모니터링 항목"
    }},
    "improvement_triggers": ["개선이 필요한 시점을 알리는 지표 5-7개"]
  }},
  
  "stakeholder_management": {{
    "stakeholders": [
      {{
        "group": "이해관계자 그룹",
        "interests": "관심사",
        "engagement_strategy": "소통 전략"
      }}
    ],
    "objection_handling": [
      {{
        "objection": "예상 반대 의견",
        "response": "대응 논리"
      }}
    ]
  }}
}}

위 스키마를 정확히 따라 JSON만 출력하세요.
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 정책 전문가입니다. 항상 JSON 형식으로만 응답합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        raw_text = response.choices[0].message.content
        parsed_data = parse_json_response(raw_text)
        
        if parsed_data:
            return parsed_data, raw_text
        
        retry_prompt = f"""
이전 응답이 올바른 JSON 형식이 아닙니다.
아래 내용을 완벽한 JSON으로 다시 출력해주세요.

{raw_text}
"""
        
        retry_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "JSON 형식으로만 응답합니다."},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        retry_text = retry_response.choices[0].message.content
        retry_parsed = parse_json_response(retry_text)
        
        return retry_parsed, retry_text
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def generate_image_prompt(brief: Dict[str, Any], style_override: str = "") -> str:
    concept = brief.get("concept", "")
    scene = brief.get("scene_description", "")
    style = brief.get("visual_style", "")
    message = brief.get("key_message", "")
    
    base_style = style_override if style_override else """
Professional documentary photography, photorealistic.
Location: Modern South Korea (Seoul, Busan, Incheon, or other Korean cities).
Architecture: Contemporary Korean buildings, clean urban environment.
People: Natural Korean individuals with realistic facial features and proportions.
CRITICAL: Maintain accurate facial anatomy - no distortion, warping, or unnatural features.
Faces must have proper proportions, clear features, and realistic expressions.
Skin tones: Natural Korean complexion with proper lighting.
Clothing: Contemporary Korean fashion, professional or casual depending on context.
Environment: Authentic Korean street scenes, offices, or public spaces.
Lighting: Natural daylight with soft shadows, professional photography standard.
Color: Natural palette, slightly desaturated for documentary feel.
Composition: Rule of thirds, professional framing.

Technical specifications:
- Sharp focus on subjects
- Proper depth of field
- Realistic human anatomy and proportions
- Natural expressions and postures
- High-quality photorealistic rendering

Strictly prohibited:
- NO text, Korean characters, or English letters visible in image
- NO distorted, warped, or malformed faces
- NO unnatural body proportions
- NO obvious AI artifacts
- NO generic stock photo aesthetics
"""
    
    prompt = f"""
{concept}

Scene description: {scene}

Visual style: {style}

{base_style}

Key message to convey: {message}

Important: Create realistic Korean people with natural, undistorted facial features.
No text or writing should appear anywhere in the image.
Focus on authentic Korean urban/suburban environment and genuine human expressions.
"""
    
    return prompt.strip()

def generate_video_prompt(brief: Dict[str, Any], duration: str = "20초") -> str:
    narrative = brief.get("narrative_arc", "")
    scenes = brief.get("scenes", [])
    style_guide = brief.get("style_guide", "")
    cta = brief.get("call_to_action", "")
    
    timeline_text = "\n\n".join([
        f"[{s.get('timestamp', '')}]\n"
        f"Scene: {s.get('scene', '')}\n"
        f"Visuals: {s.get('visuals', '')}\n"
        f"Audio: {s.get('audio', '')}\n"
        f"Message: {s.get('message', '')}"
        for s in scenes
    ])
    
    prompt = f"""
Cinematic documentary style, {duration} duration.
South Korea context, authentic locations and people.

Narrative: {narrative}

Timeline:
{timeline_text}

Style Guide: {style_guide}

Final CTA: {cta}

Professional color grading, smooth transitions.
Korean language subtitles, natural ambient sounds.
No English text on screen.
"""
    
    return prompt.strip()

def generate_video_prompts_3styles(brief: Dict[str, Any]) -> Dict[str, str]:
    """10초 영상 3가지 스타일 프롬프트 생성"""
    
    narrative = brief.get("narrative_arc", "")
    cta = brief.get("call_to_action", "")
    scenes = brief.get("scenes", [])
    
    # 기본 정보
    base_context = f"""
Duration: 10 seconds
Location: Modern South Korea
Language: Korean subtitles only
No English text visible
"""
    
    # 스타일 1: 다큐멘터리 (Documentary)
    style1 = f"""
[스타일 1: 다큐멘터리 리얼리즘]

{base_context}

Visual Style:
- Handheld camera feel, natural movements
- Realistic lighting, documentary aesthetic
- Authentic Korean street scenes and people
- Observational approach, fly-on-the-wall style
- Natural color grading with slight desaturation

Camera:
- Medium shots and close-ups
- Slight camera shake for realism
- Follow subjects naturally

Audio:
- Natural ambient sounds (traffic, voices, city sounds)
- Minimal background music
- Natural Korean dialogue or voice-over

Narrative: {narrative}

Mood: Authentic, grounded, trustworthy
Pacing: Steady, observational
Final Message: {cta}

Technical: 24fps, cinematic aspect ratio, professional documentary style
"""
    
    # 스타일 2: 시네마틱 (Cinematic)
    style2 = f"""
[스타일 2: 시네마틱 드라마]

{base_context}

Visual Style:
- Smooth cinematic camera movements (gimbal/slider)
- Dramatic lighting with warm and cool tones
- Korean urban landscape with cinematic composition
- Establishing shots of Seoul skyline or modern architecture
- Rich color grading inspired by Korean cinema

Camera:
- Wide establishing shots
- Slow push-ins and reveals
- Overhead/drone shots of Korean cityscape
- Smooth tracking shots

Audio:
- Emotional background music (orchestral or modern Korean OST style)
- Carefully designed sound effects
- Polished voice-over narration

Narrative: {narrative}

Mood: Inspiring, emotional, aspirational
Pacing: Dynamic with emotional beats
Final Message: {cta}

Technical: 24fps, anamorphic feel, cinematic color grade
"""
    
    # 스타일 3: 모던 다이내믹 (Modern Dynamic)
    style3 = f"""
[스타일 3: 모던 다이내믹]

{base_context}

Visual Style:
- Fast-paced dynamic cuts
- Modern Korean lifestyle and technology
- Bright, energetic visuals
- Clean, contemporary aesthetic
- Vibrant color grading with saturated tones

Camera:
- Quick cuts between multiple angles
- Time-lapse of Korean city life
- Dynamic camera movements
- Close-ups on details and faces
- Match cuts for visual rhythm

Audio:
- Upbeat modern Korean music
- Rhythmic sound design
- Quick voice-over or on-screen Korean text animations
- Sync with visual cuts

Narrative: {narrative}

Mood: Energetic, modern, forward-thinking
Pacing: Fast, rhythmic, attention-grabbing
Final Message: {cta}

Technical: 30fps or 60fps slow-motion elements, high contrast, vibrant colors
"""
    
    return {
        "documentary": style1,
        "cinematic": style2,
        "modern_dynamic": style3
    }
