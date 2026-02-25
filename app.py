import streamlit as st

pg = st.navigation({
    "── 정시 시스템 ──": [
        st.Page("pages/1_정세담소개.py", title="정세담 소개",    icon="📋"),
        st.Page("pages/0_학생.py",        title="학생 (정시)",   icon="🎓"),
        st.Page("pages/2_학부모.py",      title="학부모 (정시)", icon="👨‍👩‍👧"),
        st.Page("pages/3_교사.py",        title="교사 (정시)",   icon="📚"),
        st.Page("pages/9_AI설정.py",      title="AI 설정",       icon="🤖"),
    ],
    "── 내신/수시 시스템 ──": [
        st.Page("pages/학생_내신.py",     title="학생 (내신-교과)",     icon="📝"),
        st.Page("pages/학생_학종.py",     title="학생 (내신-학종)",     icon="🏆"),
        st.Page("pages/학부모_리포트.py", title="학부모 (내신/수시)",   icon="📊"),
        st.Page("pages/교사_대시보드.py", title="교사 (내신/수시)",     icon="🏫"),
        st.Page("pages/정책_대시보드.py", title="정책 담당자",           icon="🏛️"),
        st.Page("pages/관리자_import.py", title="데이터 Import (관리)", icon="⚙️"),
    ],
})

pg.run()
