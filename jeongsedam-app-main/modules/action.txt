# modules/action_buttons.py

import streamlit as st


def render_ai_actions(result: dict):
    if not isinstance(result, dict):
        return

    st.markdown("### ⚡ AI 원클릭 생성")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 🎬 영상")
        st.link_button("Sora 바로가기", "https://sora.openai.com")
        st.link_button("Runway 바로가기", "https://runwayml.com")
        st.link_button("Pika 바로가기", "https://pika.art")

        if st.button("🎬 영상 프롬프트 복사"):
            prompt = result.get("video_prompt", "")
            if prompt:
                st.code(prompt)
            else:
                st.info("영상 프롬프트가 없습니다.")

    with col2:
        st.markdown("#### 🖼 이미지")
        if st.button("🖼 이미지 프롬프트 복사"):
            prompt = result.get("image_prompt", "")
            if prompt:
                st.code(prompt)
            else:
                st.info("이미지 프롬프트가 없습니다.")

    with col3:
        st.markdown("#### 📊 PPT")
        if st.button("📊 PPT 프롬프트 복사"):
            prompt = result.get("ppt_prompt", "")
            if prompt:
                st.code(prompt)
            else:
                st.info("PPT 프롬프트가 없습니다.")
