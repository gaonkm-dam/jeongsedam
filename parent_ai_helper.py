import os
import streamlit as st

from openai import OpenAI


def _get_api_key() -> str:
    """
    API 키 우선순위:
    1) 환경변수 OPENAI_API_KEY
    2) 프로젝트 루트 api_key.txt (OPENAI_API_KEY=... 형식)
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        key_file = os.path.join(base_dir, "api_key.txt")
        with open(key_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass

    return ""


def generate_ai_text(prompt: str) -> str | None:
    """
    AI ON/OFF 토글(st.session_state["use_openai"])에 따라 동작.
    - OFF → None 반환 (호출 없음, 비용 0)
    - ON  → OpenAI 호출 후 텍스트 반환
    - 오류 발생 시 절대 프로그램 중단하지 않고 None 반환
    """

    if not st.session_state.get("use_openai", False):
        return None

    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 학부모/학생을 돕는 루틴 코치다. 낙인/압박 금지. 실행 가능한 조언만."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return None
