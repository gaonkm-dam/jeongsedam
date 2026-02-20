import streamlit as st
import sys
import os

# 프로젝트 루트를 path에 추가 (database, openai_helper, config import용)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import database as db
import openai_helper as ai
import config
from datetime import datetime, timedelta
import sqlite3 as _sqlite3

# ── 페이지 설정은 app.py(entry point)에서만 하므로 여기선 생략 ──

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.student = None
    st.session_state.current_page = 'login'
    st.session_state.current_session_id = None
    st.session_state.questions = []
    st.session_state.user_answers = {}
    st.session_state.submitted = False

if 'student_use_openai' not in st.session_state:
    st.session_state.student_use_openai = config.USE_OPENAI

db.init_database()
ai_initialized = ai.init_openai()

# ── 태블릿/모바일 최적화 CSS ────────────────────────────────────
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
.stNumberInput > div > div > input { min-height: 44px !important; font-size: 1rem !important; }
[data-testid="metric-container"] {
    background: #f8f9fa; border-radius: 12px; padding: 12px !important; margin-bottom: 8px;
}
.streamlit-expanderHeader { font-size: 1rem !important; min-height: 44px; }
.stTabs [data-baseweb="tab"] { min-height: 44px !important; font-size: 0.95rem !important; }
.dataframe { font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)


# ── OpenAI 상태 표시 헬퍼 ──────────────────────────────────────
def show_ai_status():
    if st.session_state.student_use_openai:
        st.success("AI ON (OpenAI 사용 중)")
    else:
        st.warning("AI OFF (Mock 데이터 사용, 비용 없음)")


# ── 로그인 ────────────────────────────────────────────────────
def _do_login(login_id: str, password: str):
    student = db.get_student_by_login(login_id, password)
    if student:
        st.session_state.logged_in = True
        st.session_state.student = student
        st.session_state.current_page = 'dashboard'
        st.rerun()


def show_login():
    st.title("🎓 정세담 학습 시스템")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # ── 데모 자동 로그인 (학부모 페이지와 동일 방식) ──
        st.markdown("### 학생 데모 로그인")
        st.caption("버튼 클릭 한 번으로 바로 입장합니다.")

        DEMO_ACCOUNTS = [
            ("김민준 (학생1)", "student1", "pass1"),
            ("이서연 (학생2)", "student2", "pass2"),
            ("박지호 (학생3)", "student3", "pass3"),
        ]

        for label, lid, pw in DEMO_ACCOUNTS:
            if st.button(f"🎓 {label}로 입장", use_container_width=True, key=f"demo_{lid}"):
                _do_login(lid, pw)

        st.divider()

        # ── 직접 로그인 (접기 가능) ──
        with st.expander("직접 아이디/비밀번호 로그인"):
            login_id = st.text_input("아이디", key="manual_id")
            password = st.text_input("비밀번호", type="password", key="manual_pw")
            if st.button("로그인", use_container_width=True, key="manual_login"):
                student = db.get_student_by_login(login_id, password)
                if student:
                    _do_login(login_id, password)
                else:
                    st.error("아이디 또는 비밀번호가 잘못되었습니다.")


# ── 대시보드 ──────────────────────────────────────────────────
def _get_streak(student_id):
    """연속 학습일 계산"""
    con = _sqlite3.connect(os.path.join(_root, "student_system.db"))
    rows = con.execute(
        "SELECT DISTINCT substr(created_at,1,10) as d FROM study_sessions WHERE student_id=? ORDER BY d DESC",
        (student_id,)
    ).fetchall()
    con.close()
    if not rows:
        return 0
    dates = [datetime.strptime(r[0], "%Y-%m-%d").date() for r in rows]
    streak = 1
    for i in range(1, len(dates)):
        if (dates[i-1] - dates[i]).days == 1:
            streak += 1
        else:
            break
    today = datetime.now().date()
    if dates[0] < today - timedelta(days=1):
        return 0
    return streak

def _ensure_goal_table():
    con = _sqlite3.connect(os.path.join(_root, "student_system.db"))
    con.execute("""CREATE TABLE IF NOT EXISTS student_study_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        target_count INTEGER NOT NULL,
        week_start TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, subject, week_start)
    )""")
    con.commit()
    con.close()

_ensure_goal_table()

