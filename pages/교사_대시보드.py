import streamlit as st
import datetime
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import naesin_database as db
import naesin_engine as eng

st.set_page_config(page_title="교사 내신/수시 대시보드", layout="wide", initial_sidebar_state="expanded")

db.init_naesin_database()

ZONE_COLOR = {'안정': '#22c55e', '적정': '#f59e0b', '도전': '#ef4444', '알수없음': '#94a3b8'}
POSS_COLOR = {'높음': '#22c55e', '보통': '#f59e0b', '낮음': '#ef4444', '알수없음': '#94a3b8'}


def top_nav():
    st.markdown("""
    <style>
    .nav-bar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;}
    .nav-btn{padding:6px 16px;border-radius:20px;font-size:14px;font-weight:600;text-decoration:none;
             background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;}
    .nav-btn.active{background:#059669;color:#fff;border-color:#059669;}
    </style>
    <div class="nav-bar">
      <a class="nav-btn" href="/3_교사" target="_self">정시 대시보드</a>
      <a class="nav-btn active" href="/교사_대시보드" target="_self">내신/수시 대시보드</a>
    </div>
    """, unsafe_allow_html=True)


def login_section():
    if 'edu_teacher' in st.session_state and st.session_state['edu_teacher']:
        return True
    st.title("교사 내신/수시 대시보드")
    st.markdown("**로그인** (데모: teacher1 / pass1)")
    with st.form("teacher_login"):
        login_id = st.text_input("아이디", placeholder="teacher1")
        password = st.text_input("비밀번호", type="password", placeholder="pass1")
        if st.form_submit_button("로그인", use_container_width=True):
            user = db.get_edu_user(login_id, password)
            if user and user['role'] == 'teacher':
                st.session_state['edu_teacher'] = user
                st.rerun()
            elif user:
                st.error("교사 계정으로 로그인해주세요.")
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    return False


# ─────────────────────────────────────────────────────────
# 탭 1: 학급 전체 대시보드
# ─────────────────────────────────────────────────────────

