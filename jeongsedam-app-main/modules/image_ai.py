# modules/image_ai.py

import base64
from io import BytesIO
from typing import Dict, Any, List

import streamlit as st
from PIL import Image
from openai import OpenAI

# OpenAI client
client = OpenAI()


# ---------------------------
# 세션 상태 초기화
# ---------------------------
def _ensure_state():
    if "image_results" not in st.session_state:
        st.session_state.image_results = []


# ---------------------------
# 프롬프트 생성
# ---------------------------
def _prompt_from_result(r: Dict[str, Any]) -> str:
    base = r.get("image_prompt")
    if not base:
        base = (
            "대한민국 도시 환경을 배경으로 한 현실적이고 신뢰감 있는 장면. "
            "자연광, 다큐멘터리 스타일, 과장 없음. "
            "사람과 공간이 자연스럽게 어우러진 모습."
        )

    quality_guard = (
        "\n\n[품질 규칙]\n"
        "- 과장/판타지 금지\n"
        "- 한국 도시 맥락 유지\n"
        "- 텍스트/로고/영문 문구 없음\n"
        "- 실제 촬영 같은 색감\n"
    )

    return base + quality_guard


# ---------------------------
# 이미지 생성 (핵심)
# ---------------------------
def _gen_images(prompt: str, n: int = 2, size: str = "1024x1024") -> List[Image.Image]:
    res = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        n=n,
    )

    images: List[Image.Image] = []
    for d in res.data:
        img_bytes = base64.b64decode(d.b64_json)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        images.append(img)

    return images


# ---------------------------
# 화면 렌더링
# ---------------------------
def render_image_ai(r: Dict[str, Any]):
    _ensure_state()

    st.markdown("## 🖼 이미지 (완전 자동 생성)")
    st.caption("버튼 1번 → 2장 생성 / 새로고침 → 2장씩 추가")

    col1, col2, col3 = st.columns([1.2, 1.2, 1.6])

    # 최초 생성
    with col1:
        if st.button("🖼 이미지 2장 생성", use_container_width=True, key="img_gen_first"):
            prompt = _prompt_from_result(r)
            imgs = _gen_images(prompt, n=2)
            st.session_state.image_results.extend(imgs)
            st.rerun()

    # 추가 생성
    with col2:
        if st.button("🔄 새로고침 (추가 2장)", use_container_width=True, key="img_gen_more"):
            prompt = _prompt_from_result(r)
            imgs = _gen_images(prompt, n=2)
            st.session_state.image_results.extend(imgs)
            st.rerun()

    # 개수 표시
    with col3:
        st.write(f"생성된 이미지 수: {len(st.session_state.image_results)}")

    st.divider()

    # 결과 표시
    if st.session_state.image_results:
        st.markdown("### 생성 결과")
        for i, img in enumerate(st.session_state.image_results):
            st.image(img, use_container_width=True)
