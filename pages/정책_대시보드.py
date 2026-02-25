import streamlit as st
import datetime
import json
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import naesin_database as db
import naesin_engine as eng

st.set_page_config(page_title="정책 담당자 대시보드", layout="wide", initial_sidebar_state="expanded")

db.init_naesin_database()

REGION_LABELS = {
    'seoul': '서울', 'gyeonggi': '경기', 'incheon': '인천',
    'busan': '부산', 'daejeon': '대전', 'gyeongbuk': '경북',
    'jeonnam': '전남', 'chungnam': '충남',
}


def top_nav():
    st.markdown("""
    <style>
    .nav-bar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;}
    .nav-btn{padding:6px 16px;border-radius:20px;font-size:14px;font-weight:600;text-decoration:none;
             background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;}
    .nav-btn.active{background:#dc2626;color:#fff;border-color:#dc2626;}
    </style>
    <div class="nav-bar">
      <a class="nav-btn active" href="/정책_대시보드" target="_self">정책 대시보드</a>
    </div>
    """, unsafe_allow_html=True)


def login_section():
    if 'edu_policy' in st.session_state and st.session_state['edu_policy']:
        return True
    st.title("정책 담당자 대시보드")
    st.markdown("**로그인** (데모: policy1 / pass1)")
    with st.form("policy_login"):
        login_id = st.text_input("아이디", placeholder="policy1")
        password = st.text_input("비밀번호", type="password", placeholder="pass1")
        if st.form_submit_button("로그인", use_container_width=True):
            user = db.get_edu_user(login_id, password)
            if user and user['role'] == 'policy':
                st.session_state['edu_policy'] = user
                st.rerun()
            elif user:
                st.error("정책 담당자 계정으로 로그인해주세요.")
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    return False


