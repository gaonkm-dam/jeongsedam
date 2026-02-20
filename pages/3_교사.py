import streamlit as st
import sqlite3
import pandas as pd
import datetime as dt
import random
import re
import os
from typing import Optional, List, Dict, Any

# =====================================================
# 페이지 설정 (학생/학부모 절대 건드리지 않음)
# =====================================================
st.set_page_config(
    page_title="교사",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# wide 레이아웃에서 콘텐츠 너비 제한 + 태블릿 최적화
st.markdown("""
<style>
/* 전체 컨테이너 */
.block-container { max-width: 860px !important; padding: 1rem 1rem 2rem 1rem !important; margin: auto; }

/* 버튼 터치 최적화 */
.stButton > button {
    min-height: 48px !important;
    font-size: 1rem !important;
    border-radius: 10px !important;
    width: 100% !important;
    margin-bottom: 4px !important;
}

/* selectbox / input 크게 */
.stSelectbox > div, .stTextInput > div, .stNumberInput > div {
    font-size: 1rem !important;
}
.stSelectbox [data-baseweb="select"] {
    min-height: 48px !important;
    font-size: 1rem !important;
}

/* metric 카드 */
[data-testid="metric-container"] {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 12px !important;
    margin-bottom: 8px;
}

/* 사이드바 */
.css-1d391kg { padding-top: 1rem; }

/* dataframe 폰트 */
.dataframe { font-size: 0.9rem !important; }

/* expander */
.streamlit-expanderHeader { font-size: 1rem !important; min-height: 44px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# DB 연결 (기존 student_system.db 그대로 사용, 추가 테이블만)
# =====================================================
DB_PATH = "student_system.db"

def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def ensure_teacher_tables():
    con = get_conn()
    cur = con.cursor()

    # 교사 계정
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 학생별 메모/피드백
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_student_memo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        memo TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 수업 계획 / 과제
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_lesson_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        subject TEXT,
        grade TEXT,
        title TEXT NOT NULL,
        content TEXT,
        due_date TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 교사 AI 로그 캐시
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_ai_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        student_id INTEGER,
        log_type TEXT NOT NULL,
        log_key TEXT NOT NULL,
        content TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(teacher_id, student_id, log_type, log_key)
    )
    """)

    # 데모 교사 3명 초기 생성
    DEMO_TEACHERS = [
        ("김선생", "teacher1@test.com", "pass1"),
        ("이선생", "teacher2@test.com", "pass2"),
        ("박선생", "teacher3@test.com", "pass3"),
    ]
    for name, email, pw in DEMO_TEACHERS:
        cur.execute(
            "INSERT OR IGNORE INTO teachers(name, email, password) VALUES(?,?,?)",
            (name, email, pw)
        )

    con.commit()
    con.close()

ensure_teacher_tables()

# =====================================================
# DB 조회 함수 (읽기 전용 - 기존 테이블 절대 수정 없음)
# =====================================================
def get_all_students() -> List[Dict]:
    con = get_conn()
    rows = con.execute("SELECT id, name, grade FROM students ORDER BY id").fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_student_summary(student_id: int) -> Dict:
    con = get_conn()
    try:
        s = con.execute(
            "SELECT * FROM study_sessions WHERE student_id=?", (student_id,)
        ).fetchall()
        q = con.execute(
            """SELECT q.is_correct FROM questions q
               JOIN study_sessions ss ON ss.id = q.session_id
               WHERE ss.student_id=?""", (student_id,)
        ).fetchall()
    finally:
        con.close()

    total_q = len(q)
    correct = sum(1 for r in q if r["is_correct"] == 1)
    correct_rate = round(correct / total_q * 100, 1) if total_q > 0 else 0.0
    dates = list({str(r["created_at"])[:10] for r in s if r["created_at"]})
    last_date = max(dates) if dates else "없음"

    if total_q <= 50:
        level = "Beginner"
    elif total_q <= 200:
        level = "Basic"
    elif total_q <= 500:
        level = "Intermediate"
    else:
        level = "Advanced"

    return {
        "total_questions": total_q,
        "correct": correct,
        "correct_rate": correct_rate,
        "study_days": len(dates),
        "last_date": last_date,
        "level": level,
    }

def get_subject_stats(student_id: int) -> pd.DataFrame:
    SUBJECTS = ["국어", "영어", "수학", "과학", "사회", "한자", "역사"]
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT ss.subject, q.is_correct
               FROM study_sessions ss
               LEFT JOIN questions q ON q.session_id = ss.id
               WHERE ss.student_id=?""", (student_id,)
        ).fetchall()
    finally:
        con.close()

    if not rows:
        return pd.DataFrame(columns=["과목", "총 문항", "정답률(%)"])

    df = pd.DataFrame([dict(r) for r in rows])
    result = []
    for subj in SUBJECTS:
        sub = df[df["subject"] == subj]
        if sub.empty:
            result.append({"과목": subj, "총 문항": 0, "정답률(%)": 0.0})
        else:
            total = len(sub)
            cr = round(sub["is_correct"].dropna().mean() * 100, 1) if sub["is_correct"].dropna().size > 0 else 0.0
            result.append({"과목": subj, "총 문항": total, "정답률(%)": cr})
    return pd.DataFrame(result)

def get_recent_sessions(student_id: int, limit: int = 20) -> pd.DataFrame:
    con = get_conn()
    try:
        rows = con.execute(
            """SELECT id, subject, grade, difficulty, exam_type,
                      total_questions, correct_count,
                      substr(created_at,1,10) as date
               FROM study_sessions WHERE student_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (student_id, limit)
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])

def get_session_questions_detail(session_id: int) -> pd.DataFrame:
    con = get_conn()
    try:
        rows = con.execute(
            "SELECT question_number, question_text, answer, explanation, is_correct FROM questions WHERE session_id=? ORDER BY question_number",
            (session_id,)
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])

def get_psych_tests(student_id: int) -> List[Dict]:
    con = get_conn()
    try:
        rows = con.execute(
            "SELECT * FROM psychological_tests WHERE student_id=? ORDER BY test_date DESC",
            (student_id,)
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]

# 심리 문항 레이블
PSY_LABELS = {
    "q1": "학교생활 즐거움",
    "q2": "친구 관계",
    "q3": "공부 집중력",
    "q4": "불안감",
    "q5": "수면 상태",
    "q6": "식욕/체력",
    "q7": "가족 관계",
    "q8": "자존감",
    "q9": "스트레스",
    "q10": "미래 불안",
    "q11": "의욕/동기",
    "q12": "감정 표현",
    "q13": "외로움",
    "q14": "분노/짜증",
    "q15": "성취감",
    "q16": "자기 효능감",
    "q17": "피로감",
    "q18": "즐거운 활동",
    "q19": "지지 받는 느낌",
    "q20": "행복감",
}

RISK_MAP = {
    "안정": ("안정", "#28a745"),
    "주의": ("관찰 필요", "#ffc107"),
    "위험": ("지원 필요", "#fd7e14"),
    "고위험": ("집중 지원", "#dc3545"),
}

def calc_risk(score: int) -> str:
    if score >= 80: return "안정"
    if score >= 60: return "주의"
    if score >= 40: return "위험"
    return "고위험"

