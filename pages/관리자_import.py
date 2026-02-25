import streamlit as st
import pandas as pd
import io
import naesin_database as db

st.set_page_config(page_title="관리자 데이터 Import", layout="wide")

db.init_naesin_database()


def login_section():
    if 'admin_ok' in st.session_state and st.session_state['admin_ok']:
        return True
    st.title("관리자 - 데이터 Import")
    st.markdown("**관리자 로그인** (데모: policy1 / pass1)")
    with st.form("admin_login"):
        login_id = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            user = db.get_edu_user(login_id, password)
            if user and user['role'] in ('policy', 'teacher'):
                st.session_state['admin_ok'] = True
                st.rerun()
            else:
                st.error("권한 없음 (policy 또는 teacher 계정 필요)")
    return False


def main():
    if not login_section():
        return

    st.title("관리자 - 대학/학과/컷오프 데이터 Import")
    st.markdown("""
    이 페이지에서 CSV/Excel 파일로 대학, 학과, 전형 컷오프 데이터를 일괄 등록할 수 있습니다.

    **정시 데이터와 완전히 분리**되어 있으며, 내신/수시 추천 엔진에서만 사용됩니다.
    """)

    tab1, tab2, tab3, tab4 = st.tabs(["대학 Import", "학과 Import", "컷오프 Import", "현황 조회"])

    with tab1:
        st.subheader("대학 데이터 Import")
        st.markdown("**CSV 컬럼:** `name`, `degree_type`(four_year/two_year), `region_code`, `homepage_url`")

        with st.expander("CSV 양식 예시 보기"):
            sample_uni = pd.DataFrame([
                {'name': '예시대학교', 'degree_type': 'four_year', 'region_code': 'seoul', 'homepage_url': 'https://example.ac.kr'},
                {'name': '예시전문대학교', 'degree_type': 'two_year', 'region_code': 'gyeonggi', 'homepage_url': 'https://example2.ac.kr'},
            ])
            st.dataframe(sample_uni)
            csv_sample = sample_uni.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("양식 다운로드", data=csv_sample.encode('utf-8-sig'),
                               file_name="university_template.csv", mime="text/csv")

        uploaded = st.file_uploader("CSV 또는 Excel 파일 업로드", type=['csv', 'xlsx'], key='uni_upload')
        if uploaded:
            try:
                if uploaded.name.endswith('.xlsx'):
                    df = pd.read_excel(uploaded)
                else:
                    df = pd.read_csv(uploaded, encoding='utf-8-sig')
                st.dataframe(df.head(10))
                if st.button("대학 데이터 등록", type="primary", key='uni_import'):
                    count = db.import_universities_from_df(df)
                    st.success(f"{count}건 등록 완료")
            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

    with tab2:
        st.subheader("학과 데이터 Import")
        st.markdown("**CSV 컬럼:** `university_name`, `name`, `category`(인문/이공/의약/예체능/기타), `department_url`(선택)")

        with st.expander("CSV 양식 예시 보기"):
            sample_dept = pd.DataFrame([
                {'university_name': '서울대학교', 'name': '컴퓨터공학부', 'category': '이공', 'department_url': ''},
                {'university_name': '연세대학교', 'name': '경영학과', 'category': '기타', 'department_url': ''},
            ])
            st.dataframe(sample_dept)
            csv_sample2 = sample_dept.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("양식 다운로드", data=csv_sample2.encode('utf-8-sig'),
                               file_name="department_template.csv", mime="text/csv")

        uploaded2 = st.file_uploader("CSV 또는 Excel 파일 업로드", type=['csv', 'xlsx'], key='dept_upload')
        if uploaded2:
            try:
                if uploaded2.name.endswith('.xlsx'):
                    df2 = pd.read_excel(uploaded2)
                else:
                    df2 = pd.read_csv(uploaded2, encoding='utf-8-sig')
                st.dataframe(df2.head(10))
                if st.button("학과 데이터 등록", type="primary", key='dept_import'):
                    count2 = db.import_departments_from_df(df2)
                    st.success(f"{count2}건 등록 완료")
            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

    with tab3:
        st.subheader("컷오프 데이터 Import")
        st.markdown("**CSV 컬럼:** `university_name`, `department_name`, `admission_type`(naesin/holistic/suneung), `year`, `naesin_avg`, `notes`")

        with st.expander("CSV 양식 예시 보기"):
            sample_cutoff = pd.DataFrame([
                {'university_name': '서울대학교', 'department_name': '컴퓨터공학부', 'admission_type': 'naesin', 'year': 2024, 'naesin_avg': 1.1, 'notes': '내신 평균 기준'},
                {'university_name': '연세대학교', 'department_name': '경영학과', 'admission_type': 'holistic', 'year': 2024, 'naesin_avg': 70, 'notes': '활동점수 기준'},
            ])
            st.dataframe(sample_cutoff)
            csv_sample3 = sample_cutoff.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("양식 다운로드", data=csv_sample3.encode('utf-8-sig'),
                               file_name="cutoff_template.csv", mime="text/csv")

        uploaded3 = st.file_uploader("CSV 또는 Excel 파일 업로드", type=['csv', 'xlsx'], key='cutoff_upload')
        if uploaded3:
            try:
                if uploaded3.name.endswith('.xlsx'):
                    df3 = pd.read_excel(uploaded3)
                else:
                    df3 = pd.read_csv(uploaded3, encoding='utf-8-sig')
                st.dataframe(df3.head(10))
                if st.button("컷오프 데이터 등록", type="primary", key='cutoff_import'):
                    count3 = db.import_cutoffs_from_df(df3)
                    st.success(f"{count3}건 등록 완료")
            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

    with tab4:
        st.subheader("현황 조회")

        col1, col2 = st.columns(2)
        with col1:
            unis = db.get_universities()
            four_y = [u for u in unis if u['degree_type'] == 'four_year']
            two_y = [u for u in unis if u['degree_type'] == 'two_year']
            st.metric("총 대학 수", len(unis))
            st.metric("4년제", len(four_y))
            st.metric("2년제", len(two_y))

        with col2:
            con = db.get_connection()
            dept_cnt = con.execute("SELECT COUNT(*) as c FROM departments").fetchone()['c']
            cutoff_cnt = con.execute("SELECT COUNT(*) as c FROM admissions_cutoffs").fetchone()['c']
            con.close()
            st.metric("총 학과 수", dept_cnt)
            st.metric("컷오프 데이터", cutoff_cnt)

        st.markdown("#### 대학 목록")
        df_unis = pd.DataFrame([{
            '대학명': u['name'],
            '학위': '4년제' if u['degree_type'] == 'four_year' else '2년제',
            '지역': u['region_code'],
            '홈페이지': u['homepage_url'],
        } for u in unis])
        st.dataframe(df_unis, use_container_width=True)

        import datetime
        csv_unis = df_unis.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "대학 목록 CSV 다운로드",
            data=csv_unis.encode('utf-8-sig'),
            file_name=f"university_list_{datetime.date.today()}.csv",
            mime="text/csv",
            key="dl_unis"
        )


main()