def main():
    top_nav()

    if not login_section():
        return

    policy = st.session_state['edu_policy']

    with st.sidebar:
        st.markdown(f"**{policy['name']}**")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.pop('edu_policy', None)
            st.rerun()

    st.title("정책 담당자 대시보드")

    # ── 필터 ──
    st.markdown("### 필터")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        region_filter = st.selectbox("지역", ['전체'] + list(REGION_LABELS.values()))
        region_code = next((k for k, v in REGION_LABELS.items() if v == region_filter), None)
    with col_f2:
        school_filter = st.selectbox("학교", ['전체 (데모: 정세담고)', '정세담고등학교'])
        school_id = 1 if '정세담' in school_filter else None
    with col_f3:
        period = st.selectbox("기간", ['최근 7일', '최근 30일', '최근 분기(90일)'])
        period_days = {'최근 7일': 7, '최근 30일': 30, '최근 분기(90일)': 90}.get(period, 30)
    with col_f4:
        mode_label = st.selectbox("갱신 모드", ['데모(즉시)', '운영(3일평균)'])
        demo_mode = mode_label == '데모(즉시)'

    if not demo_mode:
        st.info("운영 모드: 변화 지표는 3일 누적 평균 기준으로 제공됩니다.")

    metrics = db.compute_policy_aggregates(
        region_code=region_code,
        school_id=school_id
    )

    if not metrics:
        st.warning("해당 조건의 학생 데이터가 없습니다.")
        return

    # ── KPI 카드 ──
    st.divider()
    st.markdown("### KPI 현황")

    row1 = st.columns(5)
    row1[0].metric("총 학생 수", metrics.get('total_students', 0))
    row1[1].metric("오늘 학습 입력률", f"{metrics.get('log_input_rate_today', 0):.1f}%",
                   delta=None)
    row1[2].metric("오늘 상태 입력률", f"{metrics.get('state_input_rate_today', 0):.1f}%")
    row1[3].metric("활동 참여율", f"{metrics.get('activity_participation_rate', 0):.1f}%")
    row1[4].metric("위험군 비율", f"{metrics.get('risk_rate', 0):.1f}%",
                   delta=f"{metrics.get('risk_student_count', 0)}명",
                   delta_color="inverse")

    row2 = st.columns(5)
    row2[0].metric("내신 평균 등급", f"{metrics.get('naesin_avg') or '-'}")
    row2[1].metric("위험군 학생 수", metrics.get('risk_student_count', 0))
    avg_study = metrics.get('avg_study_minutes_30d', 0)
    row2[2].metric("30일 평균 학습(분)", f"{avg_study:.0f}")
    track_dist = metrics.get('track_preference_distribution', {})
    row2[3].metric("정시 선호", track_dist.get('suneung', 0))
    row2[4].metric("내신/혼합 선호", track_dist.get('naesin', 0) + track_dist.get('mixed', 0))

    # ── 내신 등급 분포 ──
    st.divider()
    st.markdown("### 내신 등급 분포")
    grade_dist = metrics.get('naesin_grade_distribution', {})
    if grade_dist:
        df_dist = pd.DataFrame([
            {'등급': int(k), '학생수': v}
            for k, v in sorted(grade_dist.items(), key=lambda x: int(x[0]))
        ])
        fig = px.bar(df_dist, x='등급', y='학생수', title='내신 등급 분포 (전체)',
                     color='등급', color_continuous_scale='Blues_r',
                     text_auto=True)
        fig.update_layout(showlegend=False, margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("내신 등급 데이터 없음")

    # ── 전형 선호 분포 ──
    st.markdown("### 전형 선호 분포")
    col1, col2 = st.columns(2)
    with col1:
        if track_dist:
            fig2 = px.pie(
                values=list(track_dist.values()),
                names=[{'suneung': '정시', 'naesin': '내신', 'mixed': '혼합'}.get(k, k)
                       for k in track_dist.keys()],
                title='정시 vs 내신 vs 혼합',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            st.plotly_chart(fig2, use_container_width=True)

    with col2:
        unis = db.get_universities()
        degree_counts = {}
        for u in unis:
            degree_counts[u['degree_type']] = degree_counts.get(u['degree_type'], 0) + 1
        fig3 = px.pie(
            values=list(degree_counts.values()),
            names=[{'four_year': '4년제', 'two_year': '2년제'}.get(k, k) for k in degree_counts.keys()],
            title='DB 내 4년제 vs 2년제 대학 비중',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── 위험군 현황 ──
    st.divider()
    st.markdown("### 위험군 현황")
    st.markdown(f"- 위험군 학생 수: **{metrics.get('risk_student_count', 0)}명** ({metrics.get('risk_rate', 0):.1f}%)")
    st.markdown("- 위험군 기준: 최근 7일 스트레스≥4 또는 피로≥4 또는 의욕≤2 (연속 발생)")
    st.caption("위험군 명단은 개인정보 보호 정책에 따라 교사/관리자만 열람 가능합니다.")

    # ── 기간 변화 추세 ──
    st.divider()
    st.markdown(f"### 기간 변화 추세 ({period})")

    students_all = db.get_class_students(None) if not school_id else []
    con = db.get_connection()
    q = "SELECT es.student_id FROM edu_students es WHERE 1=1"
    params = []
    if school_id:
        q += " AND es.school_id=?"
        params.append(school_id)
    rows = con.execute(q, params).fetchall()
    con.close()
    all_student_ids = [r['student_id'] for r in rows]

    if all_student_ids:
        today = datetime.date.today()
        daily_summary = []
        for d in range(period_days, -1, -1):
            dt = (today - datetime.timedelta(days=d)).isoformat()
            con2 = db.get_connection()
            ph = ','.join('?' * len(all_student_ids))
            log_cnt = con2.execute(
                f"SELECT COUNT(*) as c FROM daily_learning_logs WHERE student_id IN ({ph}) AND date=?",
                all_student_ids + [dt]
            ).fetchone()['c']
            avg_min = con2.execute(
                f"SELECT AVG(study_minutes) as a FROM daily_learning_logs WHERE student_id IN ({ph}) AND date=?",
                all_student_ids + [dt]
            ).fetchone()['a'] or 0
            avg_mot = con2.execute(
                f"SELECT AVG(motivation) as a FROM daily_state_checks WHERE student_id IN ({ph}) AND date=?",
                all_student_ids + [dt]
            ).fetchone()['a'] or 0
            con2.close()
            daily_summary.append({
                'date': dt,
                '입력률(%)': round(log_cnt / len(all_student_ids) * 100, 1),
                '평균학습(분)': round(avg_min, 1),
                '평균의욕': round(avg_mot, 2),
            })

        df_trend = pd.DataFrame(daily_summary)
        if not df_trend.empty:
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                fig4 = px.line(df_trend, x='date', y='입력률(%)',
                               title=f'{period} 일별 학습 입력률', markers=False)
                fig4.update_layout(margin=dict(t=30, b=30), height=230)
                st.plotly_chart(fig4, use_container_width=True)
            with col_t2:
                fig5 = px.line(df_trend, x='date', y='평균학습(분)',
                               title=f'{period} 일별 평균 학습시간', markers=False,
                               color_discrete_sequence=['#3b82f6'])
                fig5.update_layout(margin=dict(t=30, b=30), height=230)
                st.plotly_chart(fig5, use_container_width=True)

    # ── 정책 효과 판단 영역 ──
    st.divider()
    st.markdown("### 정책 효과 판단")
    st.markdown("""
    이 영역은 **도입 전/후 비교**를 위한 구조입니다.
    - 매일 집계된 `policy_aggregates_daily` 테이블 기반으로 기간 비교 가능
    - 현재 데모: 30일 누적 집계 저장 기능 포함
    """)

    if st.button("오늘 집계 저장 (정책 기록용)", type="primary"):
        db.save_policy_aggregate(region_code or 'seoul', school_id, metrics)
        st.success("오늘 집계가 저장되었습니다. (정책 보고용 비교 기준 누적)")

    hist = db.get_policy_aggregates_history(region_code, period_days)
    if hist:
        hist_rows = []
        for h in hist:
            m = h.get('metrics', {})
            hist_rows.append({
                '날짜': h['date'],
                '총학생': m.get('total_students', '-'),
                '입력률(%)': m.get('log_input_rate_today', '-'),
                '내신평균': m.get('naesin_avg', '-'),
                '위험군비율(%)': m.get('risk_rate', '-'),
                '평균학습(분)': m.get('avg_study_minutes_30d', '-'),
            })
        df_hist = pd.DataFrame(hist_rows)
        st.dataframe(df_hist, use_container_width=True)

        if len(df_hist) >= 2:
            fig6 = px.line(df_hist, x='날짜', y='입력률(%)', title='입력률 추세 (정책 효과)', markers=True)
            st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("저장된 집계 기록이 없습니다. 위 버튼으로 오늘 집계를 저장해보세요.")

    # ── CSV 내보내기 ──
    st.divider()
    st.markdown("### CSV 내보내기 (정책 보고용)")

    export_type = st.selectbox("내보낼 데이터", [
        '현재 KPI 요약', '학생별 내신 현황', '학생별 활동 현황',
        '일별 집계 이력', '학생별 7일 변화',
    ])

    if st.button("CSV 다운로드", type="primary"):
        if export_type == '현재 KPI 요약':
            df_exp = pd.DataFrame([{
                '항목': k, '값': v
            } for k, v in metrics.items() if not isinstance(v, dict)])
            csv = df_exp.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("다운로드", data=csv.encode('utf-8-sig'),
                               file_name=f"kpi_{datetime.date.today()}.csv",
                               mime="text/csv")

        elif export_type == '학생별 내신 현황':
            con3 = db.get_connection()
            q2 = "SELECT es.student_id FROM edu_students es WHERE 1=1"
            p2 = []
            if school_id:
                q2 += " AND es.school_id=?"
                p2.append(school_id)
            sid_rows = con3.execute(q2, p2).fetchall()
            con3.close()
            all_rows = []
            for r in sid_rows:
                sid2 = r['student_id']
                grades = db.get_grades(sid2)
                for g in grades:
                    all_rows.append({
                        'student_id': sid2,
                        '학년도': g['school_year'], '학기': g['semester'],
                        '과목': g['subject_name'], '등급': g['grade_level_num'],
                    })
            df_exp = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
            csv = df_exp.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("다운로드", data=csv.encode('utf-8-sig'),
                               file_name=f"naesin_{datetime.date.today()}.csv",
                               mime="text/csv")

        elif export_type == '학생별 활동 현황':
            con4 = db.get_connection()
            q3 = "SELECT es.student_id FROM edu_students es WHERE 1=1"
            p3 = []
            if school_id:
                q3 += " AND es.school_id=?"
                p3.append(school_id)
            sid_rows2 = con4.execute(q3, p3).fetchall()
            con4.close()
            all_rows2 = []
            for r in sid_rows2:
                sid3 = r['student_id']
                acts = db.get_activities(sid3)
                for a in acts:
                    all_rows2.append({
                        'student_id': sid3,
                        '유형': a['type_name'], '제목': a['title'],
                        '역할': a['role'], '전공연계': a['major_related'],
                        '시간(h)': a['hours'] or 0,
                    })
            df_exp2 = pd.DataFrame(all_rows2) if all_rows2 else pd.DataFrame()
            csv = df_exp2.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("다운로드", data=csv.encode('utf-8-sig'),
                               file_name=f"activities_{datetime.date.today()}.csv",
                               mime="text/csv")

        elif export_type == '일별 집계 이력':
            hist2 = db.get_policy_aggregates_history(region_code, period_days)
            rows_hist = []
            for h in hist2:
                m = h.get('metrics', {})
                rows_hist.append({'날짜': h['date'], **{k: v for k, v in m.items() if not isinstance(v, dict)}})
            df_hist2 = pd.DataFrame(rows_hist) if rows_hist else pd.DataFrame()
            csv = df_hist2.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("다운로드", data=csv.encode('utf-8-sig'),
                               file_name=f"policy_history_{datetime.date.today()}.csv",
                               mime="text/csv")

        elif export_type == '학생별 7일 변화':
            con5 = db.get_connection()
            q5 = "SELECT es.student_id FROM edu_students es WHERE 1=1"
            p5 = []
            if school_id:
                q5 += " AND es.school_id=?"
                p5.append(school_id)
            sid_rows5 = con5.execute(q5, p5).fetchall()
            con5.close()
            ch_rows = []
            for r in sid_rows5:
                sid5 = r['student_id']
                ch = eng.calculate_changes(sid5, 7)
                burn = eng.detect_burnout_risk(ch)
                ch_rows.append({
                    'student_id': sid5,
                    '7일평균학습(분)': ch.get('study_minutes_avg') or 0,
                    '7일평균의욕': ch.get('motivation_avg') or 0,
                    '7일평균스트레스': ch.get('stress_avg') or 0,
                    '번아웃위험': burn['level'],
                })
            df_ch = pd.DataFrame(ch_rows) if ch_rows else pd.DataFrame()
            csv = df_ch.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("다운로드", data=csv.encode('utf-8-sig'),
                               file_name=f"student_changes_{datetime.date.today()}.csv",
                               mime="text/csv")

    # ── 진로불일치 분석 ──
    st.divider()
    st.markdown("### 진로불일치 분석")
    st.markdown("""
    - **진로불일치 정의**: 전공연계 활동이 0건이면서 내신 등급이 우수(1~3등급)한 학생
    - 이 지표는 학생의 활동이 희망 진로와 연계되지 않을 위험을 나타냅니다.
    """)

    con6 = db.get_connection()
    q6 = "SELECT es.student_id FROM edu_students es WHERE 1=1"
    p6 = []
    if school_id:
        q6 += " AND es.school_id=?"
        p6.append(school_id)
    sids = [r['student_id'] for r in con6.execute(q6, p6).fetchall()]
    con6.close()

    mismatch_count = 0
    for sid in sids:
        avg = db.get_naesin_avg(sid)
        acts = db.get_activities(sid)
        major_related = [a for a in acts if a['major_related']]
        if avg and avg <= 3.0 and not major_related:
            mismatch_count += 1

    total = len(sids)
    st.metric("진로불일치 위험 학생", f"{mismatch_count}명",
              delta=f"{round(mismatch_count/total*100, 1) if total else 0}%",
              delta_color="inverse")
    st.caption("진로불일치 학생에게는 전공연계 활동 참여를 안내해주세요.")


main()