def get_memos(teacher_id: int, student_id: int) -> List[Dict]:
    con = get_conn()
    rows = con.execute(
        "SELECT id, memo, created_at FROM teacher_student_memo WHERE teacher_id=? AND student_id=? ORDER BY created_at DESC",
        (teacher_id, student_id)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def save_memo(teacher_id: int, student_id: int, memo: str):
    con = get_conn()
    con.execute(
        "INSERT INTO teacher_student_memo(teacher_id, student_id, memo) VALUES(?,?,?)",
        (teacher_id, student_id, memo)
    )
    con.commit()
    con.close()

def delete_memo(memo_id: int):
    con = get_conn()
    con.execute("DELETE FROM teacher_student_memo WHERE id=?", (memo_id,))
    con.commit()
    con.close()

def get_lesson_plans(teacher_id: int) -> pd.DataFrame:
    con = get_conn()
    rows = con.execute(
        "SELECT id, subject, grade, title, content, due_date, substr(created_at,1,10) as created FROM teacher_lesson_plan WHERE teacher_id=? ORDER BY created_at DESC",
        (teacher_id,)
    ).fetchall()
    con.close()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])

def save_lesson_plan(teacher_id: int, subject: str, grade: str, title: str, content: str, due_date: str):
    con = get_conn()
    con.execute(
        "INSERT INTO teacher_lesson_plan(teacher_id, subject, grade, title, content, due_date) VALUES(?,?,?,?,?,?)",
        (teacher_id, subject, grade, title, content, due_date)
    )
    con.commit()
    con.close()

def delete_lesson_plan(plan_id: int):
    con = get_conn()
    con.execute("DELETE FROM teacher_lesson_plan WHERE id=?", (plan_id,))
    con.commit()
    con.close()

def get_ai_log(teacher_id: int, student_id: Optional[int], log_type: str, log_key: str) -> Optional[str]:
    con = get_conn()
    row = con.execute(
        "SELECT content FROM teacher_ai_log WHERE teacher_id=? AND student_id=? AND log_type=? AND log_key=?",
        (teacher_id, student_id, log_type, log_key)
    ).fetchone()
    con.close()
    return row["content"] if row else None

def upsert_ai_log(teacher_id: int, student_id: Optional[int], log_type: str, log_key: str, content: str):
    con = get_conn()
    con.execute("""
    INSERT INTO teacher_ai_log(teacher_id, student_id, log_type, log_key, content, updated_at)
    VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
    ON CONFLICT(teacher_id, student_id, log_type, log_key)
    DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at
    """, (teacher_id, student_id, log_type, log_key, content))
    con.commit()
    con.close()