def _get_goals(student_id, week_start):
    con = _sqlite3.connect(os.path.join(_root, "student_system.db"))
    rows = con.execute(
        "SELECT subject, target_count FROM student_study_goals WHERE student_id=? AND week_start=?",
        (student_id, week_start)
    ).fetchall()
    con.close()
    return {r[0]: r[1] for r in rows}

def _save_goal(student_id, subject, target, week_start):
    con = _sqlite3.connect(os.path.join(_root, "student_system.db"))
    con.execute(
        "INSERT OR REPLACE INTO student_study_goals(student_id, subject, target_count, week_start) VALUES(?,?,?,?)",
        (student_id, subject, target, week_start)
    )
    con.commit()
    con.close()

def _get_week_progress(student_id, week_start, week_end):
    con = _sqlite3.connect(os.path.join(_root, "student_system.db"))
    rows = con.execute(
        """SELECT ss.subject, COUNT(q.id) as cnt
           FROM study_sessions ss JOIN questions q ON q.session_id=ss.id
           WHERE ss.student_id=? AND substr(ss.created_at,1,10) BETWEEN ? AND ?
           GROUP BY ss.subject""",
        (student_id, week_start, week_end)
    ).fetchall()
    con.close()
    return {r[0]: r[1] for r in rows}

def _get_wrong_notes(student_id):
    con = _sqlite3.connect(os.path.join(_root, "student_system.db"))
    rows = con.execute(
        """SELECT q.id, q.question_number, q.question_text, q.answer, q.explanation,
                  ss.subject, ss.grade, substr(ss.created_at,1,10) as study_date
           FROM questions q JOIN study_sessions ss ON ss.id=q.session_id
           WHERE ss.student_id=? AND q.is_correct=0
           ORDER BY ss.created_at DESC""",
        (student_id,)
    ).fetchall()
    con.close()
    return [dict(zip(["id","question_number","question_text","answer","explanation","subject","grade","study_date"], r)) for r in rows]

