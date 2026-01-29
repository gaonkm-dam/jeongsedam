# modules/mobile_ui.py
import streamlit as st
import streamlit.components.v1 as components


# ✅ 모바일 UI용 CSS (안전)
def inject_mobile_css():
    st.markdown("""
    <style>
    /* 모바일 대응 */
    @media (max-width: 768px) {
        .block-container {
            padding: 0.8rem !important;
        }
        textarea {
            font-size: 14px !important;
        }
        button {
            width: 100% !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


# ✅ 복사 버튼 (JS는 html 컴포넌트 안에서만!)
def copy_button(text: str, label="복사"):
    components.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{text}`)"
                style="
                padding:10px;
                width:100%;
                font-size:14px;
                cursor:pointer;
                ">
            📋 {label}
        </button>
        """,
        height=60
    )


# ✅ AI 바로가기 버튼 (외부 이동만, JS 최소)
def quick_ai_links():
    st.markdown("### 🚀 바로 생성하기")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.link_button("🎬 Sora", "https://openai.com/sora")
    with c2:
        st.link_button("🎞 Runway", "https://runwayml.com")
    with c3:
        st.link_button("🎥 Pika", "https://pika.art")