# =====================================================
# AI 생성 (OpenAI ON/OFF)
# =====================================================
def try_ai_generate(prompt: str) -> str:
    use_ai = st.session_state.get("teacher_use_openai", False)
    if use_ai:
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY") or ""
            if not api_key:
                for fname in [".env", "api_key.txt"]:
                    try:
                        base = os.path.dirname(os.path.abspath(__file__))
                        fp = os.path.join(base, "..", fname)
                        with open(fp, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.startswith("OPENAI_API_KEY="):
                                    api_key = line.strip().split("=", 1)[1]
                                    break
                        if api_key:
                            break
                    except Exception:
                        pass
            if not api_key:
                return "[API 키 없음] 학생 페이지에서 API 키를 설정해 주세요."
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 교육 전문가입니다. 교사에게 학생 분석 리포트를 제공합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1200,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"[AI 오류] {e}"
    else:
        templates = [
            "학생의 최근 학습 패턴을 분석한 결과, 꾸준한 학습 루틴이 형성되고 있습니다. 특히 정답률이 높은 과목을 중심으로 자신감을 키워주세요.",
            "오늘 학습 데이터 기반으로 보면, 풀어야 할 문항 양보다 '이해도 확인'이 우선입니다. 짧은 복습 시간을 추천합니다.",
            "학생이 특정 과목에서 집중적인 학습을 하고 있습니다. 다른 과목 균형도 함께 점검해 주세요.",
        ]
        return f"[AI OFF - 템플릿 응답]\n\n{random.choice(templates)}"

# =====================================================
# 사이드바 로그인
# =====================================================
DEMO_TEACHERS = [
    ("김선생", "teacher1@test.com", "pass1"),
    ("이선생", "teacher2@test.com", "pass2"),
    ("박선생", "teacher3@test.com", "pass3"),
]

def sidebar_teacher_login() -> Optional[int]:
    for key, default in [("teacher_id", None), ("teacher_name", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

    with st.sidebar:
        if not st.session_state.get("teacher_id"):
            st.markdown("### 📚 교사 로그인")
            st.caption("버튼 클릭 한 번으로 바로 입장합니다.")
            con = get_conn()
            for name, email, pw in DEMO_TEACHERS:
                if st.button(f"📚 {name}으로 입장", use_container_width=True, key=f"tdemo_{email}"):
                    row = con.execute(
                        "SELECT id, name FROM teachers WHERE email=? AND password=?", (email, pw)
                    ).fetchone()
                    if row:
                        st.session_state["teacher_id"] = int(row["id"])
                        st.session_state["teacher_name"] = row["name"]
                        st.rerun()
            con.close()
        else:
            st.success(f"✅ {st.session_state['teacher_name']} 선생님")
            st.divider()
            if st.button("🚪 로그아웃", use_container_width=True, key="teacher_logout_sidebar"):
                st.session_state["teacher_id"] = None
                st.session_state["teacher_name"] = None
                st.rerun()

    return st.session_state.get("teacher_id")

TEACHER_ID = sidebar_teacher_login()

# =====================================================
# 미로그인 화면
# =====================================================
if not TEACHER_ID:
    st.markdown("## 📚 교사 공간")
    st.caption("좌측 사이드바에서 교사 계정으로 입장하세요.")
    st.divider()

    TEACHER_QUOTES = [
        "한 명의 좋은 교사가 백 명의 학생을 변화시킵니다.",
        "교육은 가장 강력한 무기입니다.",
        "학생의 가능성을 가장 먼저 보는 사람이 교사입니다.",
        "오늘의 작은 격려가 평생의 자신감이 됩니다.",
        "모든 학생은 다른 속도로 성장합니다.",
        "교사의 믿음이 학생의 한계를 넓힙니다.",
        "데이터는 학생을 이해하는 도구입니다.",
        "루틴이 성적을 만들고, 습관이 미래를 만듭니다.",
        "오늘도 학생 곁에서 함께해 주셔서 감사합니다.",
        "가르치는 것은 두 번 배우는 것입니다.",
    ]
    st.info(f"💬 **{random.choice(TEACHER_QUOTES)}**")

    st.markdown("""
    ---
    ### 이곳에서 할 수 있는 것들
    - 학생 3명 전체 학습 현황 대시보드
    - 학생별 과목/정답률/학습일 상세 분석
    - 심리 테스트 결과 조회 (교사 전용)
    - 학생별 문제 풀이 이력 조회
    - 학생에게 메모/피드백 남기기
    - 수업 계획 / 과제 등록 관리
    - 교사용 OpenAI 학습 분석 리포트 생성

    **좌측 사이드바 → 교사로 입장** 버튼을 눌러 시작하세요.
    """)
    st.stop()

# =====================================================
# 로그인 완료 - 메인 화면
# =====================================================
teacher_name = st.session_state.get("teacher_name", "선생님")
col_title, col_logout = st.columns([5, 1])
with col_title:
    st.markdown(f"## 📚 {teacher_name} 선생님")
with col_logout:
    if st.button("로그아웃", key="teacher_logout_main", use_container_width=True):
        st.session_state["teacher_id"] = None
        st.session_state["teacher_name"] = None
        st.rerun()

st.caption("학생 데이터를 기반으로 학습 현황을 분석하고 지원합니다.")

# AI ON/OFF 토글
if "teacher_use_openai" not in st.session_state:
    st.session_state["teacher_use_openai"] = False

ai_col1, ai_col2 = st.columns([3, 7])
with ai_col1:
    ai_toggle = st.toggle("AI 사용", value=st.session_state["teacher_use_openai"], key="ai_toggle_teacher")
    st.session_state["teacher_use_openai"] = ai_toggle
with ai_col2:
    if st.session_state["teacher_use_openai"]:
        st.success("AI ON (OpenAI 사용)")
    else:
        st.warning("AI OFF (기본 텍스트 사용, 비용 없음)")

st.divider()

# 학생 목록 로드
all_students = get_all_students()
if not all_students:
    st.error("학생 데이터가 없습니다.")
    st.stop()

# 메뉴 선택 (모바일/태블릿 최적화 - selectbox 방식)
MENU_OPTIONS = [
    "📊 전체 대시보드",
    "🔍 학생별 상세 분석",
    "🧠 심리 테스트 결과",
    "📋 문제 이력 조회",
    "✏️ 메모 / 피드백",
    "📅 수업 계획 / 과제",
    "🏫 대학 추천 상담",
    "🔔 출석 알림",
    "📡 레이더 차트",
]

selected_menu = st.selectbox("메뉴 선택", MENU_OPTIONS, key="teacher_menu")

st.divider()

_show1 = selected_menu == "📊 전체 대시보드"
_show2 = selected_menu == "🔍 학생별 상세 분석"
_show3 = selected_menu == "🧠 심리 테스트 결과"
_show4 = selected_menu == "📋 문제 이력 조회"
_show5 = selected_menu == "✏️ 메모 / 피드백"
_show6 = selected_menu == "📅 수업 계획 / 과제"
_show7 = selected_menu == "🏫 대학 추천 상담"
_show8 = selected_menu == "🔔 출석 알림"
_show9 = selected_menu == "📡 레이더 차트"

tab1 = type('_Tab', (), {'__enter__': lambda s: s, '__exit__': lambda s,*a: None})()
tab2 = tab1; tab3 = tab1; tab4 = tab1; tab5 = tab1; tab6 = tab1; tab7 = tab1; tab8 = tab1; tab9 = tab1

# 전역: 모든 섹션에서 공통 사용
stu_names = [s["name"] for s in all_students]

# ─────────────────────────────────────────────────
# TAB 1: 전체 대시보드
# ─────────────────────────────────────────────────
if _show1:
    st.markdown("### 학생 3명 전체 학습 현황")
    st.caption("모든 학생의 학습 데이터를 한눈에 비교합니다. (비교/줄세우기가 아닌 현황 파악용)")

    summary_rows = []
    for stu in all_students:
        s = get_student_summary(stu["id"])
        summary_rows.append({
            "이름": stu["name"],
            "학년": stu["grade"],
            "총 문항": s["total_questions"],
            "정답 수": s["correct"],
            "정답률(%)": s["correct_rate"],
            "학습일": s["study_days"],
            "마지막 학습": s["last_date"],
            "레벨": s["level"],
        })

    df_summary = pd.DataFrame(summary_rows)
    st.dataframe(df_summary, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 학생별 정답률 비교")

    try:
        import altair as alt
        bar = alt.Chart(df_summary).mark_bar().encode(
            x=alt.X("이름:N"),
            y=alt.Y("정답률(%):Q", scale=alt.Scale(domain=[0, 100])),
            color=alt.condition(
                alt.datum["정답률(%)"] >= 70,
                alt.value("#4CAF50"),
                alt.value("#FF9800")
            ),
            tooltip=["이름", "총 문항", "정답률(%)", "레벨"]
        ).properties(height=260)
        st.altair_chart(bar, use_container_width=True)
    except ImportError:
        st.bar_chart(df_summary.set_index("이름")["정답률(%)"])

    st.caption("70% 이상: 초록 / 70% 미만: 주황. 지속적인 격려와 루틴 점검이 중요합니다.")

    st.divider()
    st.markdown("#### 학습일 현황")
    try:
        bar2 = alt.Chart(df_summary).mark_bar(color="#5B9BD5").encode(
            x=alt.X("이름:N"),
            y=alt.Y("학습일:Q"),
            tooltip=["이름", "학습일", "마지막 학습"]
        ).properties(height=220)
        st.altair_chart(bar2, use_container_width=True)
    except Exception:
        st.bar_chart(df_summary.set_index("이름")["학습일"])

# ─────────────────────────────────────────────────
# TAB 2: 학생별 상세 분석
# ─────────────────────────────────────────────────
if _show2:
    st.markdown("### 학생별 상세 분석")

    sel_name = st.selectbox("학생 선택", stu_names, key="tab2_student")
    sel_stu = next(s for s in all_students if s["name"] == sel_name)
    sel_id = sel_stu["id"]

    summary = get_student_summary(sel_id)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 문항", f"{summary['total_questions']}개")
    c2.metric("정답 수", f"{summary['correct']}개")
    c3.metric("정답률", f"{summary['correct_rate']}%")
    c4.metric("학습일", f"{summary['study_days']}일")
    c5.metric("레벨", summary["level"])
    st.caption(f"마지막 학습일: {summary['last_date']}")

    st.divider()
    st.markdown("#### 과목별 분석")

    df_subj = get_subject_stats(sel_id)
    if df_subj["총 문항"].sum() == 0:
        st.info("아직 학습 데이터가 없습니다.")
    else:
        try:
            import altair as alt
            bar_subj = alt.Chart(df_subj).mark_bar().encode(
                x=alt.X("과목:N"),
                y=alt.Y("정답률(%):Q", scale=alt.Scale(domain=[0, 100])),
                color=alt.condition(
                    alt.datum["정답률(%)"] >= 70,
                    alt.value("#4CAF50"),
                    alt.value("#FF9800")
                ),
                tooltip=["과목", "총 문항", "정답률(%)"]
            ).properties(height=260)
            st.altair_chart(bar_subj, use_container_width=True)
        except Exception:
            st.bar_chart(df_subj.set_index("과목")["정답률(%)"])
        st.dataframe(df_subj, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### AI 학습 분석 리포트")
    report_key = f"analysis:{sel_id}:{dt.date.today().isoformat()}"
    cached_report = get_ai_log(TEACHER_ID, sel_id, "analysis", report_key)

    if st.button("리포트 생성/갱신", use_container_width=True, key="gen_report"):
        subj_text = ", ".join(
            [f"{r['과목']}({r['정답률(%)']}%)" for _, r in df_subj.iterrows() if r["총 문항"] > 0]
        ) if not df_subj.empty else "데이터 없음"
        prompt = f"""
교사에게 제공할 학생 학습 분석 리포트를 작성하라.
[학생 정보]
- 이름: {sel_name} / 학년: {sel_stu['grade']}
- 총 문항: {summary['total_questions']} / 정답률: {summary['correct_rate']}%
- 학습일: {summary['study_days']}일 / 레벨: {summary['level']}
- 과목별 현황: {subj_text}

요구사항:
1. 학생의 현재 학습 수준 요약 (2문장)
2. 강점 과목 / 보강 권장 과목 (각 1개)
3. 교사 권장 행동 3가지 (짧고 실용적으로)
4. 학생에게 전달할 응원 메시지 1개

낙인/비교/압박 금지. 성장 관점으로 작성.
"""
        content = try_ai_generate(prompt)
        upsert_ai_log(TEACHER_ID, sel_id, "analysis", report_key, content)
        cached_report = content

    if cached_report:
        st.write(cached_report)
    else:
        st.caption("버튼을 눌러 오늘의 리포트를 생성하세요.")

# ─────────────────────────────────────────────────
# TAB 3: 심리 테스트 결과 (교사 전용)
# ─────────────────────────────────────────────────
if _show3:
    st.markdown("### 심리 테스트 결과 (교사 전용)")
    st.caption("이 데이터는 진단이 아니라, 학생 지원 방향을 파악하기 위한 관찰 지표입니다.")

    sel_psy_name = st.selectbox("학생 선택", stu_names, key="tab3_student")
    sel_psy_stu = next(s for s in all_students if s["name"] == sel_psy_name)
    psy_tests = get_psych_tests(sel_psy_stu["id"])

    if not psy_tests:
        st.info(f"{sel_psy_name} 학생의 심리 테스트 데이터가 없습니다.")
    else:
        latest = psy_tests[0]
        total_score = latest.get("total_score") or sum(
            (latest.get(f"q{i}") or 0) for i in range(1, 21)
        )
        risk = calc_risk(int(total_score))
        label, color = RISK_MAP.get(risk, ("관찰", "#6c757d"))

        col_r1, col_r2 = st.columns(2)
        col_r1.metric("총점", f"{total_score}점 / 100점")
        col_r2.metric("지원 단계", label)
        st.caption(f"검사일: {str(latest.get('test_date', ''))[:10]}")
        st.info("※ 이 결과는 학부모에게는 보이지 않습니다. 교사만 열람 가능합니다.")

        st.divider()
        st.markdown("#### 문항별 응답")

        q_rows = []
        for qk, qlabel in PSY_LABELS.items():
            val = latest.get(qk)
            if val is not None:
                q_rows.append({"문항": qlabel, "점수": int(val)})

        if q_rows:
            df_psy = pd.DataFrame(q_rows)
            try:
                import altair as alt
                bar_psy = alt.Chart(df_psy).mark_bar().encode(
                    x=alt.X("문항:N", sort=None),
                    y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 5])),
                    color=alt.condition(
                        alt.datum["점수"] >= 4,
                        alt.value("#4CAF50"),
                        alt.condition(
                            alt.datum["점수"] >= 3,
                            alt.value("#5B9BD5"),
                            alt.value("#FF9800")
                        )
                    ),
                    tooltip=["문항", "점수"]
                ).properties(height=300)
                st.altair_chart(bar_psy, use_container_width=True)
            except Exception:
                st.bar_chart(df_psy.set_index("문항")["점수"])
            st.dataframe(df_psy, use_container_width=True, hide_index=True)
            st.caption("1점: 매우 낮음 / 3점: 보통 / 5점: 매우 높음")

        if len(psy_tests) > 1:
            st.divider()
            st.markdown(f"#### 이전 테스트 이력 (총 {len(psy_tests)}회)")
            hist = [{"검사일": str(t.get("test_date",""))[:10], "총점": t.get("total_score", 0), "지원단계": calc_risk(int(t.get("total_score", 0)))} for t in psy_tests]
            st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────
# TAB 4: 문제 이력 조회
# ─────────────────────────────────────────────────
if _show4:
    st.markdown("### 학생별 문제 이력 조회")

    sel_hist_name = st.selectbox("학생 선택", stu_names, key="tab4_student")
    sel_hist_stu = next(s for s in all_students if s["name"] == sel_hist_name)
    sel_hist_id = sel_hist_stu["id"]

    df_sessions = get_recent_sessions(sel_hist_id, limit=30)

    if df_sessions.empty:
        st.info(f"{sel_hist_name} 학생의 학습 이력이 없습니다.")
    else:
        st.markdown(f"**최근 {len(df_sessions)}개 세션**")
        st.dataframe(
            df_sessions[["date", "subject", "grade", "difficulty", "exam_type", "total_questions", "correct_count"]].rename(columns={
                "date": "날짜", "subject": "과목", "grade": "학년",
                "difficulty": "난이도", "exam_type": "시험유형",
                "total_questions": "총 문항", "correct_count": "정답 수"
            }),
            use_container_width=True, hide_index=True
        )

        st.divider()
        st.markdown("#### 세션 문제 상세 보기")

        session_options = {f"{r['date']} | {r['subject']} {r['grade']} ({r['total_questions']}문항)": r["id"] for _, r in df_sessions.iterrows()}
        sel_session_label = st.selectbox("세션 선택", list(session_options.keys()), key="tab4_session")
        sel_session_id = session_options[sel_session_label]

        df_q = get_session_questions_detail(sel_session_id)
        if df_q.empty:
            st.info("해당 세션의 문제 데이터가 없습니다.")
        else:
            for _, row in df_q.iterrows():
                with st.expander(f"문제 {int(row['question_number'])} {'✅' if row['is_correct'] == 1 else '❌' if row['is_correct'] == 0 else '⬜'}"):
                    st.markdown(f"**문제:** {row['question_text']}")
                    st.markdown(f"**정답:** {row['answer']}")
                    if row["explanation"]:
                        st.caption(f"해설: {row['explanation']}")
                    if row["is_correct"] is None:
                        st.caption("채점 정보 없음")

# ─────────────────────────────────────────────────
# TAB 5: 메모 / 피드백
# ─────────────────────────────────────────────────
if _show5:
    st.markdown("### 학생 메모 / 피드백")
    st.caption("학생별로 교사가 남기는 관찰 메모입니다. 학생/학부모에게는 보이지 않습니다.")

    sel_memo_name = st.selectbox("학생 선택", stu_names, key="tab5_student")
    sel_memo_stu = next(s for s in all_students if s["name"] == sel_memo_name)
    sel_memo_id = sel_memo_stu["id"]

    st.markdown(f"#### {sel_memo_name} 학생 메모 작성")
    new_memo = st.text_area("메모 내용", placeholder="학습 태도, 집중도, 특이사항 등을 기록하세요.", height=120, key="new_memo_input")
    if st.button("메모 저장", use_container_width=True, key="save_memo_btn"):
        if new_memo.strip():
            save_memo(TEACHER_ID, sel_memo_id, new_memo.strip())
            st.success("메모가 저장되었습니다.")
            st.rerun()
        else:
            st.warning("메모 내용을 입력하세요.")

    st.divider()
    st.markdown(f"#### {sel_memo_name} 학생 메모 이력")
    memos = get_memos(TEACHER_ID, sel_memo_id)

    if not memos:
        st.info("저장된 메모가 없습니다.")
    else:
        for m in memos:
            with st.expander(f"📝 {str(m['created_at'])[:16]} | {str(m['memo'])[:40]}..."):
                st.write(m["memo"])
                if st.button("🗑️ 삭제", key=f"del_memo_{m['id']}"):
                    delete_memo(m["id"])
                    st.rerun()

    st.divider()
    st.markdown("#### AI 학생 피드백 초안 생성")
    fb_key = f"feedback:{sel_memo_id}:{dt.date.today().isoformat()}"
    cached_fb = get_ai_log(TEACHER_ID, sel_memo_id, "feedback", fb_key)

    if st.button("피드백 초안 생성", use_container_width=True, key="gen_feedback"):
        summary_fb = get_student_summary(sel_memo_id)
        prompt = f"""
교사가 학생에게 전달할 피드백 초안을 작성하라.
[학생: {sel_memo_name} / 학년: {sel_memo_stu['grade']}]
[현황: 총 {summary_fb['total_questions']}문항, 정답률 {summary_fb['correct_rate']}%, 학습일 {summary_fb['study_days']}일, 레벨 {summary_fb['level']}]
기존 메모 요약: {', '.join([m['memo'][:30] for m in memos[:3]]) if memos else '없음'}

요구:
1. 학생에게 전달할 긍정적 피드백 (2문장)
2. 개선이 필요한 부분 (압박 없이 제안 형태, 1문장)
3. 다음 학습 목표 제안 (1문장)

따뜻하고 구체적으로 작성. 낙인 금지.
"""
        content = try_ai_generate(prompt)
        upsert_ai_log(TEACHER_ID, sel_memo_id, "feedback", fb_key, content)
        cached_fb = content

    if cached_fb:
        st.write(cached_fb)
    else:
        st.caption("버튼을 눌러 피드백 초안을 생성하세요.")

# ─────────────────────────────────────────────────
# TAB 6: 수업 계획 / 과제
# ─────────────────────────────────────────────────
if _show6:
    st.markdown("### 수업 계획 / 과제 관리")

    SUBJECTS = ["", "국어", "영어", "수학", "과학", "사회", "역사", "한자", "기타"]
    GRADES = ["", "초1", "초2", "초3", "초4", "초5", "초6", "중1", "중2", "중3", "고1", "고2", "고3"]

    with st.form("lesson_plan_form"):
        st.markdown("#### 새 수업 계획 / 과제 등록")
        fc1, fc2 = st.columns(2)
        with fc1:
            plan_subject = st.selectbox("과목", SUBJECTS)
            plan_grade = st.selectbox("학년", GRADES)
        with fc2:
            plan_title = st.text_input("제목 (필수)", placeholder="예: 2단원 핵심 개념 복습 과제")
            plan_due = st.text_input("마감일 (선택)", placeholder="2026-03-01")

        plan_content = st.text_area("내용", placeholder="수업 내용, 과제 설명, 준비물 등을 입력하세요.", height=120)
        submitted = st.form_submit_button("등록", use_container_width=True)
        if submitted:
            if plan_title.strip():
                save_lesson_plan(TEACHER_ID, plan_subject, plan_grade, plan_title.strip(), plan_content.strip(), plan_due.strip())
                st.success("등록 완료!")
                st.rerun()
            else:
                st.error("제목을 입력하세요.")

    st.divider()
    st.markdown("#### 등록된 수업 계획 목록")
    df_plans = get_lesson_plans(TEACHER_ID)

    if df_plans.empty:
        st.info("등록된 수업 계획이 없습니다.")
    else:
        for _, row in df_plans.iterrows():
            tag = f"{row['subject']} {row['grade']}".strip() if (row.get("subject") or row.get("grade")) else "전체"
            due_text = f" | 마감: {row['due_date']}" if row.get("due_date") else ""
            with st.expander(f"📅 [{tag}] {row['title']}{due_text} (등록일: {row['created']})"):
                if row.get("content"):
                    st.write(row["content"])
                if st.button("🗑️ 삭제", key=f"del_plan_{row['id']}"):
                    delete_lesson_plan(int(row["id"]))
                    st.rerun()

    st.divider()
    st.markdown("#### AI 수업 계획 초안 생성")
    ai_plan_key = f"lesson_plan:{dt.date.today().isoformat()}"
    cached_lp = get_ai_log(TEACHER_ID, None, "lesson_plan", ai_plan_key)

    lp_c1, lp_c2 = st.columns(2)
    with lp_c1:
        lp_subject = st.selectbox("과목 선택", SUBJECTS[1:], key="lp_subject")
    with lp_c2:
        lp_grade = st.selectbox("학년 선택", GRADES[1:], key="lp_grade")
    lp_topic = st.text_input("주제 / 단원", placeholder="예: 조선시대 정치 구조", key="lp_topic")

    if st.button("수업 계획 초안 생성", use_container_width=True, key="gen_lesson_plan"):
        prompt = f"""
교사를 위한 수업 계획 초안을 작성하라.
[과목: {lp_subject} / 학년: {lp_grade} / 주제: {lp_topic or '미정'}]

구성:
1. 학습 목표 (2개)
2. 수업 흐름 (도입 5분 / 전개 30분 / 마무리 5분)
3. 핵심 질문 2개
4. 과제 제안 1개
5. 참고 자료 제안

실용적이고 구체적으로 작성.
"""
        content = try_ai_generate(prompt)
        upsert_ai_log(TEACHER_ID, None, "lesson_plan", ai_plan_key, content)
        cached_lp = content

    if cached_lp:
        st.write(cached_lp)
    else:
        st.caption("버튼을 눌러 수업 계획 초안을 생성하세요.")

# ─────────────────────────────────────────────────
# TAB 7: 대학 추천 상담 (교사 전용 심화)
# ─────────────────────────────────────────────────
if _show7:
    st.markdown("### 🏫 대학 추천 상담 (교사 전용 심화)")
    st.caption("교사가 학생 진로 상담에 활용할 수 있는 입시 데이터입니다. 합격 보장이 아닌 참고 자료로 사용하세요.")

    # ── 대학 데이터풀 ────────────────────────────────────────────
    # 구조: (대학, 학과, 계열, 지역, 학위, 점수범위하한, 점수범위상한, 옵션, 장학금여부, 취업률%, 비고)
    UNIV_POOL = [
        # ── 최상위권 (92~100) ──
        ("서울대학교",   "경영학과",       "인문",   "서울",   "4년제",  95, 100, "도전", True,  85, "수능 상위 0.1% 수준"),
        ("서울대학교",   "컴퓨터공학부",   "이공",   "서울",   "4년제",  94, 100, "도전", True,  91, "SW중심대학, 삼성·카카오 취업 다수"),
        ("서울대학교",   "의예과",         "의약",   "서울",   "4년제",  97, 100, "도전", True,  99, "의사 면허 취득, 경쟁 최상"),
        ("연세대학교",   "경영학과",       "인문",   "서울",   "4년제",  92, 98,  "도전", True,  82, "연고대 프리미엄, 글로벌 취업"),
        ("연세대학교",   "컴퓨터과학과",   "이공",   "서울",   "4년제",  91, 97,  "도전", True,  89, "AI·빅데이터 특화"),
        ("고려대학교",   "법학과",         "인문",   "서울",   "4년제",  91, 97,  "도전", True,  78, "법조인 양성 명문"),
        ("고려대학교",   "경제학과",       "인문",   "서울",   "4년제",  90, 96,  "도전", True,  80, "금융·경제 분야 강세"),
        # ── 상위권 (80~92) ──
        ("성균관대학교", "글로벌경영",     "인문",   "서울",   "4년제",  85, 92,  "도전", True,  81, "삼성 장학재단 연계"),
        ("성균관대학교", "소프트웨어학과", "이공",   "수원",   "4년제",  84, 91,  "도전", True,  90, "SW특기자 전형 있음"),
        ("한양대학교",   "경영학부",       "인문",   "서울",   "4년제",  83, 90,  "현실", True,  80, "실무형 교육, 취업률 우수"),
        ("한양대학교",   "컴퓨터소프트웨어학부","이공","서울","4년제",  82, 90,  "현실", True,  88, "ERICA캠퍼스 분리 주의"),
        ("서강대학교",   "경제학과",       "인문",   "서울",   "4년제",  83, 91,  "현실", True,  79, "소규모 정예 교육"),
        ("서강대학교",   "컴퓨터공학과",   "이공",   "서울",   "4년제",  82, 90,  "현실", True,  87, "구글·메타 인턴십 연계"),
        ("중앙대학교",   "경영경제대학",   "인문",   "서울",   "4년제",  78, 87,  "현실", True,  77, "광고·미디어 분야 강세"),
        ("중앙대학교",   "AI학과",         "이공",   "서울",   "4년제",  79, 88,  "현실", True,  86, "2023년 신설, 취업 전망 좋음"),
        ("경희대학교",   "경영학과",       "인문",   "서울",   "4년제",  76, 85,  "현실", True,  75, "한의예과로도 유명"),
        ("경희대학교",   "컴퓨터공학과",   "이공",   "서울",   "4년제",  75, 84,  "현실", True,  84, "국제캠퍼스(수원) 구분"),
        ("건국대학교",   "경영학과",       "인문",   "서울",   "4년제",  73, 82,  "현실", False, 73, "스타트업 연계 활발"),
        ("동국대학교",   "경영학과",       "인문",   "서울",   "4년제",  71, 80,  "현실", False, 72, "불교 재단, 문화콘텐츠 강점"),
        ("홍익대학교",   "시각디자인",     "예체능", "서울",   "4년제",  72, 83,  "현실", False, 76, "미대 최상위, 디자인 분야 취업률 높음"),
        # ── 중상위권 (68~82) ──
        ("국민대학교",   "경영학부",       "인문",   "서울",   "4년제",  68, 78,  "현실", False, 70, "자동차디자인 특화"),
        ("국민대학교",   "소프트웨어학부", "이공",   "서울",   "4년제",  67, 77,  "현실", False, 82, "SW중심대학 선정"),
        ("숭실대학교",   "정보통신전자공학부","이공", "서울",   "4년제",  65, 75,  "현실", False, 80, "IT 분야 인지도 높음"),
        ("세종대학교",   "호텔관광경영",   "인문",   "서울",   "4년제",  65, 75,  "안정", False, 71, "관광·호텔 분야 특화"),
        ("단국대학교",   "경영학과",       "인문",   "경기",   "4년제",  63, 73,  "안정", False, 68, "죽전캠퍼스 위치"),
        ("가천대학교",   "의예과",         "의약",   "경기",   "4년제",  90, 96,  "현실", True,  99, "지방의대 중 커트라인 높음"),
        ("가천대학교",   "경영학과",       "인문",   "경기",   "4년제",  62, 72,  "안정", False, 67, "인천 소재"),
        ("상명대학교",   "경영학과",       "인문",   "서울",   "4년제",  60, 70,  "안정", False, 65, "서울 은평구 위치"),
        ("명지대학교",   "경영학과",       "인문",   "서울",   "4년제",  59, 69,  "안정", False, 64, "용인캠퍼스 주의"),
        # ── 지방거점국립대 ──
        ("부산대학교",   "경영학부",       "인문",   "부산",   "4년제",  75, 85,  "현실", True,  76, "지방 1위 국립대, 등록금 저렴"),
        ("부산대학교",   "컴퓨터공학과",   "이공",   "부산",   "4년제",  73, 83,  "현실", True,  83, "부울경 IT 취업 강세"),
        ("경북대학교",   "경영학부",       "인문",   "대구",   "4년제",  72, 82,  "현실", True,  74, "대구 경북 최상위"),
        ("전남대학교",   "의예과",         "의약",   "광주",   "4년제",  88, 94,  "현실", True,  99, "지방의대, 군의관 선호"),
        ("충남대학교",   "경영학부",       "인문",   "대전",   "4년제",  70, 80,  "현실", True,  72, "정부출연기관 취업 연계"),
        # ── 이공계 특화 ──
        ("KAIST",        "전산학부",       "이공",   "대전",   "4년제",  95, 100, "도전", True,  95, "전원 장학금, 이공계 최정상"),
        ("POSTECH",      "컴퓨터공학과",   "이공",   "포항",   "4년제",  93, 99,  "도전", True,  93, "포스코 장학금, 소수정예"),
        ("UNIST",        "전기전자공학부", "이공",   "울산",   "4년제",  88, 95,  "도전", True,  90, "울산 소재, 이공계 급성장"),
        ("인하대학교",   "항공우주공학",   "이공",   "인천",   "4년제",  75, 84,  "현실", False, 85, "항공사·방산 취업 특화"),
        ("아주대학교",   "소프트웨어학과", "이공",   "경기",   "4년제",  73, 82,  "현실", False, 84, "삼성전자 인접, 인턴십 활발"),
        # ── 예체능 ──
        ("한국예술종합학교","연기과",      "예체능", "서울",   "4년제",  80, 95,  "도전", True,  72, "실기 100%, 내신 반영 없음"),
        ("중앙대학교",   "연극학과",       "예체능", "서울",   "4년제",  70, 82,  "현실", False, 65, "예체능 최상위 학과"),
        ("홍익대학교",   "회화과",         "예체능", "서울",   "4년제",  73, 85,  "현실", False, 60, "미대 명문, 실기 비중 높음"),
        # ── 교육계 ──
        ("서울교육대학교","초등교육",      "교육",   "서울",   "4년제",  85, 93,  "도전", True,  100,"초등 교사 임용 연계, 안정적"),
        ("한국교원대학교","교육학과",      "교육",   "충북",   "4년제",  80, 90,  "도전", True,  95, "전원 장학금, 교사 임용 강세"),
        # ── 의약 ──
        ("연세대학교",   "치의예과",       "의약",   "서울",   "4년제",  94, 99,  "도전", True,  99, "치과의사 양성"),
        ("경희대학교",   "한의예과",       "의약",   "서울",   "4년제",  88, 95,  "도전", True,  98, "한의사 면허, 서울권 최상위"),
        ("이화여자대학교","약학과",        "의약",   "서울",   "4년제",  87, 94,  "현실", True,  97, "여대, 약사 국가고시 연계"),
        # ── 2년제 전문대 ──
        ("한국폴리텍대학","정보통신",      "이공",   "전국",   "2년제",  40, 65,  "안정", True,  88, "국립, 등록금 저렴, 취업률 최상"),
        ("서울여자간호대","간호학과",      "의약",   "서울",   "2년제",  55, 72,  "안정", False, 97, "간호사 면허, 취업 100% 근접"),
        ("한국관광대학교","항공서비스",    "인문",   "경기",   "2년제",  45, 65,  "안정", False, 85, "항공 승무원 특화"),
        ("동서울대학교", "컴퓨터정보통신", "이공",   "경기",   "2년제",  42, 62,  "안정", False, 80, "IT취업률 우수"),
        ("백석문화대학교","사회복지",      "인문",   "충남",   "2년제",  38, 58,  "안정", False, 75, "복지 분야 취업 강세"),
    ]

    COLS = ["대학", "학과", "계열", "지역", "학위", "점수_하한", "점수_상한", "옵션", "장학금", "취업률", "비고"]
    df_all = pd.DataFrame(UNIV_POOL, columns=COLS)

    # ── 학생 선택 + 점수 입력 ──────────────────────────────────
    st.markdown("#### 1) 학생 선택 및 점수 입력")
    u7c1, u7c2 = st.columns([2, 2])
    with u7c1:
        sel_u7_name = st.selectbox("학생 선택", [s["name"] for s in all_students], key="tab7_student")
        sel_u7_stu = next(s for s in all_students if s["name"] == sel_u7_name)
        sel_u7_id = sel_u7_stu["id"]
        u7_summary = get_student_summary(sel_u7_id)
        st.metric("현재 정답률 기반 점수", f"{u7_summary['correct_rate']}점")
    with u7c2:
        consult_score = st.number_input(
            "상담 점수 입력 (0~100)",
            min_value=0, max_value=100,
            value=int(round(u7_summary["correct_rate"])),
            step=1, key="tab7_score"
        )
        st.caption("실제 모의고사 점수 또는 예상 점수를 입력하세요.")

    # ── 필터 ────────────────────────────────────────────────────
    st.markdown("#### 2) 필터 옵션")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        filter_degree = st.multiselect("학위", ["4년제", "2년제"], default=["4년제", "2년제"], key="f_degree")
    with fc2:
        filter_region = st.multiselect("지역", sorted(df_all["지역"].unique()), default=list(df_all["지역"].unique()), key="f_region")
    with fc3:
        filter_major = st.multiselect("계열", sorted(df_all["계열"].unique()), default=list(df_all["계열"].unique()), key="f_major")
    with fc4:
        filter_option = st.multiselect("옵션", ["도전", "현실", "안정"], default=["도전", "현실", "안정"], key="f_option")

    # ── 점수 범위 필터 + 적용 ────────────────────────────────────
    margin = st.slider("± 점수 여유 범위", 0, 20, 10, key="f_margin")
    st.caption(f"입력 점수 {consult_score}점 기준 ±{margin}점 범위 내 대학을 표시합니다.")

    score_lo = max(0, consult_score - margin)
    score_hi = min(100, consult_score + margin)

    df_filtered = df_all[
        (df_all["점수_하한"] <= score_hi) &
        (df_all["점수_상한"] >= score_lo) &
        (df_all["학위"].isin(filter_degree)) &
        (df_all["지역"].isin(filter_region)) &
        (df_all["계열"].isin(filter_major)) &
        (df_all["옵션"].isin(filter_option))
    ].copy()

    df_filtered["점수범위"] = df_filtered["점수_하한"].astype(str) + "~" + df_filtered["점수_상한"].astype(str)
    df_filtered["장학금"] = df_filtered["장학금"].map({True: "✅", False: "—"})

    st.divider()
    st.markdown(f"#### 3) 추천 결과 — {len(df_filtered)}개 대학")

    if df_filtered.empty:
        st.warning("해당 조건에 맞는 대학이 없습니다. 점수 범위 또는 필터를 조정해 주세요.")
    else:
        # ── 옵션별 탭 ────────────────────────────────────────────
        opt_tabs = st.tabs(["🏆 전체 보기", "🔥 도전 옵션", "✅ 현실 옵션", "🛡️ 안정 옵션"])

        display_cols = ["대학", "학과", "계열", "지역", "학위", "점수범위", "옵션", "장학금", "취업률", "비고"]

        with opt_tabs[0]:
            st.dataframe(
                df_filtered.sort_values(["옵션", "점수_상한"], ascending=[True, False])[display_cols],
                use_container_width=True, hide_index=True)

        for opt_label, opt_tab in zip(["도전", "현실", "안정"], opt_tabs[1:]):
            with opt_tab:
                df_opt = df_filtered[df_filtered["옵션"] == opt_label].sort_values("취업률", ascending=False)[display_cols]
                if df_opt.empty:
                    st.info(f"{opt_label} 옵션 대학이 없습니다.")
                else:
                    st.dataframe(df_opt, use_container_width=True, hide_index=True)

    st.divider()

    # ── 통계 대시보드 ────────────────────────────────────────────
    st.markdown("#### 4) 통계 대시보드")

    if not df_filtered.empty:
        stat1, stat2, stat3, stat4 = st.columns(4)
        stat1.metric("총 대학 수", f"{len(df_filtered)}개")
        stat2.metric("장학금 있는 대학", f"{(df_filtered['장학금']=='✅').sum()}개")
        stat3.metric("평균 취업률", f"{df_filtered['취업률'].mean():.1f}%")
        stat4.metric("최고 취업률", f"{df_filtered['취업률'].max()}%")

        st.markdown("##### 계열별 분포")
        try:
            import altair as alt
            pie_data = df_filtered.groupby("계열").size().reset_index(name="수")
            bar_major = alt.Chart(pie_data).mark_bar().encode(
                x=alt.X("계열:N"),
                y=alt.Y("수:Q"),
                color=alt.Color("계열:N"),
                tooltip=["계열", "수"]
            ).properties(height=220)
            st.altair_chart(bar_major, use_container_width=True)
        except Exception:
            pass

        st.markdown("##### 지역별 분포")
        region_data = df_filtered.groupby("지역").size().reset_index(name="수").sort_values("수", ascending=False)
        st.dataframe(region_data, use_container_width=True, hide_index=True)

        st.markdown("##### 취업률 TOP 10")
        top10 = df_filtered.nlargest(10, "취업률")[["대학", "학과", "계열", "취업률", "점수범위"]].reset_index(drop=True)
        st.dataframe(top10, use_container_width=True, hide_index=True)

    st.divider()

    # ── 3명 비교 ─────────────────────────────────────────────────
    st.markdown("#### 5) 학생 3명 동시 비교")
    st.caption("3명의 현재 점수를 기준으로 각자의 가능 대학 수를 비교합니다.")

    compare_rows = []
    for stu in all_students:
        sm = get_student_summary(stu["id"])
        sc = int(round(sm["correct_rate"]))
        cnt_challenge = len(df_all[(df_all["옵션"]=="도전") & (df_all["점수_하한"]<=sc+10) & (df_all["점수_상한"]>=sc-10)])
        cnt_real = len(df_all[(df_all["옵션"]=="현실") & (df_all["점수_하한"]<=sc+10) & (df_all["점수_상한"]>=sc-10)])
        cnt_safe = len(df_all[(df_all["옵션"]=="안정") & (df_all["점수_하한"]<=sc+10) & (df_all["점수_상한"]>=sc-10)])
        compare_rows.append({
            "학생": stu["name"],
            "현재점수": sc,
            "도전 옵션 수": cnt_challenge,
            "현실 옵션 수": cnt_real,
            "안정 옵션 수": cnt_safe,
            "합계": cnt_challenge + cnt_real + cnt_safe,
        })

    df_compare = pd.DataFrame(compare_rows)
    st.dataframe(df_compare, use_container_width=True, hide_index=True)

    st.divider()

    # ── AI 진학 상담 ─────────────────────────────────────────────
    st.markdown("#### 6) AI 진학 상담 리포트")
    ai_univ_key = f"univ:{sel_u7_id}:{consult_score}"
    cached_univ = get_ai_log(TEACHER_ID, sel_u7_id, "univ_consult", ai_univ_key)

    if st.button("AI 진학 상담 리포트 생성", use_container_width=True, key="gen_univ_report"):
        top5 = df_filtered.nlargest(5, "취업률")[["대학","학과","계열","점수범위","옵션"]].to_string(index=False) if not df_filtered.empty else "해당 없음"
        prompt = f"""
교사가 학생 진학 상담에 활용할 상담 리포트를 작성하라.
[학생: {sel_u7_name} / 학년: {sel_u7_stu['grade']} / 상담 점수: {consult_score}점]
[현재 학습 수준: 총 {u7_summary['total_questions']}문항, 정답률 {u7_summary['correct_rate']}%, 레벨 {u7_summary['level']}]
[필터 기준: 학위={filter_degree}, 계열={filter_major}, 결과={len(df_filtered)}개 대학]
[취업률 상위 5개]
{top5}

요구:
1. 현재 점수 수준에서 현실적인 진로 방향 2가지
2. 추천 대학 3곳 (각 1줄 근거 포함)
3. 점수 향상 시 추가로 고려할 대학 2곳
4. 학생에게 전달할 진학 상담 멘트 (압박 없이, 가능성 중심)
5. 교사가 부모님께 전달할 안내 사항 1개

현실적이고 구체적으로 작성. 낙인/비교/압박 절대 금지.
"""
        content = try_ai_generate(prompt)
        upsert_ai_log(TEACHER_ID, sel_u7_id, "univ_consult", ai_univ_key, content)
        cached_univ = content

    if cached_univ:
        st.write(cached_univ)
    else:
        st.caption("버튼을 눌러 AI 진학 상담 리포트를 생성하세요.")

    st.caption("※ 모든 입시 정보는 참고용이며 실제 입시 결과와 다를 수 있습니다. 반드시 대학 공식 자료를 함께 확인하세요.")

# ─────────────────────────────────────────────────
# TAB 8: 출석 알림
# ─────────────────────────────────────────────────
if _show8:
    st.markdown("### 🔔 출석 알림 & 학습 연속성 모니터링")
    st.caption("최근 학습 기록을 기반으로 학생별 출석 상태를 확인합니다.")

    today = dt.date.today()
    con = get_conn()
    try:
        attendance_rows = []
        for stu in all_students:
            last_row = con.execute(
                "SELECT MAX(created_at) as last_dt FROM study_sessions WHERE student_id=?",
                (stu["id"],)
            ).fetchone()
            last_dt_str = last_row["last_dt"] if last_row else None

            # 연속 학습일 계산
            streak_rows = con.execute(
                "SELECT DISTINCT substr(created_at,1,10) as d FROM study_sessions WHERE student_id=? ORDER BY d DESC",
                (stu["id"],)
            ).fetchall()
            streak = 0
            if streak_rows:
                dates = [dt.date.fromisoformat(r["d"]) for r in streak_rows]
                streak = 1
                for i in range(1, len(dates)):
                    if (dates[i-1] - dates[i]).days == 1:
                        streak += 1
                    else:
                        break
                if dates[0] < today - dt.timedelta(days=1):
                    streak = 0

            # 최근 7일 학습 횟수
            week_ago = (today - dt.timedelta(days=6)).isoformat()
            cnt_7 = con.execute(
                "SELECT COUNT(DISTINCT substr(created_at,1,10)) FROM study_sessions WHERE student_id=? AND substr(created_at,1,10)>=?",
                (stu["id"], week_ago)
            ).fetchone()[0]

            if last_dt_str:
                last_date = dt.date.fromisoformat(last_dt_str[:10])
                days_ago = (today - last_date).days
                if days_ago == 0:
                    status = "✅ 오늘 학습"
                    status_level = "good"
                elif days_ago <= 2:
                    status = f"🟡 {days_ago}일 전 학습"
                    status_level = "warn"
                elif days_ago <= 5:
                    status = f"🟠 {days_ago}일 미학습"
                    status_level = "danger"
                else:
                    status = f"🔴 {days_ago}일 이상 미학습"
                    status_level = "urgent"
            else:
                last_date = None
                days_ago = 999
                status = "⚫ 학습 기록 없음"
                status_level = "none"

            attendance_rows.append({
                "학생": stu["name"],
                "학년": stu["grade"],
                "마지막 학습일": str(last_date) if last_date else "없음",
                "경과일": days_ago if days_ago < 999 else "-",
                "연속 학습일": f"🔥 {streak}일" if streak >= 1 else "0일",
                "이번주 학습 횟수": f"{cnt_7}회",
                "상태": status,
            })
    finally:
        con.close()

    df_att = pd.DataFrame(attendance_rows)
    st.dataframe(df_att, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 📅 학생별 최근 30일 학습 캘린더")
    sel_att_name = st.selectbox("학생 선택", [s["name"] for s in all_students], key="att_student_sel")
    sel_att_id = next(s["id"] for s in all_students if s["name"] == sel_att_name)

    con2 = get_conn()
    try:
        cal_rows = con2.execute(
            "SELECT substr(created_at,1,10) as d, COUNT(*) as cnt FROM study_sessions WHERE student_id=? AND substr(created_at,1,10)>=? GROUP BY d ORDER BY d",
            (sel_att_id, (today - dt.timedelta(days=29)).isoformat())
        ).fetchall()
    finally:
        con2.close()

    if cal_rows:
        cal_data = {r["d"]: r["cnt"] for r in cal_rows}
        cal_display = []
        for i in range(30):
            d = (today - dt.timedelta(days=29-i)).isoformat()
            cal_display.append({"날짜": d, "학습 횟수": cal_data.get(d, 0)})
        df_cal = pd.DataFrame(cal_display).set_index("날짜")
        st.bar_chart(df_cal)
    else:
        st.info("최근 30일간 학습 기록이 없습니다.")

    st.divider()
    st.markdown("#### 🚨 미학습 알림 대상")
    alert_students = [r for r in attendance_rows if isinstance(r["경과일"], int) and r["경과일"] >= 3]
    if alert_students:
        for r in alert_students:
            st.error(f"⚠️ **{r['학생']}** — {r['경과일']}일 동안 학습 없음. 확인이 필요합니다.")
    else:
        st.success("모든 학생이 최근 3일 내에 학습했습니다! 👍")

# ─────────────────────────────────────────────────
# TAB 9: 레이더 차트
# ─────────────────────────────────────────────────
if _show9:
    st.markdown("### 📡 과목별 역량 레이더 차트")
    st.caption("학생의 과목별 정답률을 레이더(방사형) 차트로 시각화합니다.")

    RADAR_SUBJECTS = ["국어", "영어", "수학", "과학", "사회", "한자"]

    sel_radar_name = st.selectbox("학생 선택", [s["name"] for s in all_students], key="radar_student_sel")
    sel_radar_id = next(s["id"] for s in all_students if s["name"] == sel_radar_name)

    con3 = get_conn()
    try:
        subj_rows = con3.execute(
            """SELECT ss.subject, COUNT(q.id) as total, SUM(CASE WHEN q.is_correct=1 THEN 1 ELSE 0 END) as correct
               FROM study_sessions ss JOIN questions q ON q.session_id=ss.id
               WHERE ss.student_id=?
               GROUP BY ss.subject""",
            (sel_radar_id,)
        ).fetchall()
    finally:
        con3.close()

    subj_map = {}
    for r in subj_rows:
        total = r["total"] or 0
        correct = r["correct"] or 0
        subj_map[r["subject"]] = round(correct / total * 100, 1) if total > 0 else 0

    radar_values = [subj_map.get(s, 0) for s in RADAR_SUBJECTS]
    radar_df = pd.DataFrame({"과목": RADAR_SUBJECTS, "정답률(%)": radar_values})

    col_r1, col_r2 = st.columns([3, 2])
    with col_r1:
        try:
            import math
            import plotly.graph_objects as go  # type: ignore
            fig = go.Figure(data=go.Scatterpolar(
                r=radar_values + [radar_values[0]],
                theta=RADAR_SUBJECTS + [RADAR_SUBJECTS[0]],
                fill='toself',
                name=sel_radar_name,
                line_color='rgba(99,110,250,0.9)',
                fillcolor='rgba(99,110,250,0.3)',
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=True,
                title=f"{sel_radar_name} 과목별 정답률 레이더",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            # plotly 없을 경우 bar chart fallback
            st.bar_chart(radar_df.set_index("과목")["정답률(%)"])
            st.caption("레이더 차트를 위해 plotly를 설치하면 더 보기 좋습니다: pip install plotly")

    with col_r2:
        st.markdown(f"#### {sel_radar_name} 과목별 현황")
        for i, subj in enumerate(RADAR_SUBJECTS):
            rate = radar_values[i]
            if rate >= 80:
                icon = "🟢"
            elif rate >= 60:
                icon = "🟡"
            elif rate >= 40:
                icon = "🟠"
            else:
                icon = "🔴"
            st.markdown(f"{icon} **{subj}**: {rate}%")

    st.divider()
    st.markdown("#### 학생 3명 과목별 비교 (선택 과목)")
    compare_subj = st.selectbox("비교 과목 선택", RADAR_SUBJECTS, key="compare_subj")

    compare_data = []
    for stu in all_students:
        con4 = get_conn()
        try:
            r2 = con4.execute(
                """SELECT COUNT(q.id) as total, SUM(CASE WHEN q.is_correct=1 THEN 1 ELSE 0 END) as correct
                   FROM study_sessions ss JOIN questions q ON q.session_id=ss.id
                   WHERE ss.student_id=? AND ss.subject=?""",
                (stu["id"], compare_subj)
            ).fetchone()
        finally:
            con4.close()
        total = r2["total"] or 0
        correct = r2["correct"] or 0
        rate = round(correct / total * 100, 1) if total > 0 else 0
        compare_data.append({"학생": stu["name"], f"{compare_subj} 정답률(%)": rate, "총 문항": total})

    df_compare_subj = pd.DataFrame(compare_data)
    st.dataframe(df_compare_subj, use_container_width=True, hide_index=True)
    st.bar_chart(df_compare_subj.set_index("학생")[f"{compare_subj} 정답률(%)"])
    st.caption("※ 비교는 상대적 우열이 아닌 각 학생의 현재 상태 파악을 위한 것입니다.")
