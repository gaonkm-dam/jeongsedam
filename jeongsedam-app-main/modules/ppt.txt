# modules/ppt_ai.py
import streamlit as st

def build_ppt_outline(result: dict) -> str:
    summary = result.get("meeting_summary", {})
    policy = result.get("policy_result", {})
    kpi = result.get("kpi", {})

    return f"""
[슬라이드 1] 제목
- 정책 퍼포먼스 요약

[슬라이드 2] 문제 인식
- 현황
- 기존 한계

[슬라이드 3] 해결 전략
- 정책 방향
- 실행 구조

[슬라이드 4] 기대 효과
- 시민 체감 효과
- 행정 효율

[슬라이드 5] 성과 지표(KPI)
- {kpi}

[슬라이드 6] 결론
- 정책 도입 제안
""".strip()


def render_ppt_ai(result: dict):
    st.markdown("## 📊 PPT (자동 구성안)")

    outline = build_ppt_outline(result)

    st.text_area("PPT 구성안 (그대로 복사)", outline, height=260)

    st.button(
        "📋 PPT 구성 복사",
        on_click=lambda: st.toast("PPT 구성 복사 완료", icon="📊")
    )
