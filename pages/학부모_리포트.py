import streamlit as st
import datetime
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import naesin_database as db
import naesin_engine as eng

st.set_page_config(page_title="학부모 내신/수시 리포트", layout="wide", initial_sidebar_state="expanded")

db.init_naesin_database()

ZONE_COLOR = {'안정': '#22c55e', '적정': '#f59e0b', '도전': '#ef4444', '알수없음': '#94a3b8'}
POSS_COLOR = {'높음': '#22c55e', '보통': '#f59e0b', '낮음': '#ef4444', '알수없음': '#94a3b8'}


def top_nav():
    st.markdown("""
    <style>
    .nav-bar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;}
    .nav-btn{padding:6px 16px;border-radius:20px;font-size:14px;font-weight:600;text-decoration:none;
             background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;}
    .nav-btn.active{background:#7c3aed;color:#fff;border-color:#7c3aed;}
    </style>
    <div class="nav-bar">
      <a class="nav-btn" href="/2_학부모" target="_self">정시 리포트</a>
      <a class="nav-btn active" href="/학부모_리포트" target="_self">내신/수시 리포트</a>
    </div>
    """, unsafe_allow_html=True)


def login_section():
    if 'edu_parent' in st.session_state and st.session_state['edu_parent']:
        return True
    st.title("학부모 내신/수시 리포트")
    st.markdown("**로그인** (데모: parent1 / pass1)")
    with st.form("parent_login"):
        login_id = st.text_input("아이디", placeholder="parent1")
        password = st.text_input("비밀번호", type="password", placeholder="pass1")
        if st.form_submit_button("로그인", use_container_width=True):
            user = db.get_edu_user(login_id, password)
            if user and user['role'] == 'parent':
                st.session_state['edu_parent'] = user
                st.rerun()
            elif user:
                st.error("학부모 계정으로 로그인해주세요.")
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    return False


def gate_banner(today_checks, student_name):
    msgs = []
    if not today_checks['learning']:
        msgs.append("학습 기록")
    if not today_checks['state']:
        msgs.append("상태 체크")
    if msgs:
        st.warning(f"[{student_name}] 오늘 미입력 항목: **{', '.join(msgs)}** → 오늘의 변화가 제한됩니다. (어제 이전 기록은 자유 조회 가능)")


def render_reco_table_parent(results, err, label):
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
        df.style
          .applymap(lambda v: f"color:{ZONE_COLOR.get(v,'#000')};font-weight:bold", subset=['구분'])
          .applymap(lambda v: f"color:{POSS_COLOR.get(v,'#000')}", subset=['가능도']),
        use_container_width=True
    )
    st.caption(eng.DISCLAIMER)


