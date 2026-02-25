import streamlit as st
import datetime
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import naesin_database as db
import naesin_engine as eng

st.set_page_config(page_title="학생 내신/수시", layout="wide", initial_sidebar_state="expanded")

db.init_naesin_database()

PERFORMANCE_LABELS = {
    1: "1 - 계획보다 더 해냈어요",
    2: "2 - 계획대로 잘 했어요",
    3: "3 - 조금 했지만 괜찮아요",
    4: "4 - 컨디션이 조금 아쉬웠어요",
    5: "5 - 오늘은 쉬어가는 날이었어요",
}
UNDERSTANDING_LABELS = {
    1: "1 - 아주 잘 이해됐어요",
    2: "2 - 대부분 이해했어요",
    3: "3 - 조금 더 보면 될 것 같아요",
    4: "4 - 다시 한 번 보면 좋겠어요",
    5: "5 - 도움이 조금 필요해요",
}

ZONE_COLOR = {'안정': '#22c55e', '적정': '#f59e0b', '도전': '#ef4444', '알수없음': '#94a3b8'}
POSS_COLOR = {'높음': '#22c55e', '보통': '#f59e0b', '낮음': '#ef4444', '알수없음': '#94a3b8'}


# ─────────────────────────────────────────────────────────
# 공통 상단 내비
# ─────────────────────────────────────────────────────────

def top_nav():
    col_left, col_right = st.columns([3, 7])
    with col_left:
        st.page_link("pages/0_학생.py", label="정시 시스템으로", icon="🎓")
    with col_right:
        if 'naesin_track' not in st.session_state:
            st.session_state['naesin_track'] = 'naesin'
        prev = st.session_state['naesin_track']
        selected = st.radio(
            "내신/수시 전형 선택",
            options=['naesin', 'holistic'],
            format_func=lambda x: '내신-교과' if x == 'naesin' else '내신-학종',
            index=0 if prev == 'naesin' else 1,
            horizontal=True,
            key="track_selector",
            label_visibility="collapsed",
        )
        if selected != prev:
            st.session_state['naesin_track'] = selected
            st.rerun()


# ─────────────────────────────────────────────────────────
# 로그인
# ─────────────────────────────────────────────────────────

def login_section():
    if 'edu_user' in st.session_state and st.session_state['edu_user']:
        return True
    st.title("학생 내신/수시 플랫폼")
    st.markdown("**로그인** (데모: student1 / pass1 ~ student3 / pass3)")
    with st.form("login_form"):
        login_id = st.text_input("아이디", placeholder="student1")
        password = st.text_input("비밀번호", type="password", placeholder="pass1")
        if st.form_submit_button("로그인", use_container_width=True):
            user = db.get_edu_user(login_id, password)
            if user and user['role'] == 'student':
                st.session_state['edu_user'] = user
                student = db.get_edu_student_by_user_id(user['user_id'])
                st.session_state['edu_student'] = student
                st.rerun()
            elif user:
                st.error("학생 계정으로 로그인해주세요.")
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    return False


# ─────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────

def gate_banner(today_checks):
    msgs = []
    if not today_checks['learning']:
        msgs.append("학습 기록")
    if not today_checks['state']:
        msgs.append("상태 체크")
    if not today_checks['assessment']:
        msgs.append("자기평가")
    if msgs:
        st.warning(f"오늘 미입력 항목: **{', '.join(msgs)}** → 오늘의 변화/추천 갱신이 제한됩니다. (어제 이전 기록은 자유 조회 가능)")


