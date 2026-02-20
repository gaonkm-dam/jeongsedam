import streamlit as st

st.set_page_config(
    page_title="정세담 학습 시스템",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/1_정세담소개.py", title="정세담소개", icon="📋"),
    st.Page("pages/0_학생.py",   title="학생",   icon="🎓"),
    st.Page("pages/2_학부모.py",  title="학부모",  icon="👨‍👩‍👧"),
    st.Page("pages/3_교사.py",   title="교사",   icon="📚"),
])

pg.run()
