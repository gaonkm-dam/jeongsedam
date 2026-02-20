import streamlit as st
import sqlite3
import pandas as pd
import datetime as dt
import random
import re
from typing import Optional, Dict, Any, List, Tuple

# =========================
# 고정: 기존 DB 그대로 사용
# =========================
DB_PATH = "student_system.db"

# =========================
# 모바일 우선 UI 기본
# =========================
st.set_page_config(
    page_title="학부모",
    page_icon="👨‍👩‍👧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# wide 레이아웃에서 콘텐츠 최대 너비 제한 + 태블릿 최적화
st.markdown("""
<style>
.block-container { max-width: 860px !important; padding: 1rem 1rem 2rem 1rem !important; margin: auto; }
.stButton > button {
    min-height: 48px !important;
    font-size: 1rem !important;
    border-radius: 10px !important;
    width: 100% !important;
    margin-bottom: 4px !important;
}
.stSelectbox [data-baseweb="select"] { min-height: 48px !important; font-size: 1rem !important; }
.stTextInput > div > div > input { min-height: 44px !important; font-size: 1rem !important; }
[data-testid="metric-container"] {
    background: #f8f9fa; border-radius: 12px; padding: 12px !important; margin-bottom: 8px;
}
.streamlit-expanderHeader { font-size: 1rem !important; min-height: 44px; }
.dataframe { font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)

# =========================
# DB 유틸
# =========================
def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def table_exists(con, name: str) -> bool:
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def colnames(con, table: str) -> List[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    return [r[1] for r in rows]  # (cid, name, type, notnull, dflt_value, pk)

def ensure_parent_v2_tables():
    """기존 학생 DB 구조는 절대 안 건드리고, 학부모 기능용 '추가 테이블'만 생성."""
    con = get_conn()
    cur = con.cursor()

    # 학부모 데이터 제공 동의
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_data_consent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        consent_mode TEXT NOT NULL,  -- none | anon_policy | full_edu
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(parent_id, student_id)
    )
    """)

    # 학부모 오늘 동기부여 로그
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_motivation_log_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 월 도서 추천 + 로그
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_book_reco_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        year_month TEXT NOT NULL,         -- YYYY-MM
        idx INTEGER NOT NULL,             -- 1..5
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(parent_id, student_id, year_month, idx)
    )
    """)

    # AI 가이드/대화질문/함께하는 행동/정서지원/리포트 저장
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_ai_log_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        log_type TEXT NOT NULL,     -- guide | talk | together | support | daily_report | monthly_report
        period_key TEXT NOT NULL,   -- YYYY-MM-DD or YYYY-MM
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(parent_id, student_id, log_type, period_key)
    )
    """)

    # 대학 추천 결과 저장 (정책 시연용: 추천 결과를 그대로 저장)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_university_reco_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        score REAL NOT NULL,
        degree_type TEXT NOT NULL,      -- 4년제 | 2년제
        region TEXT NOT NULL,
        track TEXT NOT NULL,            -- 계열
        university_name TEXT NOT NULL,
        department TEXT NOT NULL,
        avg_score REAL NOT NULL,
        min_score REAL NOT NULL,
        max_score REAL NOT NULL,
        gap REAL NOT NULL,
        url TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(parent_id, student_id, score, university_name, department)
    )
    """)

    # 목표대학 설정 + 방향성 저장
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_goal_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        goal_university TEXT NOT NULL,
        goal_department TEXT,
        goal_score REAL NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(parent_id, student_id)
    )
    """)

    con.commit()
    con.close()

ensure_parent_v2_tables()

# =========================
# 학생 데이터: "있는 구조 그대로" 읽기
# - study_sessions + questions JOIN으로 실제 데이터 가져오기
# =========================