def render_reco_table(results, err, label):
    if err:
        st.warning(err)
        return
    if not results:
        st.info("조건에 맞는 추천 결과가 없습니다.")
        return
    rows = []
    for r in results:
        rows.append({
            '대학': r['university'],
            '학과': r['department'],
            '학위': r['degree_type'],
            '지역': r['region'],
            '계열': r['category'],
            '구분': r['zone'],
            '가능도': r['possibility'],
            '부족분/여유': r['shortfall'],
            '근거': ' | '.join(r['evidence'][:2]),
            '홈페이지': r['homepage_url'],
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df.style.applymap(
            lambda v: f"color:{ZONE_COLOR.get(v, '#000')};font-weight:bold", subset=['구분']
        ).applymap(
            lambda v: f"color:{POSS_COLOR.get(v, '#000')}", subset=['가능도']
        ),
        use_container_width=True,
        height=min(400, 40 + len(rows) * 36),
    )
    st.caption(eng.DISCLAIMER)


# ─────────────────────────────────────────────────────────
# 탭 1: 내신(교과) 입력
# ─────────────────────────────────────────────────────────

def tab_naesin_input(student_id):
    st.subheader("내신(교과) 성적 입력")
    subjects = db.get_subjects()
    terms = db.get_terms()
    if not subjects or not terms:
        st.warning("과목 또는 학기 데이터가 없습니다.")
        return

    term_options = {f"{t['school_year']}학년도 {t['grade_level']}학년 {t['semester']}학기": t['term_id'] for t in terms}

    col1, col2 = st.columns([1, 2])
    with col1:
        selected_term_label = st.selectbox("학기 선택", list(term_options.keys()))
        selected_term_id = term_options[selected_term_label]

    with col2:
        subj_options = {s['subject_name']: s['subject_id'] for s in subjects}
        selected_subj = st.selectbox("과목 선택", list(subj_options.keys()))
        selected_subj_id = subj_options[selected_subj]

    col3, col4, col5 = st.columns(3)
    with col3:
        grade_num = st.selectbox("등급 (1~9)", list(range(1, 10)), index=2)
    with col4:
        raw_score = st.number_input("원점수 (선택)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
    with col5:
        rank_in_class = st.number_input("반석차 (선택)", min_value=0, value=0, step=1)

    if st.button("저장", key="save_grade", use_container_width=True, type="primary"):
        db.save_grade(
            student_id, selected_term_id, selected_subj_id, grade_num,
            raw_score if raw_score > 0 else None,
            rank_in_class if rank_in_class > 0 else None,
            'student'
        )
        st.success(f"{selected_term_label} / {selected_subj} / {grade_num}등급 저장 완료")
        st.rerun()

    st.divider()
    st.subheader("내 내신 기록")
    grades = db.get_grades(student_id)
    if grades:
        naesin_avg = db.get_naesin_avg(student_id)
        if naesin_avg:
            st.metric("전체 내신 평균 등급", f"{naesin_avg:.2f}등급")

        filter_term = st.selectbox("학기 필터", ['전체'] + list(term_options.keys()), key='grade_filter')
        if filter_term != '전체':
            fid = term_options[filter_term]
            show_grades = [g for g in grades if g['term_id'] == fid]
        else:
            show_grades = grades

        df = pd.DataFrame([{
            '학년도': g['school_year'],
            '학년': g['grade_level'],
            '학기': g['semester'],
            '과목': g['subject_name'],
            '계열': g['category'],
            '등급': g['grade_level_num'],
            '원점수': g['raw_score'] or '-',
            '반석차': g['rank_in_class'] or '-',
            '교사확인': '완료' if g['verified_by_teacher'] else '미확인',
        } for g in show_grades])

        st.dataframe(df, use_container_width=True)

        if len(grades) >= 2:
            fig = px.bar(
                df, x='과목', y='등급', color='학기',
                title='과목별 내신 등급',
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig.update_yaxes(autorange='reversed', title='등급 (낮을수록 우수)')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("입력된 내신 기록이 없습니다.")


# ─────────────────────────────────────────────────────────
# 탭 2: 활동(학종) 입력
# ─────────────────────────────────────────────────────────

def tab_activity_input(student_id):
    st.subheader("학종 활동 입력")
    act_types = db.get_activity_types()
    type_options = {t['name']: t['activity_type_id'] for t in act_types}

    with st.form("activity_form"):
        col1, col2 = st.columns(2)
        with col1:
            act_type_name = st.selectbox("활동 유형", list(type_options.keys()))
            title = st.text_input("활동 제목 *", placeholder="예: 수학탐구동아리 - 미적분 심화연구")
            role = st.selectbox("역할", ['개인', '리더', '팀원'])
            major_related = st.checkbox("전공 연계 활동")
        with col2:
            start_date = st.date_input("시작일", value=datetime.date.today() - datetime.timedelta(days=90))
            end_date = st.date_input("종료일", value=datetime.date.today())
            hours = st.number_input("총 활동 시간(h)", min_value=0.0, value=0.0, step=0.5)
            evidence_url = st.text_input("증빙 URL (선택)", placeholder="https://...")

        summary = st.text_area("활동 요약 (2~3문장)", placeholder="이 활동의 핵심을 간결하게 서술하세요.")
        detail = st.text_area("활동 상세", placeholder="구체적인 과정, 방법, 내용을 서술하세요.")
        learned = st.text_area("배운 점", placeholder="이 활동을 통해 배우고 느낀 점을 서술하세요.")
        tags_input = st.text_input("키워드 태그 (쉼표 구분)", placeholder="수학, 탐구, 리더십")

        submitted = st.form_submit_button("활동 저장", use_container_width=True, type="primary")
        if submitted:
            if not title.strip():
                st.error("활동 제목은 필수입니다.")
            else:
                tags = [t.strip() for t in tags_input.split(',') if t.strip()]
                db.save_activity(
                    student_id, type_options[act_type_name], title.strip(),
                    summary, detail, learned, role, major_related,
                    start_date.isoformat(), end_date.isoformat(), hours,
                    evidence_url or None, tags
                )
                st.success("활동이 저장되었습니다.")
                st.rerun()

    st.divider()
    st.subheader("내 활동 목록")
    acts = db.get_activities(student_id)
    if acts:
        strength = db.get_activity_strength(student_id)
        reviews = db.get_activity_reviews_for_student(student_id)
        pending = sum(1 for r in reviews if r['status'] == 'pending')
        approved = sum(1 for r in reviews if r['status'] == 'approved')

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 활동 수", len(acts))
        m2.metric("활동 강도 점수", f"{strength:.1f}/100")
        m3.metric("교사 승인", approved)
        m4.metric("검증 대기", pending)

        if pending > 0:
            st.warning(f"교사 검증 대기 중인 활동 {pending}건 → 학종 추천이 제한될 수 있습니다.")

        review_map = {r['activity_id']: r for r in reviews}
        rows = []
        for a in acts:
            rev = review_map.get(a['activity_id'])
            rows.append({
                '유형': a['type_name'],
                '제목': a['title'],
                '역할': a['role'],
                '전공연계': 'Y' if a['major_related'] else 'N',
                '시간': a['hours'] or 0,
                '기간': f"{a['start_date']} ~ {a['end_date']}",
                '교사검증': rev['status'] if rev else '미요청',
                '점수': rev['score'] if rev and rev['score'] else '-',
                '코멘트': rev['comment'] if rev and rev['comment'] else '-',
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("입력된 활동이 없습니다. 활동을 추가하면 학종 추천을 받을 수 있습니다.")


# ─────────────────────────────────────────────────────────
# 탭 3: 매일 입력
# ─────────────────────────────────────────────────────────

def tab_daily_input(student_id):
    subjects = db.get_subjects()
    subj_options = {s['subject_name']: s['subject_id'] for s in subjects}
    today = datetime.date.today().isoformat()

    st.subheader("오늘의 학습 기록")
    with st.form("daily_learning_form"):
        col1, col2 = st.columns(2)
        with col1:
            study_minutes = st.slider("오늘 공부 시간 (분)", 0, 600, 120, step=10)
            study_type = st.selectbox("학습 유형", [
                ('problems', '문제풀이'), ('concept', '개념학습'),
                ('review', '복습'), ('mock', '모의고사'), ('other', '기타')
            ], format_func=lambda x: x[1])
        with col2:
            selected_subjs = st.multiselect("오늘 학습 과목 (다중선택)", list(subj_options.keys()))

        if st.form_submit_button("학습 기록 저장", use_container_width=True, type="primary"):
            subj_ids = [subj_options[s] for s in selected_subjs]
            db.save_learning_log(student_id, today, study_minutes, subj_ids, study_type[0])
            st.success(f"학습 기록 저장! {study_minutes}분, {', '.join(selected_subjs) if selected_subjs else '과목 미선택'}")
            st.rerun()

    st.divider()
    st.subheader("오늘의 상태 체크")
    with st.form("daily_state_form"):
        col1, col2 = st.columns(2)
        with col1:
            focus = st.slider("집중력", 1, 5, 3, help="1=매우낮음, 5=매우높음")
            fatigue = st.slider("피로도", 1, 5, 3, help="1=매우낮음, 5=매우높음")
        with col2:
            stress = st.slider("스트레스", 1, 5, 3, help="1=매우낮음, 5=매우높음")
            motivation = st.slider("의욕", 1, 5, 3, help="1=매우낮음, 5=매우높음")

        if st.form_submit_button("상태 저장", use_container_width=True, type="primary"):
            db.save_state_check(student_id, today, focus, stress, fatigue, motivation)
            st.success("상태 저장 완료!")
            st.rerun()

    st.divider()
    st.subheader("오늘의 자기평가")
    with st.form("daily_assess_form"):
        perf = st.radio(
            "수행 평가",
            options=list(PERFORMANCE_LABELS.keys()),
            format_func=lambda k: PERFORMANCE_LABELS[k],
            horizontal=False, index=1
        )
        under = st.radio(
            "이해도 평가",
            options=list(UNDERSTANDING_LABELS.keys()),
            format_func=lambda k: UNDERSTANDING_LABELS[k],
            horizontal=False, index=1
        )
        if st.form_submit_button("자기평가 저장", use_container_width=True, type="primary"):
            db.save_self_assessment(student_id, today, perf, under)
            st.success("자기평가 저장 완료!")
            st.rerun()


# ─────────────────────────────────────────────────────────
# 탭 4: 대시보드
# ─────────────────────────────────────────────────────────

def tab_dashboard(student_id, user):
    today_checks = db.check_today_logs(student_id)
    gate_banner(today_checks)

    st.subheader(f"안녕하세요, {user['name']}!")

    demo_mode = st.toggle("데모 모드 (즉시 갱신)", value=True,
                          help="ON: 입력 즉시 변화 반영(데모) / OFF: 3일 평균 기준 안내(실제 운영)")
    if not demo_mode:
        st.info("운영 모드: 변화/추천은 3일 누적 데이터 평균을 기준으로 갱신됩니다.")

    naesin_avg = db.get_naesin_avg(student_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("내신 평균 등급", f"{naesin_avg:.2f}" if naesin_avg else "미입력")
    changes_7 = eng.calculate_changes(student_id, 7)
    changes_30 = eng.calculate_changes(student_id, 30)
    c2.metric("7일 평균 학습(분)", f"{changes_7.get('study_minutes_avg') or 0:.0f}")
    c3.metric("7일 평균 의욕", f"{changes_7.get('motivation_avg') or 0:.1f}/5")
    burnout = eng.detect_burnout_risk(changes_7)
    c4.metric("번아웃 위험", burnout['level'],
              delta=None, delta_color="off")

    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 최근 30일 학습 시간")
        logs = db.get_learning_logs(student_id, 30)
        if logs:
            df_log = pd.DataFrame(logs)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_log['date'], y=df_log['study_minutes'],
                                     mode='lines+markers', name='학습(분)',
                                     line=dict(color='#3b82f6', width=2)))
            fig.update_layout(margin=dict(t=10, b=30, l=10, r=10), height=220,
                               xaxis_title='날짜', yaxis_title='분')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("학습 기록이 없습니다.")

        st.markdown("#### 최근 7일 상태 변화")
        states = db.get_state_checks(student_id, 7)
        if states:
            df_s = pd.DataFrame(states)
            fig2 = go.Figure()
            for col, color, name in [
                ('focus', '#22c55e', '집중'), ('motivation', '#3b82f6', '의욕'),
                ('stress', '#f59e0b', '스트레스'), ('fatigue', '#ef4444', '피로')
            ]:
                fig2.add_trace(go.Scatter(x=df_s['date'], y=df_s[col],
                                          mode='lines+markers', name=name,
                                          line=dict(color=color)))
            fig2.update_layout(margin=dict(t=10, b=30, l=10, r=10), height=200,
                                yaxis=dict(range=[0, 6]))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("상태 기록이 없습니다.")

    with col_right:
        st.markdown("#### 번아웃 위험 분석")
        level_color = {'낮음': '#22c55e', '보통': '#f59e0b', '높음': '#ef4444'}
        b_level = burnout['level']
        b_score = burnout['score']
        b_color = level_color.get(b_level, '#94a3b8')
        st.markdown(
            f"<div style='padding:12px;border-radius:8px;background:{b_color};color:#fff;font-weight:bold;font-size:16px;'>"
            f"위험 수준: {b_level} (점수 {b_score}/10)</div>",
            unsafe_allow_html=True
        )
        if burnout['reasons']:
            for r in burnout['reasons']:
                st.markdown(f"- {r}")

        st.markdown("#### 7일/30일 변화 요약")
        rows_change = [
            ('기간', '7일', '30일'),
            ('평균 학습(분)', f"{changes_7.get('study_minutes_avg') or 0:.0f}", f"{changes_30.get('study_minutes_avg') or 0:.0f}"),
            ('집중 평균', f"{changes_7.get('focus_avg') or 0:.1f}", f"{changes_30.get('focus_avg') or 0:.1f}"),
            ('의욕 평균', f"{changes_7.get('motivation_avg') or 0:.1f}", f"{changes_30.get('motivation_avg') or 0:.1f}"),
            ('스트레스 평균', f"{changes_7.get('stress_avg') or 0:.1f}", f"{changes_30.get('stress_avg') or 0:.1f}"),
            ('기록 일수', str(changes_7.get('log_days', 0)), str(changes_30.get('log_days', 0))),
        ]
        st.table(pd.DataFrame(rows_change[1:], columns=rows_change[0]))

    st.divider()
    st.subheader("대학+학과 추천")
    st.caption("추천 결과는 참고용입니다. 단정하거나 과장하지 않으며, 반드시 대학 공식 입학처를 확인하세요.")

    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    with r_col1:
        option = st.selectbox("옵션", ['A(보수적)', 'B(균형)', 'C(공격적)'], index=1, key='reco_opt_s')
        opt_key = option[0]
    with r_col2:
        degree_f = st.selectbox("학위", ['전체', '4년제', '2년제'], key='deg_f_s')
        degree_map = {'전체': None, '4년제': 'four_year', '2년제': 'two_year'}
    with r_col3:
        cat_f = st.selectbox("계열", ['전체', '인문', '이공', '의약', '예체능'], key='cat_f_s')
    with r_col4:
        _default_track_idx = 1 if st.session_state.get('naesin_track') == 'holistic' else 0
        track_sel = st.selectbox("전형", ['내신(교과)', '내신(학종)'], index=_default_track_idx, key='track_sel_s')

    track_key = 'naesin' if '교과' in track_sel else 'holistic'

    reco_results, reco_err = eng.get_recommendations_with_snapshot(
        student_id,
        track=track_key,
        option=opt_key,
        degree_filter=degree_map.get(degree_f),
        category_filter=None if cat_f == '전체' else cat_f,
        limit=5,
    )

    if track_key == 'holistic':
        acts = db.get_activities(student_id)
        if not acts:
            st.error("활동 데이터 없음 → 학종 추천 불가. 활동 입력 탭에서 활동을 먼저 등록하세요.")
        reviews = db.get_activity_reviews_for_student(student_id)
        pending = sum(1 for r in reviews if r['status'] == 'pending')
        if pending > 0:
            st.warning(f"교사 검증 대기 {pending}건 → 학종 추천 정확도가 낮을 수 있습니다. (검증 대기 표시)")

    render_reco_table(reco_results, reco_err, track_sel)

    if reco_results:
        r0 = reco_results[0]
        missing = r0.get('shortfall', '')
        ev = r0.get('evidence', [])
        st.info(
            f"**TOP1 추천: {r0['university']} {r0['department']}** ({r0['zone']}, 가능도 {r0['possibility']})\n\n"
            f"부족분/여유: {missing}\n\n조건: {ev[-1] if ev else ''}"
        )

    st.divider()
    st.subheader("예측 (d7 / d30 / AI 보조)")
    st.caption("예측은 참고용 보조 정보입니다. 단정 금지. 전제조건·부족분을 반드시 확인하세요.")

    forecasts = eng.generate_forecasts(student_id)

    fc_map = {(f['metric'], f['window']): f for f in forecasts}

    tab_f1, tab_f2, tab_f3 = st.tabs(["d7 예측", "d30 예측", "AI 종합"])

    with tab_f1:
        f = fc_map.get(('naesin_avg', 'd7'))
        if f:
            v = f['value']
            st.metric("내신 평균 7일 예측", f"{v.get('estimate', '-')}등급",
                      delta=f"{round(v.get('estimate', 0) - v.get('current', 0), 2):+.2f}",
                      delta_color="inverse")
            st.caption(f"범위: {v.get('range', ['-','-'])[0]} ~ {v.get('range', ['-','-'])[1]} | 전제: {v.get('condition','')}")
        f2 = fc_map.get(('burnout_risk', 'd7'))
        if f2:
            v2 = f2['value']
            st.metric("번아웃 위험 (7일)", v2.get('level', '-'))
            if v2.get('reasons'):
                st.caption("원인: " + ", ".join(v2['reasons']))

    with tab_f2:
        f = fc_map.get(('naesin_avg', 'd30'))
        if f:
            v = f['value']
            st.metric("내신 평균 30일 예측", f"{v.get('estimate', '-')}등급",
                      delta=f"{round(v.get('estimate', 0) - v.get('current', 0), 2):+.2f}",
                      delta_color="inverse")
            st.caption(f"전제: {v.get('condition', '')}")
        f3 = fc_map.get(('activity_strength', 'd7'))
        if f3:
            v3 = f3['value']
            st.metric("활동 강도 추세", v3.get('trend', '-'))

    with tab_f3:
        f = fc_map.get(('admission_readiness', 'ai'))
        if f:
            v = f['value']
            st.metric("입시 준비도 (AI 산출)", f"{v.get('score', 0):.1f}/100",
                      help="규칙 기반 산출값. 합격 보장 아님")
            st.markdown(f"**수준:** {v.get('level', '-')}")
            if v.get('basis'):
                st.markdown("**근거:**")
                for b in v['basis']:
                    st.markdown(f"  - {b}")
            if v.get('missing'):
                st.markdown("**부족분/조건:**")
                for m in v['missing']:
                    st.markdown(f"  - {m}")
            if v.get('next_actions'):
                st.markdown("**다음 행동 (1~2개):**")
                for a in v['next_actions']:
                    st.markdown(f"  - {a}")
            st.caption(f['disclaimer'])


# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────

def main():
    top_nav()

    if not login_section():
        return

    user = st.session_state['edu_user']
    student = st.session_state.get('edu_student')

    if not student:
        st.error("학생 프로필을 찾을 수 없습니다.")
        return

    student_id = student['student_id']

    with st.sidebar:
        st.markdown(f"**{user['name']}** ({user['login_id']})")
        if st.button("로그아웃", use_container_width=True):
            for k in ['edu_user', 'edu_student']:
                st.session_state.pop(k, None)
            st.rerun()

    is_holistic = st.session_state.get('naesin_track') == 'holistic'

    if is_holistic:
        tab2, tab1, tab3, tab4 = st.tabs(["활동(학종) 입력", "내신(교과) 입력", "매일 입력", "대시보드"])
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["내신(교과) 입력", "활동(학종) 입력", "매일 입력", "대시보드"])

    with tab1:
        tab_naesin_input(student_id)
    with tab2:
        tab_activity_input(student_id)
    with tab3:
        tab_daily_input(student_id)
    with tab4:
        tab_dashboard(student_id, user)


main()