def section_naesin(student_id, student_name):
    st.subheader(f"{student_name} - 내신(교과) 리포트")

    naesin_avg = db.get_naesin_avg(student_id)
    if naesin_avg:
        st.metric("내신 전체 평균 등급", f"{naesin_avg:.2f}등급")
    else:
        st.warning("내신 데이터가 없습니다.")
        return

    grades = db.get_grades(student_id)
    if not grades:
        st.info("등록된 성적이 없습니다.")
        return

    df_all = pd.DataFrame([{
        '학년도': g['school_year'],
        '학년': g['grade_level'],
        '학기': g['semester'],
        '과목': g['subject_name'],
        '계열': g['category'],
        '등급': g['grade_level_num'],
        '원점수': g['raw_score'] or '-',
        '교사확인': '완료' if g['verified_by_teacher'] else '미확인',
    } for g in grades])

    st.markdown("#### 학기별 / 과목별 내신 표")
    terms_db = db.get_terms()
    term_options = {f"{t['school_year']}년 {t['grade_level']}학년 {t['semester']}학기": t['term_id'] for t in terms_db}
    sel_term = st.selectbox("학기 필터", ['전체'] + list(term_options.keys()), key=f'parent_term_{student_id}')
    if sel_term != '전체':
        fid = term_options[sel_term]
        show = [g for g in grades if g['term_id'] == fid]
        df_show = pd.DataFrame([{
            '과목': g['subject_name'], '계열': g['category'],
            '등급': g['grade_level_num'], '원점수': g['raw_score'] or '-',
            '교사확인': '완료' if g['verified_by_teacher'] else '미확인',
        } for g in show])
    else:
        df_show = df_all
    st.dataframe(df_show, use_container_width=True)

    st.markdown("#### 과목별 등급 추세")
    if len(grades) >= 2:
        fig = px.line(df_all, x='학기', y='등급', color='과목',
                      title='학기별 과목 등급 변화', markers=True)
        fig.update_yaxes(autorange='reversed', title='등급')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 과목 편중 분석")
    cat_avg = df_all.groupby('계열')['등급'].mean().reset_index()
    fig2 = px.bar(cat_avg, x='계열', y='등급', title='계열별 평균 등급', color='계열')
    fig2.update_yaxes(autorange='reversed')
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### 내신(교과) 대학+학과 추천")
    col1, col2 = st.columns(2)
    with col1:
        opt = st.selectbox("옵션", ['A(보수적)', 'B(균형)', 'C(공격적)'], index=1, key=f'p_opt_n_{student_id}')
    with col2:
        deg = st.selectbox("학위", ['전체', '4년제', '2년제'], key=f'p_deg_n_{student_id}')
    deg_map = {'전체': None, '4년제': 'four_year', '2년제': 'two_year'}
    results, err = eng.get_recommendations_with_snapshot(student_id, 'naesin', opt[0], deg_map.get(deg), limit=10)
    render_reco_table_parent(results, err, '내신교과')