def fetch_sessions(con, student_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    """
    study_sessions + questions 테이블을 JOIN하여 학생 학습 데이터를 반환.
    - OpenAI ON/OFF와 무관하게 항상 DB에 쌓인 데이터를 조회
    - subject: study_sessions.subject
    - is_correct: questions.is_correct
    - created_at: study_sessions.created_at
    """
    if not table_exists(con, "study_sessions"):
        return pd.DataFrame()

    sql = """
        SELECT
            ss.subject          AS subject,
            ss.created_at       AS created_at,
            q.is_correct        AS is_correct,
            q.question_text     AS concept
        FROM study_sessions ss
        LEFT JOIN questions q ON q.session_id = ss.id
        WHERE ss.student_id = ?
    """
    params: list = [student_id]

    if start_date:
        sql += " AND date(ss.created_at) >= date(?)"
        params.append(start_date)
    if end_date:
        sql += " AND date(ss.created_at) <= date(?)"
        params.append(end_date)

    try:
        df = pd.read_sql(sql, con, params=tuple(params))
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["day"] = df["created_at"].dt.date.astype(str)
    df["subject"] = df["subject"].fillna("미분류")
    df["concept"] = df["concept"].fillna("미분류")
    df["is_correct"] = pd.to_numeric(df["is_correct"], errors="coerce")

    return df


def fetch_session_summary(con, student_id: int) -> Dict[str, Any]:
    """
    study_sessions 집계 기반 전체 요약.
    OpenAI ON/OFF와 무관하게 항상 DB 데이터 반환.
    """
    if not table_exists(con, "study_sessions"):
        return {"total_questions": 0, "correct_count": 0, "accuracy": 0.0,
                "study_days": 0, "last_study_date": None, "level": "Beginner"}
    try:
        row = con.execute("""
            SELECT
                COALESCE(SUM(total_questions), 0) AS tq,
                COALESCE(SUM(correct_count), 0)   AS cc,
                COUNT(DISTINCT date(created_at))  AS days,
                MAX(created_at)                   AS last_dt
            FROM study_sessions WHERE student_id=?
        """, (student_id,)).fetchone()
    except Exception:
        return {"total_questions": 0, "correct_count": 0, "accuracy": 0.0,
                "study_days": 0, "last_study_date": None, "level": "Beginner"}

    tq   = row[0] or 0
    cc   = row[1] or 0
    days = row[2] or 0
    last = row[3]
    acc  = round(cc / tq * 100, 1) if tq > 0 else 0.0

    if tq >= 500:   level = "Advanced"
    elif tq >= 201: level = "Intermediate"
    elif tq >= 51:  level = "Basic"
    else:           level = "Beginner"

    return {"total_questions": tq, "correct_count": cc, "accuracy": acc,
            "study_days": days, "last_study_date": last, "level": level}

# =========================
# 학부모(데모) 로그인/연결
# - 기존 parents 테이블이 있으면 사용
# - 없으면 parent_id=1, student_id=1 데모로 고정
# =========================
def get_default_student_id(con) -> int:
    # students 테이블 있으면 1명이라도 가져오고, 없으면 1
    if table_exists(con, "students"):
        try:
            df = pd.read_sql("SELECT id FROM students ORDER BY id ASC LIMIT 1", con)
            if not df.empty:
                return int(df.iloc[0]["id"])
        except Exception:
            pass
    return 1

def sidebar_demo_login() -> Tuple[int, int]:
    """
    returns (parent_id, student_id)
    로그인 전: 데모 버튼 3개
    로그인 후: 이름 표시 + 로그아웃 버튼
    """
    # 세션 초기화
    if "parent_id" not in st.session_state:
        st.session_state["parent_id"] = None
    if "parent_student_id" not in st.session_state:
        st.session_state["parent_student_id"] = None
    if "parent_name_display" not in st.session_state:
        st.session_state["parent_name_display"] = None
    if "parent_short_name" not in st.session_state:
        st.session_state["parent_short_name"] = None  # 예: "김민준 학부모"

    DEMO_PARENTS = [
        ("김민준 학부모", "parent1@test.com", "pass1"),
        ("이서연 학부모", "parent2@test.com", "pass2"),
        ("박지호 학부모", "parent3@test.com", "pass3"),
    ]

    with st.sidebar:
        if not st.session_state.get("parent_id"):
            # ── 로그인 전 ──────────────────────────────
            st.markdown("### 👨‍👩‍👧 학부모 로그인")
            st.caption("버튼 클릭 한 번으로 바로 입장합니다.")
            con = get_conn()
            for label, email, pw in DEMO_PARENTS:
                if st.button(f"👨‍👩‍👧 {label}로 입장", use_container_width=True, key=f"pdemo_{email}"):
                    try:
                        df = pd.read_sql(
                            "SELECT * FROM parents WHERE email=? LIMIT 1", con, params=(email,)
                        )
                        if not df.empty:
                            row = df.iloc[0].to_dict()
                            st.session_state["parent_id"] = int(row["id"])

                            df_link = pd.read_sql(
                                """SELECT ps.student_id, s.name
                                   FROM parent_student ps
                                   JOIN students s ON s.id = ps.student_id
                                   WHERE ps.parent_id = ?
                                   ORDER BY ps.id ASC LIMIT 1""",
                                con, params=(int(row["id"]),)
                            )
                            if not df_link.empty:
                                st.session_state["parent_student_id"] = int(df_link.iloc[0]["student_id"])
                                student_name = df_link.iloc[0]["name"]
                            else:
                                st.session_state["parent_student_id"] = 1
                                student_name = "연결 없음"

                            st.session_state["parent_short_name"] = label          # "김민준 학부모"
                            st.session_state["parent_name_display"] = f"{label} (자녀: {student_name})"
                            st.rerun()
                    except Exception as e:
                        st.error(f"로그인 오류: {e}")
            con.close()
        else:
            # ── 로그인 후 ──────────────────────────────
            st.success(f"✅ {st.session_state['parent_name_display']}")
            st.divider()
            if st.button("🚪 로그아웃", use_container_width=True, key="parent_logout"):
                st.session_state["parent_id"] = None
                st.session_state["parent_student_id"] = None
                st.session_state["parent_name_display"] = None
                st.session_state["parent_short_name"] = None
                st.rerun()

    # fallback: 로그인 안 됐으면 None 반환
    pid = st.session_state.get("parent_id")
    sid = st.session_state.get("parent_student_id")
    return pid, sid

PARENT_ID, STUDENT_ID = sidebar_demo_login()

# =========================
# 동의(민감데이터) UI + 저장
# =========================
CONSENT_OPTIONS = [
    ("none", "데이터 제공 안함 (기본값)"),
    ("anon_policy", "익명화된 데이터만 정책 연구용 제공"),
    ("full_edu", "전체 데이터 제공 (교육 개선 목적)"),
]

def get_consent(parent_id: int, student_id: int) -> str:
    con = get_conn()
    try:
        df = pd.read_sql(
            "SELECT consent_mode FROM parent_data_consent WHERE parent_id=? AND student_id=? LIMIT 1",
            con, params=(parent_id, student_id)
        )
        if df.empty:
            return "none"
        return str(df.iloc[0]["consent_mode"])
    finally:
        con.close()

def save_consent(parent_id: int, student_id: int, mode: str):
    con = get_conn()
    try:
        con.execute("""
        INSERT INTO parent_data_consent(parent_id, student_id, consent_mode)
        VALUES(?,?,?)
        ON CONFLICT(parent_id, student_id) DO UPDATE SET
          consent_mode=excluded.consent_mode,
          updated_at=CURRENT_TIMESTAMP
        """, (parent_id, student_id, mode))
        con.commit()
    finally:
        con.close()

# =========================
# 상단 동기부여 (새로고침마다 랜덤)
# =========================
MOTIVATIONS = [
    "오늘의 ‘작은 반복’이 내일의 자신감을 만듭니다.",
    "아이의 속도는 다릅니다. 목표는 ‘지속’입니다.",
    "완벽이 아니라 ‘다시 앉는 힘’을 키우는 중입니다.",
    "부모님이 지치지 않는 것이, 아이에게 가장 큰 안전입니다.",
    "오늘은 조금만. 대신 내일도 하게 만드는 게 목표입니다.",
    "칭찬은 결과보다 ‘과정의 반복’을 잡아주는 게 효과적입니다.",
    "아이를 고치는 게 아니라, 환경을 정리하는 일부터 시작합니다.",
    "오늘 한 번 더 버틴 게 이미 성과입니다.",
]

def save_motivation_log(parent_id: int, student_id: int, msg: str):
    con = get_conn()
    try:
        con.execute(
            "INSERT INTO parent_motivation_log_v2(parent_id, student_id, message) VALUES(?,?,?)",
            (parent_id, student_id, msg)
        )
        con.commit()
    finally:
        con.close()

# =========================
# 월 도서 추천 (5권, 고정 저장)
# =========================
BOOK_POOL = [
    ("공부의 기술", "저자미상"),
    ("메타인지 학습법", "저자미상"),
    ("부모의 말", "저자미상"),
    ("성장 마인드셋", "저자미상"),
    ("습관의 힘", "저자미상"),
    ("집중력의 힘", "저자미상"),
    ("학습 코칭 전략", "저자미상"),
    ("부모 심리학", "저자미상"),
    ("아이의 자존감", "저자미상"),
    ("부모 교육 가이드", "저자미상"),
    ("생각하는 힘", "저자미상"),
    ("기억력 공부법", "저자미상"),
]

def year_month_now() -> str:
    return dt.date.today().strftime("%Y-%m")

def get_monthly_books(parent_id: int, student_id: int, ym: str) -> pd.DataFrame:
    con = get_conn()
    try:
        df = pd.read_sql("""
          SELECT idx, title, author
          FROM parent_book_reco_v2
          WHERE parent_id=? AND student_id=? AND year_month=?
          ORDER BY idx ASC
        """, con, params=(parent_id, student_id, ym))
        return df
    finally:
        con.close()

def set_monthly_books(parent_id: int, student_id: int, ym: str, force_refresh: bool = False) -> pd.DataFrame:
    existing = get_monthly_books(parent_id, student_id, ym)
    if (not existing.empty) and (not force_refresh):
        return existing

    # 5권 고정 추천 (중복 제거)
    picks = random.sample(BOOK_POOL, k=5) if len(BOOK_POOL) >= 5 else BOOK_POOL[:5]

    con = get_conn()
    try:
        # force_refresh면 기존 삭제 후 재삽입(중복 방지)
        con.execute("DELETE FROM parent_book_reco_v2 WHERE parent_id=? AND student_id=? AND year_month=?",
                    (parent_id, student_id, ym))
        for i, (title, author) in enumerate(picks, start=1):
            con.execute("""
              INSERT OR REPLACE INTO parent_book_reco_v2(parent_id, student_id, year_month, idx, title, author)
              VALUES(?,?,?,?,?,?)
            """, (parent_id, student_id, ym, i, title, author))
        con.commit()
    finally:
        con.close()

    return get_monthly_books(parent_id, student_id, ym)

# =========================
# 오늘/7일 요약 + 취약개념
# =========================
def today_key() -> str:
    return dt.date.today().isoformat()

def get_today_summary(student_id: int) -> Dict[str, Any]:
    con = get_conn()
    try:
        df = fetch_sessions(con, student_id, start_date=today_key(), end_date=today_key())
    finally:
        con.close()

    if df.empty:
        return {"sessions": 0, "questions": 0, "correct_rate": None, "wrong_rate": None, "subjects": 0}

    # 세션 수: 테이블에 세션개념이 없으니 "학습 기록 수"로 대체
    questions = len(df)
    subjects = df["subject"].nunique()

    # is_correct 컬럼이 전부 None이면 정답률 계산 불가
    valid = df["is_correct"].dropna()
    if valid.empty:
        correct_rate = None
        wrong_rate = None
    else:
        correct_rate = round(valid.mean() * 100, 1)
        wrong_rate = round(100 - correct_rate, 1)

    return {
        "sessions": questions,   # 세션 정의가 없으면 기록수로 표시(정확히는 '오늘 학습 기록 수')
        "questions": questions,
        "correct_rate": correct_rate,
        "wrong_rate": wrong_rate,
        "subjects": int(subjects),
    }

def get_7d_summary(student_id: int) -> pd.DataFrame:
    start = (dt.date.today() - dt.timedelta(days=6)).isoformat()
    end = dt.date.today().isoformat()

    con = get_conn()
    try:
        df = fetch_sessions(con, student_id, start_date=start, end_date=end)
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame()

    g = df.groupby("day").agg(
        questions=("day", "count"),
        subjects=("subject", "nunique"),
        correct_rate=("is_correct", lambda s: (s.dropna().mean()*100) if s.dropna().size else None)
    ).reset_index()

    # 날짜 빠진 날은 0으로 채우기
    all_days = [(dt.date.today() - dt.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    g_map = {r["day"]: r for _, r in g.iterrows()}
    rows = []
    for d in all_days:
        if d in g_map:
            rows.append(g_map[d])
        else:
            rows.append({"day": d, "questions": 0, "subjects": 0, "correct_rate": None})
    return pd.DataFrame(rows)

def get_weak_concepts_today(student_id: int) -> pd.DataFrame:
    con = get_conn()
    try:
        df = fetch_sessions(con, student_id, start_date=today_key(), end_date=today_key())
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame()

    # 정답 데이터 없으면 '문항 수' 기준으로 표시
    if df["is_correct"].dropna().empty:
        g = df.groupby("concept").size().reset_index(name="count").sort_values("count", ascending=False)
        return g

    g = df.groupby("concept").agg(
        correct_rate=("is_correct", lambda s: round(s.dropna().mean()*100, 1) if s.dropna().size else 0.0),
        questions=("concept", "count")
    ).reset_index().sort_values(["correct_rate", "questions"], ascending=[True, False])

    return g.head(12)

def get_subject_stats(student_id: int) -> List[Dict]:
    con = get_conn()
    try:
        df = fetch_sessions(con, student_id)
    finally:
        con.close()
    if df.empty:
        return []
    if "subject" not in df.columns:
        return []
    if df["is_correct"].dropna().empty:
        g = df.groupby("subject").size().reset_index(name="total_questions")
        g["correct_rate"] = 0.0
    else:
        g = df.groupby("subject").agg(
            total_questions=("subject", "count"),
            correct_rate=("is_correct", lambda s: round(s.dropna().mean() * 100, 1) if s.dropna().size > 0 else 0.0)
        ).reset_index()
    return g.to_dict(orient="records")

# =========================
# AI 가이드 (OpenAI ON/OFF 대응)
# - 프로젝트에 config.USE_OPENAI가 있어도 여기서는 건드리지 않음
# - openai_helper가 있으면 import 시도, 실패하면 템플릿으로 대체
# =========================
def try_ai_generate(prompt: str) -> str:
    # session_state["use_openai"] ON일 때만 AI 호출
    if st.session_state.get("use_openai", False):
        try:
            import parent_ai_helper  # type: ignore
            result = parent_ai_helper.generate_ai_text(prompt)
            if result:
                return result
        except Exception:
            pass

    # OFF 상태이거나 AI 호출 실패 시 fallback 템플릿
    return (
        "오늘은 '압박'이 아니라 '루틴 유지'가 핵심입니다.\n"
        "- 아이가 멈추면: 원인을 추궁하기보다, 오늘 가능한 최소 단위를 정해 주세요.\n"
        "- 정답률이 낮아도: '왜 틀렸어?' 대신 '어디에서 막혔는지 같이 찾자'가 효과적입니다.\n"
        "- 오늘의 목표: 10분이라도 앉는 경험을 만들고 끝내는 것.\n"
    )

def upsert_ai_log(parent_id: int, student_id: int, log_type: str, period_key: str, content: str):
    con = get_conn()
    try:
        con.execute("""
        INSERT INTO parent_ai_log_v2(parent_id, student_id, log_type, period_key, content)
        VALUES(?,?,?,?,?)
        ON CONFLICT(parent_id, student_id, log_type, period_key) DO UPDATE SET
          content=excluded.content,
          created_at=CURRENT_TIMESTAMP
        """, (parent_id, student_id, log_type, period_key, content))
        con.commit()
    finally:
        con.close()

def get_ai_log(parent_id: int, student_id: int, log_type: str, period_key: str) -> Optional[str]:
    con = get_conn()
    try:
        df = pd.read_sql("""
          SELECT content FROM parent_ai_log_v2
          WHERE parent_id=? AND student_id=? AND log_type=? AND period_key=?
          ORDER BY created_at DESC LIMIT 1
        """, con, params=(parent_id, student_id, log_type, period_key))
        if df.empty:
            return None
        return str(df.iloc[0]["content"])
    finally:
        con.close()

# =========================
# 심리(요구사항: "심리학 항목" 기반)
# - 기존 psychological_tests 테이블이 있으면 활용
# - 없으면 "데이터 없음" 처리
# - 오늘/7일 그래프 + AI 분석 + 날짜 검색
# =========================
PSY_ITEMS = [f"q{i}" for i in range(1, 21)]  # q1~q20, 실제 DB 컬럼명과 일치

# q1~q20 → 사람이 읽기 쉬운 표시 이름 (학생 페이지 문항 순서와 동일)
PSY_LABEL_MAP = {
    "q1":  "학교생활 즐거움",
    "q2":  "친구 관계",
    "q3":  "공부 집중력",
    "q4":  "스트레스 관리",
    "q5":  "긍정적 사고",
    "q6":  "부모 대화",
    "q7":  "자신감",
    "q8":  "미래 계획",
    "q9":  "걱정·불안",
    "q10": "감정 조절",
    "q11": "수면 충분",
    "q12": "규칙적 생활",
    "q13": "취미·여가",
    "q14": "목표 향한 노력",
    "q15": "도전 의지",
    "q16": "배려심",
    "q17": "새로운 도전",
    "q18": "문제 해결",
    "q19": "책임감",
    "q20": "행복감",
}

def detect_psych_table(con) -> Optional[str]:
    # 프로젝트마다 이름이 다를 수 있어 후보 탐색
    candidates = ["psychological_tests", "psychology_tests", "psychology", "psych_tests"]
    for t in candidates:
        if table_exists(con, t):
            return t
    return None

def fetch_psych(con, student_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    t = detect_psych_table(con)
    if not t:
        return pd.DataFrame()

    cols = colnames(con, t)
    cols_l = {c.lower(): c for c in cols}

    sid_col = cols_l.get("student_id") or cols_l.get("student") or "student_id"
    # psychological_tests 는 test_date, 다른 테이블은 created_at 사용
    created_col = (cols_l.get("test_date") or cols_l.get("created_at")
                   or cols_l.get("date") or cols_l.get("timestamp") or "test_date")

    # 항목 컬럼명 매핑 (없으면 빈 데이터)
    item_cols = {}
    for item in PSY_ITEMS:
        key = item.lower()
        for c in cols:
            if key in c.lower():
                item_cols[item] = c
                break

    # 최소 1개 항목이라도 있어야 의미
    if not item_cols:
        return pd.DataFrame()

    select_cols = [f"{created_col} AS created_at"] + [f"{v} AS `{k}`" for k, v in item_cols.items()]
    sql = f"SELECT {', '.join(select_cols)} FROM {t} WHERE {sid_col}=?"
    params = [student_id]
    if start_date:
        sql += f" AND date({created_col}) >= date(?)"
        params.append(start_date)
    if end_date:
        sql += f" AND date({created_col}) <= date(?)"
        params.append(end_date)

    df = pd.read_sql(sql, con, params=tuple(params))
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["day"] = df["created_at"].dt.date.astype(str)
    return df

def psych_today_and_week(student_id: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    start = (dt.date.today() - dt.timedelta(days=6)).isoformat()
    end = dt.date.today().isoformat()
    con = get_conn()
    try:
        df_week = fetch_psych(con, student_id, start_date=start, end_date=end)
        df_today = fetch_psych(con, student_id, start_date=end, end_date=end)
    finally:
        con.close()
    return df_today, df_week

def ai_analyze_psych(df_today: pd.DataFrame, df_week: pd.DataFrame) -> str:
    # 데이터 요약
    def summarize(df: pd.DataFrame) -> str:
        if df.empty:
            return "데이터 없음"
        last = df.sort_values("created_at").iloc[-1]
        parts = []
        for item in PSY_ITEMS:
            if item in df.columns:
                v = last.get(item)
                if pd.notna(v):
                    parts.append(f"{item}:{v}")
        return ", ".join(parts) if parts else "데이터 부족"

    prompt = f"""
너는 학부모를 돕는 교육 코치다. 낙인/진단 표현 금지. 동행/지지/루틴 관점으로만.
[오늘 심리 요약] {summarize(df_today)}
[최근 7일 요약] {summarize(df_week)}
요구:
1) 오늘 아이에게 도움이 되는 말 2개(질문형 포함)
2) 오늘 부모가 할 행동 2개(현실적, 10분 단위)
3) 위험/주의 같은 단어 대신 '지원 필요도' 관점 문장 1개
"""
    return try_ai_generate(prompt)

# =========================
# 대학 추천(필터+슬라이더/직접입력+여러 대학 리스트+링크)
# - 실제 공공데이터/API는 다음 단계. 지금은 시연 가능한 구조를 먼저 완성.
# =========================
UNIV_DATA = [
    # (대학, 학과, 유형, 지역, 계열, 평균, 범위(min,max), url)
    ("국민대학교", "자동차공학과", "4년제", "서울", "공학", 79.5, (76, 83), "https://www.kookmin.ac.kr"),
    ("단국대학교", "경영학과", "4년제", "경기", "상경", 75.0, (72, 78), "https://www.dankook.ac.kr"),
    ("세종대학교", "경영학과", "4년제", "서울", "상경", 82.0, (79, 85), "https://www.sejong.ac.kr"),
    ("가천대학교", "컴퓨터공학과", "4년제", "경기", "공학", 74.0, (71, 77), "https://www.gachon.ac.kr"),
    ("명지대학교", "경영학과", "4년제", "서울", "상경", 72.0, (69, 75), "https://www.mju.ac.kr"),
    ("한성대학교", "IT융합", "4년제", "서울", "공학", 70.0, (67, 73), "https://www.hansung.ac.kr"),
    ("서울과학기술대학교", "기계시스템디자인공학과", "4년제", "서울", "공학", 84.0, (81, 87), "https://www.seoultech.ac.kr"),

    ("수도권전문대학", "IT", "2년제", "서울", "공학", 65.0, (62, 68), "https://www.ac.kr"),
    ("수도권전문대학", "간호", "2년제", "서울", "보건", 66.0, (63, 69), "https://www.ac.kr"),
    ("경기전문대학", "호텔", "2년제", "경기", "서비스", 64.0, (61, 67), "https://www.ac.kr"),
    ("인천전문대학", "항공", "2년제", "인천", "서비스", 67.0, (64, 70), "https://www.ac.kr"),
    ("부산전문대학", "디자인", "2년제", "부산", "예체능", 63.0, (60, 66), "https://www.ac.kr"),
]

REGIONS = ["전지역", "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
TRACKS = ["전체", "공학", "상경", "인문", "자연", "보건", "교육", "예체능", "서비스"]

def compute_current_score(student_id: int) -> float:
    con = get_conn()
    try:
        df = fetch_sessions(con, student_id)
    finally:
        con.close()
    if df.empty or df["is_correct"].dropna().empty:
        return 0.0
    return round(df["is_correct"].dropna().mean() * 100, 1)

def recommend_universities(score: float, degree_filter: str, region_filter: str, track_filter: str, limit: int = 20) -> pd.DataFrame:
    rows = []
    for (u, d, deg, reg, tr, avg, (mn, mx), url) in UNIV_DATA:
        if degree_filter != "전체" and deg != degree_filter:
            continue
        if region_filter != "전지역" and reg != region_filter:
            continue
        if track_filter != "전체" and tr != track_filter:
            continue

        gap = round(score - float(avg), 1)

        # "갈 수 있을 법한 여러 개"를 위해: 범위와 격차 기반으로 넓게 잡되, 너무 먼 건 제외
        # - 범위 안이면 우선
        # - 범위 밖이어도 ±8 이내는 후보로 포함
        in_range = (score >= mn and score <= mx)
        if (not in_range) and (abs(score - avg) > 8):
            continue

        rows.append({
            "대학명": u,
            "학과": d,
            "유형": deg,
            "지역": reg,
            "계열": tr,
            "평균 점수": float(avg),
            "합격 범위": f"{mn}~{mx}",
            "점수 격차": gap,
            "링크": url,
            "_in_range": 1 if in_range else 0,
            "_abs_gap": abs(score - avg)
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values(by=["_in_range", "_abs_gap"], ascending=[False, True]).head(limit)
    df = df.drop(columns=["_in_range", "_abs_gap"])
    return df

def save_university_results(parent_id: int, student_id: int, score: float, df: pd.DataFrame):
    if df.empty:
        return
    con = get_conn()
    try:
        for _, r in df.iterrows():
            # 평균/범위 파싱
            rng = str(r["합격 범위"])
            m = re.findall(r"(\d+)", rng)
            mn = float(m[0]) if len(m) > 0 else 0.0
            mx = float(m[1]) if len(m) > 1 else mn

            con.execute("""
            INSERT OR IGNORE INTO parent_university_reco_v2(
              parent_id, student_id, score,
              degree_type, region, track,
              university_name, department,
              avg_score, min_score, max_score, gap, url
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                parent_id, student_id, float(score),
                str(r["유형"]), str(r["지역"]), str(r["계열"]),
                str(r["대학명"]), str(r["학과"]),
                float(r["평균 점수"]), float(mn), float(mx), float(r["점수 격차"]), str(r["링크"])
            ))
        con.commit()
    finally:
        con.close()

# =========================
# 목표대학 방향 기능
# =========================
def save_goal(parent_id: int, student_id: int, goal_u: str, goal_d: str, goal_score: float):
    con = get_conn()
    try:
        con.execute("""
        INSERT INTO parent_goal_v2(parent_id, student_id, goal_university, goal_department, goal_score)
        VALUES(?,?,?,?,?)
        ON CONFLICT(parent_id, student_id) DO UPDATE SET
          goal_university=excluded.goal_university,
          goal_department=excluded.goal_department,
          goal_score=excluded.goal_score,
          updated_at=CURRENT_TIMESTAMP
        """, (parent_id, student_id, goal_u, goal_d, float(goal_score)))
        con.commit()
    finally:
        con.close()

def get_goal(parent_id: int, student_id: int) -> Optional[Dict[str, Any]]:
    con = get_conn()
    try:
        df = pd.read_sql("""
          SELECT goal_university, goal_department, goal_score, updated_at
          FROM parent_goal_v2
          WHERE parent_id=? AND student_id=? LIMIT 1
        """, con, params=(parent_id, student_id))
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    finally:
        con.close()

def goal_direction_plan(current_score: float, goal_score: float, weak_df: pd.DataFrame) -> str:
    gap = round(goal_score - current_score, 1)

    weak_text = ""
    if not weak_df.empty and "correct_rate" in weak_df.columns:
        top = weak_df.sort_values("correct_rate", ascending=True).head(3)
        weak_text = ", ".join([str(x) for x in top["concept"].tolist() if x])

    prompt = f"""
너는 학부모/학생을 돕는 루틴 코치다. 낙인/압박 금지. 실행 가능한 플랜만.
현재 종합 점수: {current_score}
목표 점수: {goal_score}
점수 격차: {gap}
취약 개념(가능하면): {weak_text if weak_text else "데이터 부족"}

요구:
1) 2주 루틴(하루 20분 기준) 제안
2) 점수 격차가 큰 경우에도 부모가 할 말 2문장(압박금지)
3) '지금부터 무엇을 보면 되는지' 체크리스트 5개
"""
    return try_ai_generate(prompt)

# =========================
# 화면 렌더링
# =========================

# ── 미로그인: 동기부여 화면 + 로그인 안내 ───────────────────
if not PARENT_ID:
    st.markdown("## 👨‍👩‍👧 학부모 공간")
    st.caption("좌측 사이드바에서 학부모 계정으로 입장하세요.")
    st.divider()

    _WELCOME_QUOTES = [
        "오늘의 작은 관심이 아이의 미래를 바꿉니다.",
        "아이는 비교가 아니라 성장으로 봐주세요.",
        "포기하지 않는 부모가 아이를 지킵니다.",
        "결과보다 과정을 함께해주세요.",
        "기다림도 교육입니다.",
        "부모의 안정이 아이의 안정입니다.",
        "꾸준함이 가장 큰 힘입니다.",
        "아이는 속도가 아니라 방향입니다.",
        "압박보다 신뢰가 효과적입니다.",
        "오늘도 함께 걸어가는 하루입니다.",
        "변화는 작은 루틴에서 시작됩니다.",
        "아이는 부모의 눈빛을 기억합니다.",
        "응원은 가장 강한 동기입니다.",
        "아이는 혼자가 아닙니다.",
        "부모도 충분히 잘하고 있습니다.",
        "지금의 노력이 미래를 만듭니다.",
        "아이의 가능성을 믿어주세요.",
        "성장은 시간이 필요합니다.",
        "오늘의 관심이 내일을 만듭니다.",
        "함께하는 시간이 가장 큰 자산입니다.",
        "부모의 여유가 아이의 자신감입니다.",
        "과정은 배신하지 않습니다.",
        "작은 변화가 큰 결과를 만듭니다.",
        "오늘도 충분히 의미 있는 하루입니다.",
        "함께 가는 길이 가장 안전합니다.",
        "포기하지 않는 것이 가장 큰 힘입니다.",
        "부모의 믿음이 아이의 힘입니다.",
        "오늘도 잘하고 있습니다.",
        "아이와 함께 성장하는 과정입니다.",
        "부모도 케어 받아야 합니다. 잠시 쉬어가도 괜찮습니다.",
    ]

    import random as _random
    _quote = _random.choice(_WELCOME_QUOTES)
    st.success(f"💬 **{_quote}**")

    st.markdown("""
    ---
    ### 이곳에서 할 수 있는 것들
    - 자녀의 오늘 학습 요약 확인
    - 과목별 정답률 분석
    - 심리 상태 관찰 지표
    - 목표 대학 설정 및 가능성 탐색
    - 부모를 위한 월 추천 도서
    - 일간·월간 리포트 생성

    **좌측 사이드바 → 학부모로 입장** 버튼을 눌러 시작하세요.
    """)
    st.stop()

# ── 로그인 완료: 타이틀 + 로그아웃 버튼 ─────────────────────
_parent_display = st.session_state.get("parent_short_name")
if _parent_display:
    col_title, col_logout = st.columns([5, 1])
    with col_title:
        st.markdown(f"## 👨‍👩‍👧 {_parent_display}")
    with col_logout:
        if st.button("로그아웃", key="main_parent_logout", use_container_width=True):
            st.session_state["parent_id"] = None
            st.session_state["parent_student_id"] = None
            st.session_state["parent_name_display"] = None
            st.session_state["parent_short_name"] = None
            st.rerun()
else:
    st.markdown("## 👨‍👩‍👧 학부모")
st.caption("학부모는 '통제'가 아니라 '동행'입니다. 비교/줄세우기 없이, 오늘 할 수 있는 루틴만 제공합니다.")

# =========================
# AI ON/OFF 토글 (메인 화면 최상단, 로그인 직후)
# =========================
if "use_openai" not in st.session_state:
    st.session_state["use_openai"] = False

ai_toggle = st.toggle("AI 사용", value=st.session_state["use_openai"], key="ai_toggle_parent")
st.session_state["use_openai"] = ai_toggle

if st.session_state["use_openai"]:
    st.success("AI ON (OpenAI 사용)")
else:
    st.warning("AI OFF (기본 텍스트 사용, 비용 없음)")

st.divider()

# (1) 민감 데이터 동의: 첫 화면 상단
st.markdown("### 1) 데이터 제공 동의 (필수)")
current_mode = get_consent(PARENT_ID, STUDENT_ID)
labels = [x[1] for x in CONSENT_OPTIONS]
values = [x[0] for x in CONSENT_OPTIONS]
idx = values.index(current_mode) if current_mode in values else 0

picked_label = st.radio(
    "학생의 학습/심리/순위 등 민감 데이터는 제공을 원치 않을 수 있습니다. 아래 중 하나를 선택해 주세요.",
    labels,
    index=idx
)
picked_value = values[labels.index(picked_label)]

colA, colB = st.columns([1, 1])
with colA:
    if st.button("저장", use_container_width=True):
        save_consent(PARENT_ID, STUDENT_ID, picked_value)
        st.success("저장 완료")
with colB:
    st.write("")

st.caption("※ 언제든지 변경 가능합니다. 데이터 삭제 요청은 설정 > 데이터 관리에서 가능합니다. (정책 시연용 문구)")

st.divider()

# (2) 오늘의 학습 + 조언 (동기부여 + AI 가이드)
st.markdown("### 2) 오늘의 학습과 조언")
if "motivation_msg" not in st.session_state:
    st.session_state["motivation_msg"] = random.choice(MOTIVATIONS)

st.info(st.session_state["motivation_msg"])
mcol1, mcol2 = st.columns([1, 1])
with mcol1:
    if st.button("새 문구", use_container_width=True):
        st.session_state["motivation_msg"] = random.choice(MOTIVATIONS)
        st.rerun()
with mcol2:
    if st.button("이 문구 저장", use_container_width=True):
        save_motivation_log(PARENT_ID, STUDENT_ID, st.session_state["motivation_msg"])
        st.success("저장 완료")

# (3) 오늘 요약(카드 4개: 모바일용 2x2)
today = get_today_summary(STUDENT_ID)
st.markdown("#### 3) 오늘의 학습 요약")
c1, c2 = st.columns(2)
c3, c4 = st.columns(2)

c1.metric("오늘 학습 기록 수", today["sessions"])
c2.metric("오늘 문항 수", today["questions"])

if today["correct_rate"] is None:
    c3.metric("오늘 정답률", "데이터 없음")
    c4.metric("오늘 과목 수", today["subjects"])
    st.caption("정답률 계산용 컬럼이 DB에 없거나 값이 없어 표시하지 못했습니다. (학생 DB는 건드리지 않음)")
else:
    c3.metric("오늘 정답률", f"{today['correct_rate']}%")
    c4.metric("오늘 과목 수", today["subjects"])
    st.caption(f"오늘 오답률: {today['wrong_rate']}%")

# (3-B) 전체 누적 요약 카드 (OpenAI ON/OFF 무관 - DB 직접 조회)
st.markdown("#### 전체 누적 학습 요약")
st.caption("아이가 지금까지 쌓은 기록입니다. AI 사용 여부와 무관하게 항상 표시됩니다.")
_con = get_conn()
try:
    _summary = fetch_session_summary(_con, STUDENT_ID)
finally:
    _con.close()

_s1, _s2, _s3, _s4, _s5 = st.columns(5)
_s1.metric("총 문제 수",   f"{_summary['total_questions']}개")
_s2.metric("총 정답 수",   f"{_summary['correct_count']}개")
_s3.metric("전체 정답률",  f"{_summary['accuracy']}%")
_s4.metric("누적 학습일",  f"{_summary['study_days']}일")
_s5.metric("현재 레벨",    _summary['level'])

if _summary['last_study_date']:
    st.caption(f"마지막 학습일: {str(_summary['last_study_date'])[:10]}")

st.divider()

# (4) 과목별 학습 분석
st.markdown("#### 4) 과목별 학습 분석")
SUBJECT_LIST = ["국어", "영어", "수학", "과학", "사회", "한자"]
subject_stats = get_subject_stats(STUDENT_ID)
stats_map = {row["subject"]: row for row in subject_stats}
display_rows = []
for subj in SUBJECT_LIST:
    if subj in stats_map:
        r = stats_map[subj]
        display_rows.append({
            "과목": subj,
            "총 문항 수": int(r.get("total_questions", 0)),
            "정답률(%)": round(float(r.get("correct_rate", 0)), 1)
        })
    else:
        display_rows.append({"과목": subj, "총 문항 수": 0, "정답률(%)": 0.0})

df_subj = pd.DataFrame(display_rows)
if df_subj["총 문항 수"].sum() == 0:
    st.info("아직 학습 데이터가 없습니다. 학생이 문제를 풀면 과목별 현황이 표시됩니다.")
else:
    import altair as alt
    bar = alt.Chart(df_subj).mark_bar().encode(
        x=alt.X("과목:N", sort=SUBJECT_LIST),
        y=alt.Y("정답률(%):Q", scale=alt.Scale(domain=[0, 100])),
        color=alt.condition(
            alt.datum["정답률(%)"] >= 70,
            alt.value("#4CAF50"),
            alt.value("#FF9800")
        ),
        tooltip=["과목", "총 문항 수", "정답률(%)"]
    ).properties(height=280)
    st.altair_chart(bar, use_container_width=True)
    st.dataframe(df_subj, use_container_width=True, hide_index=True)
    st.caption("70% 이상: 초록 / 70% 미만: 주황. 보강이 필요한 과목을 함께 살펴보세요.")

# (5) 오늘의 부모 행동 가이드(AI)
st.markdown("#### 5) 오늘의 부모 행동 가이드")
guide_key = today_key()
cached = get_ai_log(PARENT_ID, STUDENT_ID, "guide", guide_key)
if st.button("오늘 가이드 생성/갱신", use_container_width=True):
    prompt = f"""
너는 학부모를 돕는 교육 코치다. 통제/압박/낙인 금지. 동행/루틴/회복 관점.
[오늘 요약]
- 학습 기록 수: {today['sessions']}
- 문항 수: {today['questions']}
- 정답률: {today['correct_rate']}
- 과목 수: {today['subjects']}
[오늘 과목별 학습 현황] {", ".join([f"{r['과목']}({r['정답률(%)']}%)" for r in display_rows if r['총 문항 수'] > 0][:5]) if display_rows else "데이터 없음"}

요구:
1) 부모 행동 가이드 5개(각 1줄, 현실적)
2) '오늘은 무엇을 하면 충분한지' 최소 기준 1개
3) 압박 대신 지속을 만드는 문장 2개
"""
    content = try_ai_generate(prompt)
    upsert_ai_log(PARENT_ID, STUDENT_ID, "guide", guide_key, content)
    cached = content

if cached:
    st.write(cached)
else:
    st.caption("버튼을 눌러 오늘 가이드를 생성하세요.")

# (6) 오늘 자녀와 대화 방법(질문 제시)
st.markdown("#### 6) 오늘 자녀와의 대화 질문")
talk_cached = get_ai_log(PARENT_ID, STUDENT_ID, "talk", guide_key)
if st.button("대화 질문 생성", use_container_width=True):
    prompt = f"""
학부모가 아이에게 '공부 압박' 없이 대화하기 위한 질문을 만들어라.
오늘 문항수={today['questions']}, 정답률={today['correct_rate']}, 과목수={today['subjects']}
요구:
- 질문 6개 (칭찬형 2, 점검형 2, 회복형 2)
- 말투는 단단하고 짧게
"""
    content = try_ai_generate(prompt)
    upsert_ai_log(PARENT_ID, STUDENT_ID, "talk", guide_key, content)
    talk_cached = content
if talk_cached:
    st.write(talk_cached)

# (7) 학생+부모 함께 할 행동(실생활 예시)
st.markdown("#### 7) 학생과 부모가 함께 할 행동")
together_cached = get_ai_log(PARENT_ID, STUDENT_ID, "together", guide_key)
if st.button("함께 할 행동 제안 생성", use_container_width=True):
    prompt = f"""
오늘 학습을 기준으로 부모와 아이가 함께 할 수 있는 실생활 학습 행동을 제안해라.
요구:
- 5개 제안
- 각 제안마다 '실생활 문제 예시 1개' 포함
- 부담 없는 난이도, 10분~15분 단위
"""
    content = try_ai_generate(prompt)
    upsert_ai_log(PARENT_ID, STUDENT_ID, "together", guide_key, content)
    together_cached = content
if together_cached:
    st.write(together_cached)

# (8) 정서적 지원 텍스트
st.markdown("#### 8) 정서적 지원 팀 (지원 메시지)")
support_cached = get_ai_log(PARENT_ID, STUDENT_ID, "support", guide_key)
if st.button("정서 지원 메시지 생성", use_container_width=True):
    prompt = f"""
학부모가 아이의 정서적 부담을 낮추도록 돕는 메시지를 작성해라.
금지: 진단/낙인/비교/협박.
요구:
- 부모에게 주는 메시지 4문장
- 아이에게 해줄 수 있는 말 3문장
- '오늘은 여기까지만 해도 충분' 같은 마무리 1문장
"""
    content = try_ai_generate(prompt)
    upsert_ai_log(PARENT_ID, STUDENT_ID, "support", guide_key, content)
    support_cached = content
if support_cached:
    st.write(support_cached)

st.divider()

# (9) 학생 심리 상태(오늘 + 7일 + AI 분석 + 날짜 검색)
st.markdown("### 3) 학생 심리 상태")
st.caption("※ 이 영역은 진단이 아니라, 대화/휴식/루틴 점검을 돕기 위한 관찰 정보입니다.")

df_psy_today, df_psy_week = psych_today_and_week(STUDENT_ID)

if df_psy_today.empty and df_psy_week.empty:
    st.info("아직 심리 체크 기록이 없습니다. 학생이 심리 체크를 완료하면 여기에 표시됩니다.")
else:
    # ── 오늘 심리 점수 (항목별 바 차트, y축 0~5 고정) ────────────
    st.markdown("#### 오늘의 심리 점수")
    if df_psy_today.empty:
        st.info("오늘 심리 테스트 기록이 없습니다.")
    else:
        last = df_psy_today.sort_values("created_at").iloc[-1]
        items = [k for k in PSY_ITEMS if k in df_psy_today.columns]
        bar_df = pd.DataFrame({
            "항목": [PSY_LABEL_MAP.get(k, k) for k in items],
            "점수": [int(last.get(k, 0) or 0) for k in items],
        })

        import altair as alt
        bar_chart = (
            alt.Chart(bar_df)
            .mark_bar(color="#4C78A8")
            .encode(
                x=alt.X("항목:N", sort=None, axis=alt.Axis(labelAngle=-45)),
                y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 5]),
                        axis=alt.Axis(tickCount=5, title="점수 (1=낮음, 5=높음)")),
                tooltip=["항목", "점수"],
            )
            .properties(height=320)
        )
        st.altair_chart(bar_chart, use_container_width=True)
        st.caption("※ 1점(낮음) ~ 5점(높음) 기준. 항목별 점수는 학생 자가 응답입니다.")

    # ── 최근 7일 핵심 5개 항목 추이 (y축 0~5 고정) ───────────────
    st.markdown("#### 최근 7일 심리 추이 (핵심 5개 항목)")
    if not df_psy_week.empty:
        KEY_ITEMS = ["q3", "q4", "q7", "q9", "q20"]
        cols_avail = [c for c in KEY_ITEMS if c in df_psy_week.columns]
        if cols_avail:
            g = df_psy_week.groupby("day")[cols_avail].mean().reset_index()
            g = g.melt(id_vars="day", var_name="col", value_name="점수")
            g["항목"] = g["col"].map(PSY_LABEL_MAP)

            import altair as alt
            line_chart = (
                alt.Chart(g)
                .mark_line(point=True)
                .encode(
                    x=alt.X("day:T", title="날짜"),
                    y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 5]),
                            axis=alt.Axis(tickCount=5, title="점수 (1=낮음, 5=높음)")),
                    color=alt.Color("항목:N"),
                    tooltip=["day:T", "항목:N", "점수:Q"],
                )
                .properties(height=280)
            )
            st.altair_chart(line_chart, use_container_width=True)
            st.caption("공부 집중력 / 스트레스 관리 / 자신감 / 걱정·불안 / 행복감 — 5개 핵심 항목")

    # ── AI 심리 요약 ──────────────────────────────────────────────
    st.markdown("#### AI 기반 심리 요약·대화 가이드")
    psych_key = today_key()
    psycho_cached = get_ai_log(PARENT_ID, STUDENT_ID, "psych_ai", psych_key)
    if st.button("심리 AI 분석 생성", use_container_width=True):
        content = ai_analyze_psych(df_psy_today, df_psy_week)
        upsert_ai_log(PARENT_ID, STUDENT_ID, "psych_ai", psych_key, content)
        psycho_cached = content
    if psycho_cached:
        st.write(psycho_cached)

    # ── 날짜별 조회 ───────────────────────────────────────────────
    with st.expander("날짜별 상세 조회"):
        pick_date = st.date_input("날짜 선택", value=dt.date.today(), key="psych_date_pick")
        pick_key = pick_date.isoformat()
        con = get_conn()
        try:
            df_day = fetch_psych(con, STUDENT_ID, start_date=pick_key, end_date=pick_key)
        finally:
            con.close()
        if df_day.empty:
            st.info("선택한 날짜에 심리 기록이 없습니다.")
        else:
            last_day = df_day.sort_values("created_at").iloc[-1]
            items_day = [k for k in PSY_ITEMS if k in df_day.columns]
            day_df = pd.DataFrame({
                "항목": [PSY_LABEL_MAP.get(k, k) for k in items_day],
                "점수": [int(last_day.get(k, 0) or 0) for k in items_day],
            })
            import altair as alt
            day_chart = (
                alt.Chart(day_df)
                .mark_bar(color="#4C78A8")
                .encode(
                    x=alt.X("항목:N", sort=None, axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 5]),
                            axis=alt.Axis(tickCount=5, title="점수 (1=낮음, 5=높음)")),
                    tooltip=["항목", "점수"],
                )
                .properties(height=300)
            )
            st.altair_chart(day_chart, use_container_width=True)

st.divider()

# (10) 대학 추천(책임문구 + 현재점수 + 슬라이더/직접입력 + 필터 + 여러 대학 + 링크)
st.markdown("### 4) 대학 추천")
st.warning("본 기능은 공공데이터/API 또는 공식 데이터 업로드 기반으로 운영될 수 있으며, 실제 입시 결과를 보장하지 않습니다. 참고용입니다.")

current_score = compute_current_score(STUDENT_ID)
st.markdown(f"**현재 종합 점수(학습 데이터 기반)**: `{current_score}`")

st.markdown("#### 모의 점수 입력")
manual_score = st.number_input("모의 점수 직접 입력 (0~100)", min_value=0, max_value=100, value=int(round(current_score)), step=1)
score_input = float(manual_score)

st.markdown("#### 대학 검색 필터")
f1, f2, f3 = st.columns(3)
with f1:
    degree_filter = st.selectbox("대학유형", ["전체", "4년제", "2년제"], index=0)
with f2:
    region_filter = st.selectbox("선호지역", REGIONS, index=0)
with f3:
    track_filter = st.selectbox("선호 계열", TRACKS, index=0)

if st.button("추천 보기", use_container_width=True):
    df_reco = recommend_universities(score_input, degree_filter, region_filter, track_filter, limit=30)
    if df_reco.empty:
        st.info("조건에 맞는 추천 결과가 없습니다. (데이터셋은 시연용이며 확장 예정)")
    else:
        st.markdown("#### 3-5) 결과 표시")
        st.dataframe(df_reco, use_container_width=True, hide_index=True)

        # 링크: 모바일에서 버튼으로 열기
        st.markdown("#### 대학 홈페이지 바로가기")
        for _, r in df_reco.iterrows():
            st.link_button(f"{r['대학명']} - {r['학과']} ({r['유형']}, {r['지역']})", r["링크"], use_container_width=True)

        save_university_results(PARENT_ID, STUDENT_ID, score_input, df_reco)
        st.success("추천 결과를 저장했습니다. (시연용 로그)")

st.divider()

# (11) 목표대학 설정 + 방향 플랜(너가 말한 “목표대학 -> 가는 방향” 기능)
st.markdown("### 5) 목표 대학 설정 + 방향")
goal = get_goal(PARENT_ID, STUDENT_ID)

g1, g2 = st.columns(2)
with g1:
    goal_u = st.text_input("목표 대학", value=(goal["goal_university"] if goal else ""))
with g2:
    goal_d = st.text_input("목표 학과(선택)", value=(goal["goal_department"] if goal else ""))

goal_score = st.number_input("목표 점수(100점 만점)", min_value=0.0, max_value=100.0, value=float(goal["goal_score"]) if goal else 80.0, step=0.5)

if st.button("목표 저장", use_container_width=True):
    if not goal_u.strip():
        st.error("목표 대학을 입력하세요.")
    else:
        save_goal(PARENT_ID, STUDENT_ID, goal_u.strip(), goal_d.strip(), float(goal_score))
        st.success("목표 저장 완료")

goal = get_goal(PARENT_ID, STUDENT_ID)
if goal:
    gap = round(float(goal["goal_score"]) - current_score, 1)
    st.info(f"목표까지 필요한 점수 격차: **{gap}점**")

    st.markdown("#### 목표 달성을 위한 방향(루틴/우선순위)")
    plan_key = f"goal_plan:{today_key()}"
    cached_plan = get_ai_log(PARENT_ID, STUDENT_ID, "goal_plan", plan_key)

    if st.button("방향 플랜 생성", use_container_width=True):
        plan = goal_direction_plan(current_score, float(goal["goal_score"]), pd.DataFrame())
        upsert_ai_log(PARENT_ID, STUDENT_ID, "goal_plan", plan_key, plan)
        cached_plan = plan

    if cached_plan:
        st.write(cached_plan)

st.divider()

# (12) 리포트(일간/월간)
st.markdown("### 6) 리포트")
tab_daily, tab_monthly = st.tabs(["일간 리포트", "월간 리포트"])

with tab_daily:
    st.caption("오늘 하루 기준으로 요약합니다.")
    daily_key = today_key()
    daily_cached = get_ai_log(PARENT_ID, STUDENT_ID, "daily_report", daily_key)

    if st.button("일간 리포트 생성/갱신", use_container_width=True):
        # 과목별 학습 현황 요약
        weak_text = ", ".join([f"{r['과목']}({r['정답률(%)']}%)" for r in display_rows if r['총 문항 수'] > 0][:5]) if display_rows else "데이터 없음"

        prompt = f"""
학부모에게 제공할 '일간 리포트'를 작성하라. 낙인/비교/압박 금지.
구성:
- 오늘 성과(짧게)
- 취약 개념(가능하면)
- 내일 목표(현실적)
- 부모님께 제안하는 말(단단하게 2문장)
데이터:
문항={today['questions']}, 정답률={today['correct_rate']}, 과목수={today['subjects']}
취약개념={weak_text if weak_text else "데이터 없음"}
"""
        content = try_ai_generate(prompt)
        upsert_ai_log(PARENT_ID, STUDENT_ID, "daily_report", daily_key, content)
        daily_cached = content

    if daily_cached:
        st.write(daily_cached)

with tab_monthly:
    st.caption("최근 30일(데이터가 하루 이상이면 월간으로 정의) 기준 요약.")
    ym = year_month_now()
    monthly_cached = get_ai_log(PARENT_ID, STUDENT_ID, "monthly_report", ym)

    if st.button("월간 리포트 생성/갱신", use_container_width=True):
        # 최근 30일 데이터
        start = (dt.date.today() - dt.timedelta(days=29)).isoformat()
        end = dt.date.today().isoformat()
        con = get_conn()
        try:
            df30 = fetch_sessions(con, STUDENT_ID, start_date=start, end_date=end)
        finally:
            con.close()

        q = len(df30) if not df30.empty else 0
        subj = int(df30["subject"].nunique()) if (not df30.empty and "subject" in df30.columns) else 0
        if df30.empty or df30["is_correct"].dropna().empty:
            cr = None
        else:
            cr = round(df30["is_correct"].dropna().mean()*100, 1)

        prompt = f"""
학부모에게 제공할 '월간 리포트'를 작성하라. 낙인/비교/압박 금지.
구성:
- 이달의 성과
- 취약 개념(가능하면)
- 다음달 목표(현실적)
- 부모님께 제안하는 말(단단하게 3문장)
데이터:
30일 문항={q}, 정답률={cr}, 과목수={subj}
"""
        content = try_ai_generate(prompt)
        upsert_ai_log(PARENT_ID, STUDENT_ID, "monthly_report", ym, content)
        monthly_cached = content

    if monthly_cached:
        st.write(monthly_cached)

st.divider()

# (13) 월 도서 추천(5권)
st.markdown("### 7) 학부모 이달의 도서 추천 (5권)")
ym = year_month_now()
books = set_monthly_books(PARENT_ID, STUDENT_ID, ym, force_refresh=False)

if books.empty:
    st.info("이번 달 추천 도서가 없습니다.")
else:
    for _, r in books.iterrows():
        st.write(f"{int(r['idx'])}. **{r['title']}** — {r['author']}")

if st.button("이번 달 도서 새로 추천(고정)", use_container_width=True):
    books = set_monthly_books(PARENT_ID, STUDENT_ID, ym, force_refresh=True)
    st.success("새 추천으로 갱신했습니다.")
    st.rerun()

st.caption("※ '우쭈쭈'가 아니라, 부모가 지치지 않도록 루틴을 보조하는 도서 중심으로 구성합니다.")

st.divider()

# (14) 주간 리포트
st.markdown("### 8) 이번 주 학습 주간 리포트")
st.caption("최근 7일간 학습 데이터를 요약합니다.")

week_start = (dt.date.today() - dt.timedelta(days=6)).isoformat()
week_end = dt.date.today().isoformat()

con_w = get_conn()
try:
    week_sessions = con_w.execute(
        "SELECT * FROM study_sessions WHERE student_id=? AND substr(created_at,1,10) BETWEEN ? AND ? ORDER BY created_at DESC",
        (STUDENT_ID, week_start, week_end)
    ).fetchall()
    week_sessions = [dict(r) for r in week_sessions]
finally:
    con_w.close()

if not week_sessions:
    st.info(f"이번 주({week_start} ~ {week_end}) 학습 기록이 없습니다.")
else:
    wq_total = sum(s.get("total_questions", 0) for s in week_sessions)
    wq_correct = sum(s.get("correct_count", 0) for s in week_sessions)
    w_days = len(set(s["created_at"][:10] for s in week_sessions))
    w_rate = round(wq_correct / wq_total * 100, 1) if wq_total > 0 else 0

    wc1, wc2, wc3, wc4 = st.columns(4)
    wc1.metric("이번 주 학습일", f"{w_days}일")
    wc2.metric("총 문항", f"{wq_total}개")
    wc3.metric("맞힌 문항", f"{wq_correct}개")
    wc4.metric("정답률", f"{w_rate}%")

    subj_week = {}
    for s in week_sessions:
        subj = s.get("subject", "기타")
        subj_week[subj] = subj_week.get(subj, 0) + s.get("total_questions", 0)
    if subj_week:
        st.markdown("**이번 주 과목별 문항 수**")
        df_week_subj = pd.DataFrame([{"과목": k, "문항 수": v} for k, v in subj_week.items()])
        st.bar_chart(df_week_subj.set_index("과목"))

    if w_days >= 5:
        st.success("🏆 이번 주 5일 이상 학습! 정말 꾸준하게 잘하고 있습니다.")
    elif w_days >= 3:
        st.info("✨ 이번 주 3일 이상 학습했습니다. 루틴이 만들어지고 있어요!")
    else:
        st.warning("📅 이번 주 학습 횟수가 적습니다. 짧게라도 매일 이어가보세요.")

    st.markdown("**이번 주 학습 세션 목록**")
    df_week = pd.DataFrame([{
        "날짜": s["created_at"][:10],
        "과목": s.get("subject", "-"),
        "학년": s.get("grade", "-"),
        "문항": s.get("total_questions", 0),
        "정답": s.get("correct_count", 0),
    } for s in week_sessions])
    st.dataframe(df_week, use_container_width=True, hide_index=True)