# modules/video_ai.py
import streamlit as st

SORA_URL = "https://openai.com/sora"
RUNWAY_URL = "https://runwayml.com"
PIKA_URL = "https://pika.art"

def build_video_prompt(result: dict) -> str:
    summary = result.get("meeting_summary", {})
    one = summary.get("one_liner", "")
    decision = summary.get("decision", "")
    track = summary.get("talk_track", [])

    bullets = "\n".join([f"- {x}" for x in track])

    return f"""
Ultra-realistic documentary style, South Korea context.
Natural lighting, handheld camera feel.
One continuous generation if possible. No English text on screen.

[목적]
{one}

[정책 메시지]
{decision}

[스토리 흐름]
{bullets}

20 seconds. Follow the plan exactly.
""".strip()


def render_video_ai(result: dict):
    st.markdown("## 🎬 영상 (즉시 투입용 · 자동 프롬프트)")

    prompt = build_video_prompt(result)

    col1, col2, col3 = st.columns(3)
    col1.link_button("Sora 바로가기", SORA_URL)
    col2.link_button("Runway 바로가기", RUNWAY_URL)
    col3.link_button("Pika 바로가기", PIKA_URL)

    st.text_area("영상 프롬프트", prompt, height=260)

    st.button(
        "📋 프롬프트 복사",
        on_click=lambda: st.toast("프롬프트를 복사하세요 (Ctrl+C)", icon="📋")
    )