def section_holistic(student_id, student_name):
    st.subheader(f"{student_name} - 내신(학종) 리포트")

    acts = db.get_activities(student_id)
    reviews = db.get_activity_reviews_for_student(student_id)
    strength = db.get_activity_strength(student_id)

    if not acts:
        st.warning("활동 데이터가 없습니다.")
        return

    pending = sum(1 for r in reviews if r['status'] == 'pending')
    approved = sum(1 for r in reviews if r['status'] == 'approved')

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 활동", len(acts))
    m2.metric("활동 강도", f"{strength:.1f}/100")
    m3.metric("교사 승인", approved)
    m4.metric("검증 대기", pending)

    if pending > 0:
        st.warning(f"교사 검증 대기 {pending}건 → 학종 추천 정확도가 낮을 수 있습니다.")

    rev_map = {r['activity_id']: r for r in reviews}
    rows = []
    for a in acts:
        rev = rev_map.get(a['activity_id'])
        rows.append({
            '유형': a['type_name'],
            '제목': a['title'],
            '요약': (a['summary'] or '')[:40],
            '배운점': (a['learned'] or '')[:40],
            '역할': a['role'],
            '전공연계': 'Y' if a['major_related'] else 'N',
            '시간(h)': a['hours'] or 0,
            '기간': f"{a['start_date']} ~ {a['end_date']}",
            '교사검증': rev['status'] if rev else '미요청',
            '점수': rev['score'] if rev and rev['score'] else '-',
            '코멘트': rev['comment'] if rev and rev['comment'] else '-',
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.markdown("#### 내신(학종) 대학+학과 추천")
    col1, col2 = st.columns(2)
    with col1:
        opt = st.selectbox("옵션", ['A(보수적)', 'B(균형)', 'C(공격적)'], index=1, key=f'p_opt_h_{student_id}')
    with col2:
        deg = st.selectbox("학위", ['전체', '4년제', '2년제'], key=f'p_deg_h_{student_id}')
    deg_map = {'전체': None, '4년제': 'four_year', '2년제': 'two_year'}
    results, err = eng.get_recommendations_with_snapshot(student_id, 'holistic', opt[0], deg_map.get(deg), limit=10)
    render_reco_table_parent(results, err, '학종')

    if results:
        r0 = results[0]
        st.info(
            f"**TOP1: {r0['university']} {r0['department']}** ({r0['zone']}, 가능도 {r0['possibility']})\n\n"
            f"부족분: {r0['shortfall']}\n\n이 추천은 현재 활동 데이터 기준이며, 실제 합격을 보장하지 않습니다."
        )


def section_daily(student_id, student_name):
    st.subheader(f"{student_name} - 일일 학습/상태 리포트")

    logs30 = db.get_learning_logs(student_id, 30)
    states30 = db.get_state_checks(student_id, 30)
    assessments30 = db.get_self_assessments(student_id, 30)

    if not logs30 and not states30:
        st.info("일일 기록이 없습니다.")
        return

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### 30일 학습 시간")
        if logs30:
            df = pd.DataFrame(logs30)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['date'], y=df['study_minutes'], name='학습(분)', marker_color='#3b82f6'))
            avg_min = df['study_minutes'].mean()
            fig.add_hline(y=avg_min, line_dash='dash', annotation_text=f'평균 {avg_min:.0f}분')
            fig.update_layout(margin=dict(t=10, b=30), height=230)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### 7일 학습 vs 30일 변화")
        ch7 = eng.calculate_changes(student_id, 7)
        ch30 = eng.calculate_changes(student_id, 30)
        rows = [
            ('평균 학습(분)', f"{ch7.get('study_minutes_avg') or 0:.0f}", f"{ch30.get('study_minutes_avg') or 0:.0f}"),
            ('집중 평균', f"{ch7.get('focus_avg') or 0:.1f}", f"{ch30.get('focus_avg') or 0:.1f}"),
            ('의욕 평균', f"{ch7.get('motivation_avg') or 0:.1f}", f"{ch30.get('motivation_avg') or 0:.1f}"),
            ('스트레스 평균', f"{ch7.get('stress_avg') or 0:.1f}", f"{ch30.get('stress_avg') or 0:.1f}"),
        ]
        st.table(pd.DataFrame(rows, columns=['항목', '7일', '30일']))

    with col_right:
        st.markdown("#### 30일 상태 추세")
        if states30:
            df_s = pd.DataFrame(states30)
            fig2 = go.Figure()
            for col, color, name in [
                ('focus', '#22c55e', '집중'), ('motivation', '#3b82f6', '의욕'),
                ('stress', '#f59e0b', '스트레스'), ('fatigue', '#ef4444', '피로')
            ]:
                fig2.add_trace(go.Scatter(x=df_s['date'], y=df_s[col],
                                          mode='lines', name=name, line=dict(color=color)))
            fig2.update_layout(margin=dict(t=10, b=30), height=230,
                                yaxis=dict(range=[0, 6]))
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### 자기평가 추세")
        if assessments30:
            df_a = pd.DataFrame(assessments30)
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df_a['date'], y=df_a['performance_level'],
                                      mode='lines+markers', name='수행', line=dict(color='#8b5cf6')))
            fig3.add_trace(go.Scatter(x=df_a['date'], y=df_a['understanding_level'],
                                      mode='lines+markers', name='이해', line=dict(color='#06b6d4')))
            fig3.update_layout(margin=dict(t=10, b=30), height=200,
                                yaxis=dict(range=[0, 6], autorange='reversed'))
            st.plotly_chart(fig3, use_container_width=True)
            st.caption("수행/이해: 1이 최고, 5가 낮음 (역방향)")


def main():
    top_nav()

    if not login_section():
        return

    parent = st.session_state['edu_parent']

    with st.sidebar:
        st.markdown(f"**{parent['name']}**")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.pop('edu_parent', None)
            st.rerun()

    students = db.get_linked_students(parent['user_id'], 'parent')

    if not students:
        st.warning("연결된 학생이 없습니다. 관리자에게 연동을 요청하세요.")
        return

    student_options = {f"{s['student_name']} (ID:{s['student_id']})": s for s in students}
    sel = st.selectbox("자녀 선택", list(student_options.keys()))
    student = student_options[sel]
    student_id = student['student_id']
    student_name = student['student_name']

    today_checks = db.check_today_logs(student_id)
    gate_banner(today_checks, student_name)

    tab_n, tab_h, tab_d = st.tabs(["내신(교과) 리포트", "내신(학종) 리포트", "일일 학습/상태"])

    with tab_n:
        section_naesin(student_id, student_name)
    with tab_h:
        section_holistic(student_id, student_name)
    with tab_d:
        section_daily(student_id, student_name)


main()