def tab_class_overview(teacher_user_id):
    st.subheader("학급 전체 현황")

    students = db.get_class_students(teacher_user_id)
    if not students:
        st.warning("연결된 학생이 없습니다.")
        return

    student_ids = [s['student_id'] for s in students]
    risk_data = eng.analyze_class_risk(student_ids)
    risk_map = {r['student_id']: r for r in risk_data}

    st.markdown("#### 필터")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        risk_filter = st.selectbox("위험군 필터", ['전체', '높음', '보통', '낮음'])
    with col_f2:
        input_filter = st.selectbox("입력률 필터", ['전체', '오늘 학습미입력', '오늘 상태미입력'])
    with col_f3:
        act_filter = st.selectbox("활동 필터", ['전체', '활동 없음'])

    rows = []
    for s in students:
        sid = s['student_id']
        risk = risk_map.get(sid, {})
        row = {
            'student_id': sid,
            '이름': s['student_name'],
            '학년': s['grade_level'],
            '전형선호': s['track_preference'],
            '위험수준': risk.get('burnout_level', '-'),
            '학습평균(7일분)': f"{risk.get('study_avg_7d') or 0:.0f}",
            '의욕평균(7일)': f"{risk.get('motivation_avg_7d') or 0:.1f}",
            '오늘학습': 'O' if risk.get('today_learning_done') else 'X',
            '오늘상태': 'O' if risk.get('today_state_done') else 'X',
            '활동수': risk.get('activity_count', 0),
            '검증대기': risk.get('pending_reviews', 0),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    if risk_filter != '전체':
        df = df[df['위험수준'] == risk_filter]
    if input_filter == '오늘 학습미입력':
        df = df[df['오늘학습'] == 'X']
    elif input_filter == '오늘 상태미입력':
        df = df[df['오늘상태'] == 'X']
    if act_filter == '활동 없음':
        df = df[df['활동수'] == 0]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("총 학생", len(students))
    m2.metric("위험군(높음)", len([r for r in risk_data if r['burnout_level'] == '높음']))
    m3.metric("오늘 학습입력률", f"{sum(1 for r in risk_data if r['today_learning_done'])/len(students)*100:.0f}%")
    m4.metric("오늘 상태입력률", f"{sum(1 for r in risk_data if r['today_state_done'])/len(students)*100:.0f}%")
    m5.metric("활동 없는 학생", len([r for r in risk_data if r['activity_count'] == 0]))

    st.markdown("#### 학생 목록")
    display_df = df.drop(columns=['student_id'])
    st.dataframe(
        display_df.style
          .applymap(lambda v: 'color:#ef4444;font-weight:bold' if v == '높음' else
                              ('color:#f59e0b' if v == '보통' else ''), subset=['위험수준'])
          .applymap(lambda v: 'color:#ef4444' if v == 'X' else 'color:#22c55e', subset=['오늘학습', '오늘상태']),
        use_container_width=True
    )

    st.markdown("#### 내신 등급 분포 (전체)")
    all_grades = []
    for sid in student_ids:
        g = db.get_naesin_avg(sid)
        if g:
            all_grades.append(g)
    if all_grades:
        import statistics
        st.metric("학급 내신 평균", f"{statistics.mean(all_grades):.2f}등급")
        fig = px.histogram(all_grades, nbins=9, range_x=[1, 9], title='내신 평균 등급 분포',
                           labels={'value': '등급'}, color_discrete_sequence=['#3b82f6'])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 전형 선택 분포")
    track_counts = df['전형선호'].value_counts().reset_index()
    track_counts.columns = ['전형', '학생수']
    fig2 = px.pie(track_counts, values='학생수', names='전형', title='정시 vs 내신 선택',
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig2, use_container_width=True)

    st.caption("전형 권고는 근거+선택지 제공 방식으로만 진행합니다. 단정 금지.")


# ─────────────────────────────────────────────────────────
# 탭 2: 개인 상세
# ─────────────────────────────────────────────────────────

def tab_individual(teacher_user_id):
    st.subheader("학생 개인 상세")

    students = db.get_class_students(teacher_user_id)
    if not students:
        st.warning("연결된 학생이 없습니다.")
        return

    sel_options = {f"{s['student_name']} (ID:{s['student_id']})": s for s in students}
    sel = st.selectbox("학생 선택", list(sel_options.keys()))
    student = sel_options[sel]
    student_id = student['student_id']
    student_name = student['student_name']

    today_checks = db.check_today_logs(student_id)
    if not today_checks['learning'] or not today_checks['state']:
        st.warning(f"[{student_name}] 오늘 미입력 항목이 있습니다. (어제 이전 기록은 자유 조회 가능)")

    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(["교과 내신", "학종 활동", "일일 기록", "예측/추천"])

    with sub_tab1:
        _individual_naesin(student_id, student_name)
    with sub_tab2:
        _individual_holistic(student_id, student_name, teacher_user_id)
    with sub_tab3:
        _individual_daily(student_id, student_name)
    with sub_tab4:
        _individual_forecast(student_id, student_name)


def _individual_naesin(student_id, student_name):
    st.markdown(f"#### {student_name} 교과 내신")
    naesin_avg = db.get_naesin_avg(student_id)
    if naesin_avg:
        st.metric("내신 평균 등급", f"{naesin_avg:.2f}등급")
    grades = db.get_grades(student_id)
    if not grades:
        st.info("등록된 성적 없음")
        return

    df = pd.DataFrame([{
        '학년도': g['school_year'], '학기': g['semester'],
        '과목': g['subject_name'], '계열': g['category'],
        '등급': g['grade_level_num'], '원점수': g['raw_score'] or '-',
        '교사확인': '완료' if g['verified_by_teacher'] else '미확인',
        'grade_id': g['grade_id'],
    } for g in grades])

    st.dataframe(df.drop(columns=['grade_id']), use_container_width=True)

    if len(grades) >= 2:
        fig = px.line(df, x='학기', y='등급', color='과목',
                      title='과목별 등급 추세', markers=True)
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**약점 과목 (등급 5이상)**")
    weak = [g for g in grades if g['grade_level_num'] >= 5]
    if weak:
        for g in weak:
            st.markdown(f"- {g['subject_name']}: {g['grade_level_num']}등급 ({g['school_year']} {g['semester']}학기)")
    else:
        st.success("약점 과목 없음 (등급 5 이상 없음)")

    st.markdown("**미확인 성적 교사 확인 처리**")
    unverified = [g for g in grades if not g['verified_by_teacher']]
    if unverified:
        for g in unverified:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{g['subject_name']} {g['grade_level_num']}등급 ({g['school_year']} {g['semester']}학기)")
            with col2:
                if st.button("확인 처리", key=f"verify_{g['grade_id']}"):
                    db.verify_grade(g['grade_id'], None)
                    st.rerun()
    else:
        st.success("모든 성적 확인 완료")


def _individual_holistic(student_id, student_name, teacher_user_id):
    st.markdown(f"#### {student_name} 학종 활동 검증")

    activities = db.get_pending_activities_for_teacher(teacher_user_id)
    student_acts = [a for a in activities if a['student_id'] == student_id]

    if not student_acts:
        st.info("검증할 활동이 없습니다.")
        return

    strength = db.get_activity_strength(student_id)
    st.metric("활동 강도 점수", f"{strength:.1f}/100")

    for act in student_acts:
        with st.expander(f"[{act['type_name']}] {act['title']} — 현재: {act.get('review_status') or '미검토'}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**요약:** {act.get('summary', '-')}")
                st.markdown(f"**배운점:** {act.get('learned', '-')}")
                st.markdown(f"**역할:** {act.get('role', '-')} | **전공연계:** {'Y' if act.get('major_related') else 'N'}")
                st.markdown(f"**기간:** {act.get('start_date')} ~ {act.get('end_date')} | **시간:** {act.get('hours') or 0}h")
            with col2:
                aid = act['activity_id']
                status_val = st.selectbox(
                    "검증 상태",
                    ['pending', 'approved', 'rejected'],
                    index=['pending', 'approved', 'rejected'].index(act.get('review_status') or 'pending'),
                    key=f"status_{student_id}_{aid}"
                )
                score_val = st.slider(
                    "점수 (0~100)",
                    0, 100,
                    int(act.get('review_score') or 60),
                    key=f"score_{student_id}_{aid}"
                )
                comment_val = st.text_area(
                    "코멘트",
                    value=act.get('review_comment') or '',
                    key=f"comment_{student_id}_{aid}"
                )
                if st.button("저장", key=f"save_rev_{student_id}_{aid}", type="primary"):
                    db.save_activity_review(
                        act['activity_id'], teacher_user_id,
                        status_val, score_val, comment_val
                    )
                    st.success("검증 저장 완료!")
                    st.rerun()


def _individual_daily(student_id, student_name):
    st.markdown(f"#### {student_name} 일일 기록")
    ch7 = eng.calculate_changes(student_id, 7)
    ch30 = eng.calculate_changes(student_id, 30)
    burnout = eng.detect_burnout_risk(ch7)

    level_color = {'낮음': '#22c55e', '보통': '#f59e0b', '높음': '#ef4444'}
    b_lv = burnout['level']
    b_clr = level_color.get(b_lv, '#94a3b8')
    st.markdown(
        f"<div style='padding:8px 16px;border-radius:6px;background:{b_clr};color:#fff;display:inline-block;font-weight:bold;'>"
        f"번아웃 위험: {b_lv}</div>",
        unsafe_allow_html=True
    )
    if burnout['reasons']:
        st.caption("원인: " + " / ".join(burnout['reasons']))

    st.table(pd.DataFrame([
        ('평균 학습(분)', f"{ch7.get('study_minutes_avg') or 0:.0f}", f"{ch30.get('study_minutes_avg') or 0:.0f}"),
        ('집중 평균', f"{ch7.get('focus_avg') or 0:.1f}", f"{ch30.get('focus_avg') or 0:.1f}"),
        ('의욕 평균', f"{ch7.get('motivation_avg') or 0:.1f}", f"{ch30.get('motivation_avg') or 0:.1f}"),
        ('스트레스 평균', f"{ch7.get('stress_avg') or 0:.1f}", f"{ch30.get('stress_avg') or 0:.1f}"),
        ('기록 일수', str(ch7.get('log_days', 0)), str(ch30.get('log_days', 0))),
    ], columns=['항목', '7일', '30일']))

    states30 = db.get_state_checks(student_id, 30)
    if states30:
        df_s = pd.DataFrame(states30)
        fig = go.Figure()
        for col, color, name in [
            ('focus', '#22c55e', '집중'), ('motivation', '#3b82f6', '의욕'),
            ('stress', '#f59e0b', '스트레스'), ('fatigue', '#ef4444', '피로')
        ]:
            fig.add_trace(go.Scatter(x=df_s['date'], y=df_s[col], mode='lines', name=name, line=dict(color=color)))
        fig.update_layout(margin=dict(t=10, b=30), height=200, yaxis=dict(range=[0, 6]))
        st.plotly_chart(fig, use_container_width=True)


def _individual_forecast(student_id, student_name):
    st.markdown(f"#### {student_name} 예측 / 추천")
    st.caption("예측은 보조 참고값입니다. 단정 금지. 전제조건 확인 필수.")

    forecasts = eng.generate_forecasts(student_id)
    fc_map = {(f['metric'], f['window']): f for f in forecasts}

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**d7 예측**")
        f = fc_map.get(('naesin_avg', 'd7'))
        if f:
            v = f['value']
            st.metric("내신 7일 예측", f"{v.get('estimate', '-')}",
                      delta=f"{round(v.get('estimate', 0) - v.get('current', 0), 2):+.2f}",
                      delta_color="inverse")
        f2 = fc_map.get(('burnout_risk', 'd7'))
        if f2:
            st.metric("번아웃 위험", f2['value'].get('level', '-'))

    with col2:
        st.markdown("**d30 예측**")
        f = fc_map.get(('naesin_avg', 'd30'))
        if f:
            v = f['value']
            st.metric("내신 30일 예측", f"{v.get('estimate', '-')}",
                      delta=f"{round(v.get('estimate', 0) - v.get('current', 0), 2):+.2f}",
                      delta_color="inverse")
        f3 = fc_map.get(('activity_strength', 'd7'))
        if f3:
            st.metric("활동 강도 추세", f3['value'].get('trend', '-'))

    with col3:
        st.markdown("**AI 종합 준비도**")
        f = fc_map.get(('admission_readiness', 'ai'))
        if f:
            v = f['value']
            st.metric("입시 준비도", f"{v.get('score', 0):.1f}/100")
            if v.get('missing'):
                for m in v['missing'][:2]:
                    st.caption(f"- {m}")

    st.markdown("#### 교과 추천 TOP5")
    rn, en = eng.get_recommendations_with_snapshot(student_id, 'naesin', 'B', limit=5)
    if rn:
        st.dataframe(pd.DataFrame([{
            '대학': r['university'], '학과': r['department'],
            '학위': r['degree_type'], '지역': r['region'],
            '구분': r['zone'], '가능도': r['possibility'],
            '부족분': r['shortfall'], '링크': r['homepage_url'],
        } for r in rn]), use_container_width=True)
    elif en:
        st.warning(en)

    st.markdown("#### 학종 추천 TOP5")
    rh, eh = eng.get_recommendations_with_snapshot(student_id, 'holistic', 'B', limit=5)
    if rh:
        st.dataframe(pd.DataFrame([{
            '대학': r['university'], '학과': r['department'],
            '학위': r['degree_type'], '지역': r['region'],
            '구분': r['zone'], '가능도': r['possibility'],
            '부족분': r['shortfall'], '링크': r['homepage_url'],
        } for r in rh]), use_container_width=True)
    elif eh:
        st.warning(eh)

    st.caption(eng.DISCLAIMER)


# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────

def main():
    top_nav()

    if not login_section():
        return

    teacher = st.session_state['edu_teacher']

    with st.sidebar:
        st.markdown(f"**{teacher['name']}**")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.pop('edu_teacher', None)
            st.rerun()

    tab1, tab2 = st.tabs(["학급 전체 대시보드", "학생 개인 상세"])

    with tab1:
        tab_class_overview(teacher['user_id'])
    with tab2:
        tab_individual(teacher['user_id'])


main()
