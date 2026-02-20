import streamlit as st
import sqlite3
import os
import datetime as dt

st.set_page_config(page_title="정세담 소개", layout="wide")

st.title("정세담 AI 학습·관리 시스템")

st.markdown("---")

# ==================================================
# 1. 핵심 메시지
# ==================================================

st.header("정세담은 무엇을 해결하는가")

st.info("""
정세담은  
공부 잘하는 아이를 만드는 시스템이 아닙니다.

**포기하지 않게 만드는 시스템**입니다.
""")

col1, col2 = st.columns(2)

with col1:
    st.subheader("현재 교육의 문제")
    st.write("""
    - 성적 중심 경쟁 구조
    - 부모의 불안과 과도한 통제
    - 아이의 학습 포기 증가
    - 학습 + 심리 관리 분리
    - 데이터 기반 관리 부재
    """)

with col2:
    st.subheader("정세담의 접근")
    st.write("""
    - 학습 + 심리 + 습관 통합 관리
    - 부모와 함께하는 동행 구조
    - 비교 없는 개인 성장 관리
    - 데이터 기반 학습 방향 제시
    - 포기하지 않는 루틴 설계
    """)

st.markdown("---")

# ==================================================
# 2. 시스템 구조
# ==================================================

st.header("시스템 구조")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("학생")
    st.write("""
    - 문제 풀이 및 학습 기록
    - 과목별 성취 분석
    - 학습 루틴 관리
    """)

with col2:
    st.subheader("학부모")
    st.write("""
    - 학습 상태 확인
    - 과목별 방향 제시
    - 심리 상태 관찰
    - 부모 동기부여 및 도서 제공
    """)

with col3:
    st.subheader("데이터")
    st.write("""
    - 학습 데이터 누적
    - 심리 상태 변화 추적
    - 장기 성장 분석
    - 진학 가능성 제시
    """)

st.markdown("---")

# ==================================================
# 3. 차별성
# ==================================================

st.header("정세담의 차별성")

st.success("""
1. 비교와 순위 중심이 아닌 개인 성장 관리  
2. 학습 + 심리 + 부모 관리 통합  
3. 포기하지 않게 만드는 루틴 중심 구조  
4. 데이터 기반 장기 성장 시스템  
""")

st.markdown("---")

# ==================================================
# 4. 정책 관점 가치
# ==================================================

st.header("정책 및 공공 활용 가치")

col1, col2 = st.columns(2)

with col1:
    st.subheader("교육 정책 효과")
    st.write("""
    - 학습 포기 감소
    - 교육 격차 완화
    - 취약계층 지원 가능
    - 지역 간 교육 관리 표준화
    """)

with col2:
    st.subheader("데이터 기반 행정")
    st.write("""
    - 학습 데이터 기반 정책 수립
    - 심리 위험 조기 감지
    - 학교·가정 연계 관리
    - 국가 단위 교육 데이터 구축
    """)

st.markdown("---")

# ==================================================
# 5. 핵심 철학 (마무리)
# ==================================================

st.header("정세담의 철학")

st.warning("""
정세담은  
성적을 올리는 시스템이 아니라,

학생과 부모가  
**포기하지 않도록 만드는 시스템입니다.**
""")

st.markdown("---")

st.caption("정세담 AI 통합 교육 관리 플랫폼")

st.markdown("---")

# ==================================================
# 6. 실시간 통계
# ==================================================

st.header("📊 실시간 시스템 통계")
st.caption("현재 데이터베이스에 누적된 실제 학습 데이터입니다.")

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "student_system.db")

def _safe_query(sql, params=()):
    try:
        con = sqlite3.connect(_DB_PATH)
        result = con.execute(sql, params).fetchone()
        con.close()
        return result[0] if result else 0
    except Exception:
        return 0

total_sessions = _safe_query("SELECT COUNT(*) FROM study_sessions")
total_questions = _safe_query("SELECT COUNT(*) FROM questions")
total_correct = _safe_query("SELECT SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) FROM questions")
total_students = _safe_query("SELECT COUNT(*) FROM students")
total_psych = _safe_query("SELECT COUNT(*) FROM psychological_tests")
total_vocab = _safe_query("SELECT COUNT(*) FROM search_history")
total_study_days = _safe_query("SELECT COUNT(DISTINCT substr(created_at,1,10) || '-' || student_id) FROM study_sessions")

overall_rate = round(total_correct / total_questions * 100, 1) if total_questions > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("등록 학생 수", f"{total_students}명")
c2.metric("총 학습 세션", f"{total_sessions}회")
c3.metric("총 풀이 문항", f"{total_questions}개")
c4.metric("전체 정답률", f"{overall_rate}%")

c5, c6, c7, c8 = st.columns(4)
c5.metric("심리 체크 횟수", f"{total_psych}회")
c6.metric("단어장 저장 수", f"{total_vocab}개")
c7.metric("누적 학습일 수", f"{total_study_days}일")
c8.metric("마지막 업데이트", dt.date.today().isoformat())

st.caption("※ 통계는 페이지 로드 시점 기준이며, 실제 학생 학습이 진행될수록 수치가 증가합니다.")