def show_wrong_notes():
    student = st.session_state.student
    show_ai_status()
    st.title("📝 오답 노트")
    st.caption("틀린 문제를 과목별로 정리합니다. 반복 학습으로 실력을 키워보세요!")
    if st.button("← 대시보드로 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()
    st.divider()
    wrongs = _get_wrong_notes(student['id'])
    if not wrongs:
        st.success("🎉 오답 노트가 비어있습니다! 모든 문제를 맞혔어요.")
        return
    st.info(f"총 **{len(wrongs)}개**의 오답이 있습니다. 하나씩 정복해봐요! 💪")
    SUBJECTS = ["국어","영어","수학","과학","사회","역사","한자"]
    by_subject = {}
    for w in wrongs:
        s = w["subject"]
        by_subject.setdefault(s, []).append(w)
    tabs_labels = [f"{s} ({len(by_subject[s])}개)" for s in SUBJECTS if s in by_subject]
    other = [w for w in wrongs if w["subject"] not in SUBJECTS]
    if other:
        tabs_labels.append(f"기타 ({len(other)}개)")
    if not tabs_labels:
        st.warning("오답 데이터가 없습니다.")
        return
    tabs = st.tabs(tabs_labels)
    subj_list = [s for s in SUBJECTS if s in by_subject] + (["기타"] if other else [])
    for tab, subj in zip(tabs, subj_list):
        with tab:
            items = by_subject.get(subj, other if subj=="기타" else [])
            for idx, w in enumerate(items):
                with st.expander(f"❌ [{w['study_date']}] 문제 {w['question_number']} | {w['subject']} {w['grade']}"):
                    st.markdown(f"**문제:** {w['question_text'] or '(내용 없음)'}")
                    st.success(f"**정답:** {w['answer']}")
                    if w['explanation']:
                        st.info(f"**해설:** {w['explanation']}")
                    if st.button("🔄 이 문제 다시 풀기", key=f"retry_{w['id']}_{idx}"):
                        st.session_state['retry_question'] = w
                        st.info("다시 풀기 기능: 새 학습 시작에서 같은 과목을 선택하세요.")

def show_study_goals():
    student = st.session_state.student
    show_ai_status()
    st.title("🎯 학습 목표 설정")
    st.caption("이번 주 학습 목표를 설정하고 달성도를 확인하세요!")
    if st.button("← 대시보드로 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()
    st.divider()
    today = datetime.now().date()
    week_start = str(today - timedelta(days=today.weekday()))
    week_end = str(today - timedelta(days=today.weekday()) + timedelta(days=6))
    st.caption(f"현재 주: {week_start} ~ {week_end}")
    SUBJECTS = ["국어","영어","수학","과학","사회","역사","한자"]
    goals = _get_goals(student['id'], week_start)
    progress = _get_week_progress(student['id'], week_start, week_end)
    st.markdown("#### 목표 설정")
    with st.form("goal_form"):
        new_goals = {}
        cols = st.columns(4)
        for i, subj in enumerate(SUBJECTS):
            with cols[i % 4]:
                new_goals[subj] = st.number_input(
                    f"{subj} (문항)", min_value=0, max_value=200,
                    value=goals.get(subj, 10), step=5, key=f"goal_{subj}"
                )
        if st.form_submit_button("💾 목표 저장", use_container_width=True):
            for subj, cnt in new_goals.items():
                if cnt > 0:
                    _save_goal(student['id'], subj, cnt, week_start)
            st.success("목표가 저장되었습니다!")
            st.rerun()
    st.divider()
    st.markdown("#### 이번 주 달성 현황")
    active_goals = {s: v for s, v in goals.items() if v > 0}
    if not active_goals:
        st.info("목표를 설정해주세요!")
        return
    total_target = sum(active_goals.values())
    total_done = sum(progress.get(s, 0) for s in active_goals)
    overall_pct = min(int(total_done / total_target * 100), 100) if total_target > 0 else 0
    if overall_pct >= 100:
        st.balloons()
        st.success(f"🏆 이번 주 전체 목표 달성! ({total_done}/{total_target}문항)")
    else:
        st.progress(overall_pct / 100, text=f"전체 달성도: {overall_pct}% ({total_done}/{total_target}문항)")
    st.markdown("---")
    for subj, target in active_goals.items():
        done = progress.get(subj, 0)
        pct = min(int(done / target * 100), 100) if target > 0 else 0
        col1, col2 = st.columns([3, 1])
        with col1:
            bar_color = "🟢" if pct >= 100 else "🟡" if pct >= 50 else "🔴"
            st.markdown(f"{bar_color} **{subj}** — {done}/{target}문항")
            st.progress(pct / 100)
        with col2:
            st.metric("달성률", f"{pct}%")

def show_dashboard():
    student = st.session_state.student
    stats = db.get_student_stats(student['id'])

    show_ai_status()

    # 스트릭 계산
    streak = _get_streak(student['id'])

    st.title(f"👋 {student['name']}님 환영합니다!")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("총 문제 수", f"{stats['total_questions']}개")
    with col2:
        st.metric("정답률", f"{stats['accuracy']}%")
    with col3:
        last_date = stats['last_study_date']
        date_str = last_date.split()[0] if last_date else "없음"
        st.metric("최근 학습일", date_str)
    with col4:
        st.metric("현재 레벨", f"Level {stats['level']}")
    with col5:
        rankings = db.get_rankings()
        my_rank = next((i+1 for i, r in enumerate(rankings) if r['id'] == student['id']), 0)
        st.metric("순위", f"{my_rank}위")

    # 스트릭 배너
    if streak >= 7:
        st.success(f"🔥🔥🔥 **{streak}일 연속 학습 중!** 대단해요! 이 기세로 계속 가봐요!")
    elif streak >= 3:
        st.info(f"🔥 **{streak}일 연속 학습 중!** 꾸준함이 실력입니다!")
    elif streak >= 1:
        st.info(f"✨ 오늘도 학습했어요! 내일도 이어가면 스트릭이 쌓입니다.")
    else:
        st.warning("📅 오늘 학습을 시작해서 연속 학습 스트릭을 만들어보세요!")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📚 학습 메뉴")

        if st.button("🆕 새로운 학습 시작", use_container_width=True):
            st.session_state.current_page = 'new_study'
            st.rerun()
        if st.button("🧠 심리 체크", use_container_width=True):
            st.session_state.current_page = 'psychology'
            st.rerun()
        if st.button("📖 단어장", use_container_width=True):
            st.session_state.current_page = 'vocabulary'
            st.rerun()
        if st.button("📊 학습 이력", use_container_width=True):
            st.session_state.current_page = 'history'
            st.rerun()
        if st.button("🏆 순위 보기", use_container_width=True):
            st.session_state.current_page = 'ranking'
            st.rerun()
        if st.button("📝 오답 노트", use_container_width=True):
            st.session_state.current_page = 'wrong_notes'
            st.rerun()
        if st.button("🎯 학습 목표", use_container_width=True):
            st.session_state.current_page = 'goals'
            st.rerun()

    with col_b:
        st.subheader("🎯 개인 정보")

        if st.button("🎓 목표 대학 설정", use_container_width=True):
            st.session_state.current_page = 'target_university'
            st.rerun()
        if st.button("📚 이달의 추천 도서", use_container_width=True):
            st.session_state.current_page = 'books'
            st.rerun()

        if student['target_university']:
            st.info(f"**목표 대학**\n{student['target_university']} - {student['target_department']}")
        else:
            st.warning("목표 대학을 설정해주세요!")


# ── 새로운 학습 ───────────────────────────────────────────────
def show_new_study():
    st.title("🆕 새로운 학습 시작")

    show_ai_status()

    if not st.session_state.student_use_openai:
        st.info("AI OFF 상태: Mock 문제가 생성됩니다.")

    with st.form("study_form"):
        col1, col2 = st.columns(2)

        with col1:
            subject = st.selectbox("과목", ['국어', '영어', '수학', '과학', '사회', '역사', '한자'])
            grade = st.selectbox("학년", ['초1', '초2', '초3', '초4', '초5', '초6',
                                         '중1', '중2', '중3', '고1', '고2', '고3'])
            difficulty = st.selectbox("난이도", ['쉬움', '보통', '어려움'])

        with col2:
            exam_type = st.selectbox("시험 유형", ['중간', '기말', '모의', '수능'])
            page_start = st.number_input("시작 페이지", min_value=1, value=1)
            page_end = st.number_input("끝 페이지", min_value=1, value=10)
            num_questions = st.number_input("문제 수", min_value=1, max_value=30, value=10)

        submitted = st.form_submit_button("학습 시작하기", use_container_width=True)

        if submitted:
            if page_end < page_start:
                st.error("끝 페이지는 시작 페이지보다 커야 합니다.")
            else:
                motivation = ai.generate_motivation_message("시작")
                st.success(f"💬 {motivation}")

                with st.spinner("문제를 생성하고 있습니다..."):
                    raw_questions = ai.generate_questions(
                        subject, grade, page_start, page_end,
                        difficulty, exam_type, num_questions
                    )

                    if raw_questions and len(raw_questions) > 0:
                        # question_text 키 통일
                        questions = []
                        for i, q in enumerate(raw_questions, 1):
                            questions.append({
                                "question_number": i,
                                "question_text": q.get("question_text") or q.get("question", f"문제 {i}"),
                                "answer": q.get("answer", ""),
                                "explanation": q.get("explanation", ""),
                            })

                        session_id = db.create_study_session(
                            st.session_state.student['id'],
                            subject, grade, page_start, page_end,
                            difficulty, exam_type, len(questions)
                        )

                        db.save_questions(session_id, questions)

                        st.session_state.current_session_id = session_id
                        st.session_state.questions = db.get_session_questions(session_id)
                        st.session_state.user_answers = {}
                        st.session_state.submitted = False
                        # 이전 검색 결과 초기화
                        for key in list(st.session_state.keys()):
                            if key.startswith("search_result_"):
                                del st.session_state[key]
                        st.session_state.current_page = 'solve'
                        st.rerun()
                    else:
                        st.error("문제 생성에 실패했습니다. 다시 시도해주세요.")

    if st.button("← 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()


# ── 문제 풀기 ─────────────────────────────────────────────────
def show_solve_questions():
    st.title("📝 문제 풀기")

    if not st.session_state.questions:
        st.warning("문제가 없습니다.")
        if st.button("← 돌아가기"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
        return

    session_info = db.get_connection().execute(
        'SELECT * FROM study_sessions WHERE id = ?',
        (st.session_state.current_session_id,)
    ).fetchone()

    st.info(f"**과목**: {session_info['subject']} | **학년**: {session_info['grade']} | **난이도**: {session_info['difficulty']} | **문제 수**: {len(st.session_state.questions)}개")
    st.divider()

    for q in st.session_state.questions:
        st.subheader(f"문제 {q['question_number']}")

        col1, col2 = st.columns([4, 1])

        with col1:
            question_content = q.get('question_text', '')
            if question_content:
                st.markdown(f"**{question_content}**")
            else:
                st.error("문제 내용을 불러올 수 없습니다.")

            answer_key = f"answer_{q['question_number']}"
            qnum = q['question_number']

            # 객관식 감지: 문제 텍스트에 "a." "b." "c." "d." 또는 "① ② ③ ④" 패턴
            import re as _re
            mc_pattern = _re.search(r'\ba[\.\)]\s|\bb[\.\)]\s|\bc[\.\)]\s|\bd[\.\)]\s|①|②|③|④', question_content, _re.IGNORECASE)

            if mc_pattern:
                # 객관식: 버튼으로 선택
                st.caption("보기를 터치하여 선택하세요")
                # 보기 파싱
                options = []
                for m in _re.finditer(r'([a-dA-D①②③④][\.\)]\s?)([^a-dA-D①②③④\n]+)', question_content):
                    label = m.group(1).strip().rstrip('.')
                    text = m.group(2).strip()
                    options.append((label, text))

                if not options:
                    # 파싱 실패 시 기본 4개
                    options = [("a", ""), ("b", ""), ("c", ""), ("d", "")]

                current_ans = st.session_state.user_answers.get(qnum, '')
                btn_cols = st.columns(len(options))
                for idx_b, (lbl, txt) in enumerate(options):
                    btn_label = f"{lbl}. {txt}" if txt else lbl
                    is_selected = current_ans.lower() == lbl.lower()
                    btn_type = "primary" if is_selected else "secondary"
                    with btn_cols[idx_b]:
                        if st.button(btn_label, key=f"mc_{qnum}_{lbl}", type=btn_type, use_container_width=True):
                            st.session_state.user_answers[qnum] = lbl
                            st.rerun()
                if current_ans:
                    st.caption(f"선택: **{current_ans}**")
            else:
                # 주관식/서술형: 기존 텍스트 입력
                user_answer = st.text_input(
                    "답변",
                    key=answer_key,
                    value=st.session_state.user_answers.get(qnum, ''),
                    placeholder="답을 입력하세요"
                )
                st.session_state.user_answers[qnum] = user_answer

        with col2:
            st.write("**🔍 검색**")
            search_term = st.text_input("검색어", key=f"search_{q['question_number']}", label_visibility="collapsed")

            if st.button("검색", key=f"btn_search_{q['question_number']}"):
                if search_term:
                    with st.spinner("검색 중..."):
                        result = ai.search_content(session_info['subject'], search_term)
                        st.session_state[f"search_result_{q['question_number']}"] = result
                        st.session_state[f"search_term_{q['question_number']}"] = search_term
                        st.rerun()

            if f"search_result_{q['question_number']}" in st.session_state:
                result = st.session_state[f"search_result_{q['question_number']}"]
                saved_search_term = st.session_state.get(f"search_term_{q['question_number']}", '')
                st.info(result)

                if st.button("💾 단어장 저장", key=f"save_{q['question_number']}"):
                    if saved_search_term:
                        db.save_search_history(
                            st.session_state.student['id'],
                            session_info['subject'],
                            saved_search_term,
                            result
                        )
                        st.success("저장됨!")

        st.divider()

    col_submit, col_back = st.columns([1, 1])

    with col_submit:
        if st.button("✅ 제출하기", use_container_width=True):
            correct_count = db.submit_answers(
                st.session_state.current_session_id,
                st.session_state.user_answers
            )
            st.session_state.submitted = True
            st.session_state.correct_count = correct_count
            st.session_state.current_page = 'result'
            st.rerun()

    with col_back:
        if st.button("← 돌아가기", use_container_width=True):
            st.session_state.current_page = 'dashboard'
            st.session_state.current_session_id = None
            st.session_state.questions = []
            st.rerun()


# ── 결과 ─────────────────────────────────────────────────────
def show_result():
    st.title("✅ 제출 결과")

    if not st.session_state.current_session_id:
        st.warning("결과가 없습니다.")
        if st.button("← 돌아가기"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
        return

    questions = db.get_session_questions(st.session_state.current_session_id)
    total = len(questions)
    correct = st.session_state.correct_count
    score = round((correct / total) * 100, 1) if total > 0 else 0

    motivation = ai.generate_motivation_message("완료")
    st.success(f"💬 {motivation}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 문제 수", f"{total}개")
    with col2:
        st.metric("정답 수", f"{correct}개")
    with col3:
        st.metric("점수", f"{score}점")

    st.divider()

    for q in questions:
        if q['is_correct']:
            st.success(f"✅ 문제 {q['question_number']}: 정답")
        else:
            st.error(f"❌ 문제 {q['question_number']}: 오답")

        with st.expander(f"문제 {q['question_number']} 상세보기"):
            st.write("**문제:**")
            question_content = q.get('question_text', '')
            if question_content:
                st.markdown(question_content)
            else:
                st.error("문제 내용을 불러올 수 없습니다.")
            st.write(f"**정답:** {q['answer']}")
            st.write(f"**해설:** {q['explanation']}")

    if st.button("← 대시보드로 돌아가기", use_container_width=True):
        st.session_state.current_page = 'dashboard'
        st.session_state.current_session_id = None
        st.session_state.questions = []
        st.session_state.submitted = False
        st.rerun()


# ── 심리 체크 ─────────────────────────────────────────────────
def show_psychology():
    st.title("🧠 심리 체크")
    st.info("총 20문항입니다. 각 문항에 대해 1~5점으로 평가해주세요. (결과는 학부모/교사만 확인 가능)")

    questions = [
        "학교 생활이 즐겁다", "친구들과 잘 어울린다", "공부에 집중할 수 있다",
        "스트레스를 잘 관리한다", "긍정적인 생각을 한다", "부모님과 대화가 원활하다",
        "자신감이 있다", "미래에 대한 계획이 있다", "걱정이나 불안이 적다",
        "감정 조절을 잘 한다", "충분한 수면을 취한다", "규칙적인 생활을 한다",
        "취미나 여가 활동을 즐긴다", "목표를 향해 노력한다", "실패를 두려워하지 않는다",
        "다른 사람을 배려한다", "새로운 도전을 즐긴다", "문제 해결 능력이 있다",
        "책임감이 있다", "행복하다고 느낀다"
    ]

    with st.form("psych_form"):
        answers = {}
        for i, q in enumerate(questions, 1):
            st.write(f"**{i}. {q}**")
            answers[f'q{i}'] = st.radio(
                f"질문 {i}", options=[1, 2, 3, 4, 5],
                format_func=lambda x: f"{x}점",
                horizontal=True, key=f"psych_q{i}",
                label_visibility="collapsed"
            )
            st.divider()

        submitted = st.form_submit_button("제출하기", use_container_width=True)

        if submitted:
            db.save_psychological_test(st.session_state.student['id'], answers)
            st.success("✅ 심리 체크가 완료되었습니다. 결과는 학부모/교사가 확인할 수 있습니다.")

    if st.button("← 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()


# ── 단어장 ────────────────────────────────────────────────────
def show_vocabulary():
    st.title("📖 단어장")

    student_id = st.session_state.student['id']
    subjects = ['전체', '국어', '영어', '수학', '과학', '사회', '역사', '한자']
    selected_subject = st.selectbox("과목 선택", subjects)

    if selected_subject == '전체':
        history = db.get_search_history(student_id)
    else:
        history = db.get_search_history(student_id, selected_subject)

    if not history:
        st.info("저장된 단어가 없습니다.")
    else:
        for item in history:
            with st.expander(f"[{item['subject']}] {item['search_term']} - {item['created_at'][:10]}"):
                st.write(item['result_text'])

    if st.button("← 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()


# ── 학습 이력 ─────────────────────────────────────────────────
def show_history():
    st.title("📊 학습 이력")

    student_id = st.session_state.student['id']
    history = db.get_study_history(student_id)

    if not history:
        st.info("학습 이력이 없습니다.")
    else:
        for session in history:
            accuracy = round((session['correct_count'] / session['total_questions'] * 100), 1) if session['total_questions'] > 0 else 0

            col1, col2 = st.columns([3, 1])

            with col1:
                st.subheader(f"{session['subject']} - {session['grade']}")
                st.write(f"**날짜:** {session['created_at'][:10]}")
                st.write(f"**난이도:** {session['difficulty']} | **시험 유형:** {session['exam_type']}")
                st.write(f"**정답률:** {accuracy}% ({session['correct_count']}/{session['total_questions']})")

            with col2:
                if st.button("문제 보기", key=f"view_{session['id']}"):
                    st.session_state.view_session_id = session['id']
                    st.rerun()

            st.divider()

        if 'view_session_id' in st.session_state:
            st.subheader("문제 상세")
            questions = db.get_session_questions(st.session_state.view_session_id)

            for q in questions:
                status = "✅ 정답" if q['is_correct'] else "❌ 오답"
                st.write(f"**문제 {q['question_number']}** {status}")
                question_content = q.get('question_text', '')
                if question_content:
                    st.markdown(question_content)
                else:
                    st.error("문제 내용을 불러올 수 없습니다.")
                st.write(f"**정답:** {q['answer']}")
                st.write(f"**해설:** {q['explanation']}")
                st.divider()

            if st.button("닫기"):
                del st.session_state.view_session_id
                st.rerun()

    if st.button("← 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()


# ── 순위 ─────────────────────────────────────────────────────
def show_ranking():
    st.title("🏆 순위")

    rankings = db.get_rankings()
    st.subheader("전체 순위")

    for idx, rank in enumerate(rankings, 1):
        if rank['id'] == st.session_state.student['id']:
            st.success(f"**{idx}위** - {rank['name']} (총점: {rank['total_score']}점, 정답: {rank['total_correct']}개) ⭐")
        else:
            st.info(f"**{idx}위** - {rank['name']} (총점: {rank['total_score']}점, 정답: {rank['total_correct']}개)")

    if st.button("← 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()


# ── 목표 대학 ─────────────────────────────────────────────────
def show_target_university():
    st.title("🎓 목표 대학 설정")

    student = db.get_student_by_id(st.session_state.student['id'])

    with st.form("target_form"):
        university = st.text_input("목표 대학", value=student['target_university'] or '')
        department = st.text_input("목표 학과", value=student['target_department'] or '')

        submitted = st.form_submit_button("저장하기", use_container_width=True)

        if submitted:
            db.update_target_university(student['id'], university, department)
            st.session_state.student['target_university'] = university
            st.session_state.student['target_department'] = department
            st.success("✅ 목표 대학이 저장되었습니다!")

    if st.button("← 돌아가기"):
        st.session_state.current_page = 'dashboard'
        st.rerun()


# ── 추천 도서 ─────────────────────────────────────────────────
def show_books():
    st.title("📚 이달의 추천 도서")

    show_ai_status()

    if 'book_list' not in st.session_state:
        with st.spinner("추천 도서를 불러오고 있습니다..."):
            st.session_state.book_list = ai.generate_book_recommendations()

    books = st.session_state.book_list
    st.subheader("이달의 추천 도서 10권")

    for i, book in enumerate(books, 1):
        st.write(f"{i}. {book}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 새로고침", use_container_width=True):
            del st.session_state.book_list
            st.rerun()

    with col2:
        if st.button("← 돌아가기", use_container_width=True):
            st.session_state.current_page = 'dashboard'
            st.rerun()


# ── 사이드바 ──────────────────────────────────────────────────
def build_sidebar():
    with st.sidebar:
        if st.session_state.logged_in:
            st.title("메뉴")

            if st.button("🏠 대시보드", use_container_width=True):
                st.session_state.current_page = 'dashboard'
                st.rerun()

            st.divider()

            # OpenAI ON/OFF 토글
            st.markdown("**AI 설정**")
            ai_on = st.toggle(
                "AI 사용 (OpenAI)",
                value=st.session_state.student_use_openai,
                key="sidebar_ai_toggle"
            )
            if ai_on != st.session_state.student_use_openai:
                st.session_state.student_use_openai = ai_on
                st.rerun()

            if st.session_state.student_use_openai:
                st.success("AI ON")
            else:
                st.warning("AI OFF")

            st.divider()

            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.student = None
                st.session_state.current_page = 'login'
                st.session_state.current_session_id = None
                st.session_state.questions = []
                st.rerun()


# ── 메인 ─────────────────────────────────────────────────────
build_sidebar()

if not st.session_state.logged_in:
    show_login()
else:
    page = st.session_state.current_page

    if page == 'dashboard':
        show_dashboard()
    elif page == 'new_study':
        show_new_study()
    elif page == 'solve':
        show_solve_questions()
    elif page == 'result':
        show_result()
    elif page == 'psychology':
        show_psychology()
    elif page == 'vocabulary':
        show_vocabulary()
    elif page == 'history':
        show_history()
    elif page == 'ranking':
        show_ranking()
    elif page == 'target_university':
        show_target_university()
    elif page == 'books':
        show_books()
    elif page == 'wrong_notes':
        show_wrong_notes()
    elif page == 'goals':
        show_study_goals()
