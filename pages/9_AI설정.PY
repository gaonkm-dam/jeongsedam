import streamlit as st
import os

st.set_page_config(layout="centered")
st.title("AI 설정")

st.write("OpenAI 사용 여부를 설정합니다.")
st.caption("OFF 상태에서는 AI가 호출되지 않으며 비용이 발생하지 않습니다.")

# ===============================
# 세션 상태 초기화
# ===============================
if "use_openai" not in st.session_state:
    st.session_state.use_openai = False

# ===============================
# ON / OFF 토글
# ===============================
use_ai = st.toggle(
    "OpenAI 사용",
    value=st.session_state.use_openai
)

st.session_state.use_openai = use_ai

# ===============================
# 상태 표시
# ===============================
if use_ai:
    st.success("OpenAI 사용 ON")
else:
    st.info("OpenAI 사용 OFF (비용 발생 없음)")

# ===============================
# API Key 입력
# ===============================
st.header("OpenAI API Key")

api_key = st.text_input(
    "API Key 입력",
    type="password",
    value=os.getenv("OPENAI_API_KEY", "")
)

if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    st.success("API Key 저장됨")
else:
    st.warning("API Key 미입력 상태")