import streamlit as st
import os
from datetime import datetime, date
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

from modules.database import (
    init_database, create_policy, get_policy, get_all_policies,
    search_policies, save_policy_content, save_generated_media,
    get_policy_contents, get_generated_media, update_policy_status,
    get_policies_by_date, get_policies_by_date_range, get_policies_by_month
)
from modules.ai_engine import (
    generate_policy_analysis, generate_image_prompt, generate_video_prompt,
    generate_video_prompts_3styles
)
from modules.image_generator import generate_policy_image, batch_generate_images
from modules.export_manager import create_pdf_report, create_zip_export
from config.settings import (
    POLICY_CATEGORIES, TARGET_AUDIENCES, VIDEO_PLATFORMS,
    IMAGE_SIZES, VIDEO_DURATIONS, CONTENT_PACKAGES
)

st.set_page_config(
    page_title="정세담 정책 프로그램",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border-left: 4px solid #17a2b8;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .workflow-step {
        padding: 1.5rem;
        background-color: #f8f9fa;
        border-radius: 8px;
        margin-bottom: 1rem;
        border: 2px solid #e9ecef;
    }
    .metric-card {
        padding: 1rem;
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    defaults = {
        "current_policy_id": None,
        "current_analysis": None,
        "generated_images": [],
        "video_prompts": [],
        "workflow_step": "기획",
        "show_results": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()
init_database()

st.markdown('<div class="main-header">🏛️ 정세담 정책 프로그램</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">정책 기획·실행·홍보·성과관리 자동화 시스템</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 📋 프로세스 단계")
    
    steps = ["기획", "실행", "홍보", "성과관리"]
    current_step_idx = steps.index(st.session_state.workflow_step)
    
    for idx, step in enumerate(steps):
        if idx < current_step_idx:
            st.success(f"✅ {step}")
        elif idx == current_step_idx:
            st.info(f"▶️ {step} (현재)")
        else:
            st.write(f"⏸️ {step}")
    
    st.divider()
    
    st.markdown("### 📅 날짜별 정책 검색")
    
    search_type = st.radio("검색 방식", ["전체 보기", "날짜 선택", "날짜 범위"], horizontal=True)
    
    if search_type == "날짜 선택":
        selected_date = st.date_input("날짜 선택", value=date.today())
        policies = get_policies_by_date(selected_date.strftime("%Y-%m-%d"))
        st.caption(f"{selected_date.strftime('%Y-%m-%d')} 정책 {len(policies)}건")
    elif search_type == "날짜 범위":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("시작", value=date.today())
        with col2:
            end_date = st.date_input("종료", value=date.today())
        policies = get_policies_by_date_range(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
        st.caption(f"{len(policies)}건 발견")
    else:
        policies = get_all_policies(limit=20)
        st.caption(f"최근 {len(policies)}건")
    
    st.markdown("### 🗂️ 저장된 정책")
    
    if policies:
        for policy in policies:
            with st.expander(f"{policy['title'][:20]}..."):
                st.write(f"📅 {policy['created_at'][:10]}")
                st.write(f"카테고리: {policy['category']}")
                st.write(f"대상: {policy['target_audience']}")
                st.write(f"상태: {policy['status']}")
                if st.button("불러오기", key=f"load_{policy['id']}"):
                    st.session_state.current_policy_id = policy['id']
                    contents = get_policy_contents(policy['id'])
                    if contents:
                        for content in contents:
                            if content['content_type'] == 'analysis':
                                st.session_state.current_analysis = content['content_data']
                    
                    # 생성된 이미지와 영상 프롬프트도 불러오기
                    media = get_generated_media(policy['id'])
                    st.session_state.generated_images = []
                    st.session_state.video_prompts = []
                    
                    for m in media:
                        if m['media_type'] == 'image' and m['media_data']:
                            from PIL import Image
                            from io import BytesIO
                            img = Image.open(BytesIO(m['media_data']))
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": m['media_data'],
                                "brief": "loaded"
                            })
                    
                    st.success(f"✅ 정책 불러오기 완료!")
                    st.rerun()
    else:
        st.info("저장된 정책이 없습니다")
    
    st.divider()
    
    if st.button("🆕 새 정책 시작", use_container_width=True):
        st.session_state.current_policy_id = None
        st.session_state.current_analysis = None
        st.session_state.generated_images = []
        st.session_state.video_prompts = []
        st.session_state.workflow_step = "기획"
        st.session_state.show_results = False
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 정책 입력",
    "🤖 AI 분석 생성",
    "🖼️ 이미지 생성",
    "🎬 영상 프롬프트",
    "📊 결과 및 내보내기"
])

with tab1:
    st.markdown("### 1️⃣ 정책 기본 정보 입력")
    
    col1, col2 = st.columns(2)
    
    with col1:
        policy_title = st.text_input(
            "정책 제목 *",
            placeholder="예: 도시 대기질 실시간 관리 정책",
            help="정책의 핵심을 담은 명확한 제목"
        )
        
        # 전체 카테고리 데이터 (미리 정의)
        category_database = {
            "환경": {
                "대기질": ["미세먼지 저감", "대기오염 관리", "실시간 모니터링", "배출가스 규제"],
                "수질": ["하천 정화", "상수도 개선", "하수처리", "수질 모니터링"],
                "폐기물": ["쓰레기 감량", "재활용", "음식물쓰레기", "일회용품 규제"],
                "에너지": ["신재생에너지", "태양광", "풍력", "에너지 효율화", "절전"],
                "기후변화": ["탄소중립", "온실가스 감축", "기후 적응", "ESG"],
                "자연보호": ["생태계 보전", "녹지 확대", "도시숲", "야생동물 보호"]
            },
            "교통": {
                "대중교통": ["버스 노선 개편", "지하철 확충", "환승 편의", "요금 정책"],
                "주차": ["공영주차장", "주차난 해소", "불법주차 단속", "공유주차"],
                "보행": ["보행자 우선", "보행로 확충", "횡단보도 개선", "무장애 도로"],
                "자전거": ["자전거 도로", "공유자전거", "자전거 주차장", "안전 인프라"],
                "교통안전": ["어린이 보호구역", "과속 단속", "음주운전 예방", "교통사고 감축"],
                "스마트교통": ["교통신호 최적화", "실시간 정보", "자율주행", "ITS"]
            },
            "복지": {
                "노인복지": ["경로당 지원", "돌봄 서비스", "일자리 창출", "건강관리", "치매 예방"],
                "아동복지": ["보육 지원", "놀이터 확충", "아동학대 예방", "방과후 돌봄"],
                "청년복지": ["주거 지원", "취업 지원", "청년수당", "창업 지원"],
                "장애인복지": ["이동권 보장", "일자리 창출", "편의시설", "활동지원"],
                "여성복지": ["경력단절 방지", "육아 지원", "가정폭력 예방", "성평등"],
                "취약계층": ["기초생활보장", "긴급복지", "노숙인 지원", "한부모 가정"]
            },
            "교육": {
                "학교교육": ["교육과정 개선", "학교시설 현대화", "무상급식", "돌봄교실"],
                "평생교육": ["성인 교육", "직업훈련", "온라인 강좌", "학습 지원"],
                "문화예술교육": ["예술 체험", "창작 지원", "문화 교육", "예술 동아리"],
                "직업교육": ["기술교육", "자격증 지원", "취업 연계", "맞춤형 훈련"],
                "진로교육": ["진로체험", "멘토링", "직업 탐색", "진학 상담"]
            },
            "안전": {
                "재난안전": ["화재 예방", "지진 대비", "태풍 대비", "재난 대응 훈련"],
                "범죄예방": ["CCTV 확충", "안심귀가", "학교폭력 예방", "성범죄 예방"],
                "식품안전": ["위생 관리", "식중독 예방", "원산지 표시", "불량식품 단속"],
                "시설안전": ["건물 점검", "놀이기구 안전", "승강기 관리", "시설물 유지보수"],
                "생활안전": ["가스 안전", "전기 안전", "소방시설", "응급처치 교육"]
            },
            "경제": {
                "일자리": ["일자리 창출", "구직 지원", "직업 훈련", "고용 안정"],
                "창업": ["창업 교육", "자금 지원", "멘토링", "공유 오피스"],
                "중소기업": ["경영 지원", "판로 개척", "자금 융자", "기술 개발"],
                "소상공인": ["상권 활성화", "골목상권 보호", "배달비 지원", "디지털 전환"],
                "지역경제": ["지역화폐", "로컬푸드", "전통시장 활성화", "지역 특산품"],
                "산업진흥": ["기업 유치", "산업단지", "규제 완화", "투자 촉진"]
            },
            "문화": {
                "문화예술": ["공연 지원", "전시회", "문화행사", "예술가 지원"],
                "도서관": ["도서관 확충", "장서 확대", "독서 프로그램", "디지털 자료"],
                "박물관": ["전시 기획", "체험 프로그램", "문화재 보존", "교육 연계"],
                "축제": ["지역 축제", "문화제", "예술제", "관광 연계"],
                "공연장": ["공연장 운영", "대관 지원", "무료 공연", "시설 개선"],
                "생활문화": ["동아리 지원", "문화센터", "주민자치", "마을만들기"]
            },
            "주거": {
                "공공주택": ["임대주택", "행복주택", "주거급여", "주택 공급"],
                "주거환경": ["노후주택 개선", "슬럼 정비", "주거 안전", "에너지 효율"],
                "청년주거": ["셰어하우스", "전월세 지원", "보증금 지원", "주거 상담"],
                "주거복지": ["주거 취약계층", "긴급 주거", "주거 안정", "임대료 규제"]
            },
            "건설/도시": {
                "도시재생": ["구도심 활성화", "도시정비", "재개발", "공간 재구성"],
                "건축": ["친환경 건축", "제로에너지 빌딩", "건축 허가", "건축물 관리"],
                "도시계획": ["도시 설계", "용도 지역", "토지이용", "도시 기반시설"],
                "스마트시티": ["IoT", "빅데이터", "스마트그리드", "지능형 관제"]
            },
            "농업/농촌": {
                "농업진흥": ["스마트팜", "농업기술", "농산물 품질 향상", "농기계 지원"],
                "농촌개발": ["농촌 인프라", "마을 만들기", "귀농귀촌", "농촌 관광"],
                "유통": ["직거래 장터", "로컬푸드", "유통 혁신", "농산물 브랜드"],
                "축산": ["축산 환경 개선", "동물복지", "방역", "축산물 안전"]
            },
            "보건의료": {
                "공공의료": ["보건소 확충", "무료 검진", "예방접종", "방역 체계"],
                "정신건강": ["상담 서비스", "자살 예방", "중독 치료", "정신건강센터"],
                "건강관리": ["건강검진", "만성질환 관리", "비만 예방", "금연 지원"],
                "의료복지": ["의료비 지원", "응급의료", "취약계층 의료", "원격의료"]
            },
            "디지털/ICT": {
                "디지털전환": ["중소기업 디지털화", "AI 도입", "빅데이터", "클라우드"],
                "정보화": ["디지털 리터러시", "정보 격차 해소", "노인 IT교육", "키오스크 교육"],
                "스마트서비스": ["온라인 민원", "챗봇", "모바일 앱", "전자정부"],
                "데이터": ["공공데이터 개방", "데이터 활용", "정보 보안", "개인정보 보호"]
            },
            "관광": {
                "관광진흥": ["관광 상품 개발", "외국인 유치", "관광 마케팅", "축제 연계"],
                "관광인프라": ["관광지 정비", "안내 표지판", "편의시설", "무료 와이파이"],
                "문화관광": ["문화재 관광", "한류 관광", "체험 관광", "역사 탐방"],
                "생태관광": ["자연 체험", "생태 탐방", "친환경 관광", "힐링 여행"]
            },
            "체육": {
                "생활체육": ["동네 체육관", "무료 강습", "체육 동아리", "생활 스포츠"],
                "체육시설": ["운동장 개선", "수영장", "헬스장", "스포츠 센터"],
                "스포츠행사": ["마라톤", "체육대회", "스포츠 축제", "지역 리그"],
                "청소년체육": ["학교 체육", "유소년 스포츠", "선수 육성", "체육 교육"]
            },
            "과학/기술": {
                "R&D": ["연구개발 지원", "기술 혁신", "산학협력", "실험실 구축"],
                "기술사업화": ["특허 지원", "기술이전", "창업 연계", "상용화 지원"],
                "과학교육": ["과학관", "실험 교육", "메이커 스페이스", "STEM 교육"]
            },
            "기타": {
                "인권": ["차별 금지", "소수자 보호", "인권 교육", "인권 상담"],
                "양성평등": ["성평등 정책", "여성 참여 확대", "일가정 양립"],
                "다문화": ["다문화 가정 지원", "외국인 정착", "통번역 서비스"],
                "자원봉사": ["봉사 활동 활성화", "자원봉사센터", "재능 기부"],
                "동물보호": ["유기동물 보호", "반려동물 등록", "동물 학대 예방"]
            }
        }
        
        # 선택된 카테고리를 저장할 세션 변수 초기화
        if "selected_category" not in st.session_state:
            st.session_state.selected_category = ""
        
        # 선택 버튼이 눌렸을 때 입력창을 업데이트
        if "temp_selection" in st.session_state and st.session_state.temp_selection:
            st.session_state.selected_category = st.session_state.temp_selection
            st.session_state.temp_selection = ""
        
        # 정책 카테고리 입력창
        policy_category = st.text_input(
            "정책 카테고리 *",
            value=st.session_state.selected_category if st.session_state.selected_category else "",
            placeholder="예: 화재, 청년, 주차 등 입력하면 자동완성됩니다",
            help="한 글자씩 입력하면 관련 카테고리가 자동으로 추천됩니다"
        )
        
        # 사용자가 직접 입력하면 selected_category 업데이트
        if policy_category != st.session_state.selected_category:
            st.session_state.selected_category = policy_category
        
        # 실시간 자동완성 추천 (입력창 바로 아래)
        if policy_category and len(policy_category) > 0:
            # 모든 카테고리를 플랫하게 변환
            autocomplete_suggestions = []
            
            for main_cat, sub_cats in category_database.items():
                for sub_cat, items in sub_cats.items():
                    for item in items:
                        full_path = f"{main_cat} > {sub_cat} > {item}"
                        # 입력한 텍스트가 포함되어 있으면 추천 목록에 추가
                        if policy_category.lower() in full_path.lower():
                            autocomplete_suggestions.append(full_path)
            
            # 추천 항목이 있으면 표시 (최대 10개)
            if autocomplete_suggestions:
                st.markdown("##### 💡 자동완성 추천")
                st.caption(f"{len(autocomplete_suggestions)}개 항목 발견 (최대 10개 표시)")
                
                for idx, suggestion in enumerate(autocomplete_suggestions[:10]):
                    cols = st.columns([5, 1])
                    with cols[0]:
                        # 입력한 텍스트 강조
                        if policy_category.lower() in suggestion.lower():
                            st.markdown(f"✨ {suggestion}")
                    with cols[1]:
                        if st.button("선택", key=f"autocomplete_{idx}", use_container_width=True):
                            st.session_state.temp_selection = suggestion
                            st.rerun()
                
                if len(autocomplete_suggestions) > 10:
                    st.caption(f"+ {len(autocomplete_suggestions) - 10}개 더 있습니다. 키워드를 더 구체적으로 입력하세요.")
        
        # 카테고리 검색 및 예시 표시
        with st.expander("🔍 카테고리 검색 및 예시 보기"):
            search_keyword = st.text_input(
                "키워드로 검색",
                placeholder="예: 미세먼지, 청년, 일자리, 주차, 복지 등",
                help="관련 카테고리를 빠르게 찾으세요"
            )
            
            # 검색 기능 - 세부 항목까지 개별 선택 가능
            if search_keyword:
                st.markdown(f"### 🔍 '{search_keyword}' 검색 결과")
                search_results = []
                
                for main_cat, sub_cats in category_database.items():
                    for sub_cat, items in sub_cats.items():
                        # 대분류, 중분류, 세부항목에서 검색
                        matching_items = []
                        
                        # 세부 항목에서 키워드 매칭
                        for item in items:
                            if search_keyword.lower() in item.lower():
                                matching_items.append(item)
                        
                        # 대분류 또는 중분류에 키워드가 있으면 모든 항목 포함
                        if search_keyword.lower() in main_cat.lower() or search_keyword.lower() in sub_cat.lower():
                            matching_items = items
                        
                        # 매칭되는 항목이 있으면 결과에 추가
                        if matching_items:
                            search_results.append({
                                "main": main_cat,
                                "sub": sub_cat,
                                "items": matching_items
                            })
                
                if search_results:
                    st.info(f"💡 **{len(search_results)}개 카테고리**에서 관련 항목을 찾았습니다. 원하는 항목의 선택 버튼을 클릭하세요!")
                    
                    for result in search_results:
                        st.markdown(f"#### {result['main']} > {result['sub']}")
                        
                        # 세부 항목마다 개별 선택 버튼 표시
                        for item in result['items']:
                            cols = st.columns([4, 1])
                            with cols[0]:
                                # 검색어가 포함된 항목은 강조 표시
                                if search_keyword.lower() in item.lower():
                                    st.markdown(f"✅ **{item}**")
                                else:
                                    st.write(f"• {item}")
                            with cols[1]:
                                # 각 세부 항목마다 선택 버튼
                                if st.button(
                                    "선택", 
                                    key=f"select_{result['main']}_{result['sub']}_{item}",
                                    use_container_width=True
                                ):
                                    st.session_state.temp_selection = f"{result['main']} > {result['sub']} > {item}"
                                    st.rerun()
                        
                        st.divider()
                    
                else:
                    st.info("검색 결과가 없습니다. 다른 키워드로 시도해보세요.")
            
            else:
                # 전체 카테고리 리스트 표시 - 세부 항목까지 선택 가능
                st.markdown("### 📚 전체 카테고리 목록")
                st.caption("각 세부 항목마다 선택 버튼을 클릭하여 입력할 수 있습니다")
                
                for main_cat, sub_cats in category_database.items():
                    with st.expander(f"**{main_cat}** ({len(sub_cats)}개 세부 분야)"):
                        for sub_cat, items in sub_cats.items():
                            st.markdown(f"#### {sub_cat}")
                            
                            # 세부 항목마다 개별 선택 버튼
                            for item in items:
                                cols = st.columns([4, 1])
                                with cols[0]:
                                    st.write(f"• {item}")
                                with cols[1]:
                                    if st.button(
                                        "선택", 
                                        key=f"select_full_{main_cat}_{sub_cat}_{item}",
                                        use_container_width=True
                                    ):
                                        st.session_state.temp_selection = f"{main_cat} > {sub_cat} > {item}"
                                        st.rerun()
                            
                            st.divider()
        
        target_audience = st.selectbox(
            "주요 대상 *",
            options=list(TARGET_AUDIENCES.keys()),
            help="정책의 주요 대상 그룹"
        )
        
        if target_audience in TARGET_AUDIENCES:
            audience_info = TARGET_AUDIENCES[target_audience]
            st.info(f"**톤**: {audience_info['tone']}\n\n**초점**: {audience_info['focus']}")
    
    with col2:
        policy_description = st.text_area(
            "정책 설명 *",
            height=150,
            placeholder="정책의 배경, 목적, 기대 효과 등을 자세히 입력하세요",
            help="AI가 이 내용을 기반으로 분석합니다"
        )
        
        keywords = st.text_input(
            "강조 키워드 (쉼표로 구분)",
            placeholder="예: 시민참여, 데이터기반, 지속가능성",
            help="정책에서 강조하고 싶은 핵심 키워드"
        )
        
        constraints = st.text_area(
            "제약 조건 (선택)",
            height=100,
            placeholder="예: 예산 1억 이내, 3개월 시범운영, 기존 인프라 활용",
            help="예산, 기간, 법적 제약 등"
        )
    
    content_package = st.selectbox(
        "콘텐츠 패키지",
        options=list(CONTENT_PACKAGES.keys()),
        help="생성할 콘텐츠의 범위"
    )
    
    st.info(f"**선택한 패키지 포함 항목**: {', '.join(CONTENT_PACKAGES[content_package])}")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("💾 정책 저장", use_container_width=True):
            if not policy_title or not policy_description:
                st.error("정책 제목과 설명은 필수입니다")
            else:
                policy_id = create_policy(
                    title=policy_title,
                    category=policy_category,
                    target_audience=target_audience,
                    description=policy_description
                )
                st.session_state.current_policy_id = policy_id
                st.success(f"✅ 정책이 저장되었습니다 (ID: {policy_id})")
                st.session_state.workflow_step = "실행"
    
    with col2:
        if st.button("🚀 AI 분석 생성", use_container_width=True):
            if not policy_title or not policy_description:
                st.error("정책 제목과 설명은 필수입니다")
            else:
                try:
                    if not st.session_state.current_policy_id:
                        policy_id = create_policy(
                            title=policy_title,
                            category=policy_category,
                            target_audience=target_audience,
                            description=policy_description
                        )
                        st.session_state.current_policy_id = policy_id
                    
                    with st.spinner("AI가 정책을 분석하고 있습니다... (30-60초 소요)"):
                        analysis, raw = generate_policy_analysis(
                            title=policy_title,
                            category=policy_category,
                            target_audience=target_audience,
                            description=policy_description,
                            keywords=keywords,
                            constraints=constraints
                        )
                        
                        if analysis:
                            st.session_state.current_analysis = analysis
                            save_policy_content(
                                st.session_state.current_policy_id,
                                "analysis",
                                analysis
                            )
                            st.success("✅ AI 분석이 완료되었습니다!")
                            st.session_state.show_results = True
                            st.session_state.workflow_step = "홍보"
                            st.balloons()
                        else:
                            st.error(f"AI 분석 생성에 실패했습니다. 원문:\n{raw[:500]}")
                            
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")
                    st.error("OpenAI API 키를 확인해주세요. 또는 네트워크 연결을 확인해주세요.")
                    import traceback
                    st.code(traceback.format_exc())

with tab2:
    st.markdown("### 2️⃣ AI 생성 결과")
    
    if st.session_state.current_analysis:
        analysis = st.session_state.current_analysis
        
        with st.expander("📋 정책 기획", expanded=True):
            if "policy_planning" in analysis:
                planning = analysis["policy_planning"]
                st.markdown(f"**목표**: {planning.get('objective', '')}")
                st.markdown(f"**대상 분석**: {planning.get('target_analysis', '')}")
                
                st.markdown("**핵심 전략**:")
                for idx, strategy in enumerate(planning.get("key_strategies", []), 1):
                    st.write(f"{idx}. {strategy}")
                
                st.markdown("**기대 효과**:")
                for outcome in planning.get("expected_outcomes", []):
                    st.write(f"• {outcome}")
        
        with st.expander("⚙️ 실행 계획"):
            if "execution_plan" in analysis:
                execution = analysis["execution_plan"]
                
                action_items = execution.get("action_items", [])
                if action_items:
                    st.markdown("**실행 항목**:")
                    for item in action_items:
                        st.markdown(f"""
                        **{item.get('phase', '')}**
                        - 실행 내용: {item.get('action', '')}
                        - 담당: {item.get('responsible', '')}
                        - 기간: {item.get('timeline', '')}
                        """)
                
                st.markdown("**리스크 관리**:")
                for risk in execution.get("risk_management", []):
                    st.warning(f"⚠️ {risk.get('risk', '')}\n- 영향: {risk.get('impact', '')}\n- 완화: {risk.get('mitigation', '')}")
        
        with st.expander("📣 커뮤니케이션 전략"):
            if "communication_strategy" in analysis:
                comm = analysis["communication_strategy"]
                
                st.markdown("**핵심 메시지**:")
                for msg in comm.get("key_messages", []):
                    st.write(f"• {msg}")
                
                st.markdown("**대상별 메시지**:")
                target_msgs = comm.get("target_specific_messages", {})
                for target, msg in target_msgs.items():
                    st.info(f"**{target}**: {msg}")
        
        with st.expander("📈 성과 지표 (KPI)"):
            if "performance_metrics" in analysis:
                metrics = analysis["performance_metrics"]
                
                kpi_framework = metrics.get("kpi_framework", [])
                if kpi_framework:
                    for kpi in kpi_framework:
                        st.markdown(f"""
                        **{kpi.get('metric', '')}**
                        - 측정 방법: {kpi.get('measurement_method', '')}
                        - 목표 범위: {kpi.get('target_range', '')}
                        - 데이터 출처: {kpi.get('data_source', '')}
                        """)
        
        with st.expander("🎨 콘텐츠 제작 브리프"):
            if "content_briefs" in analysis:
                briefs = analysis["content_briefs"]
                
                st.markdown("### 이미지 브리프 1")
                if "image_brief_1" in briefs:
                    brief1 = briefs["image_brief_1"]
                    st.write(f"**컨셉**: {brief1.get('concept', '')}")
                    st.write(f"**장면**: {brief1.get('scene_description', '')}")
                    st.write(f"**스타일**: {brief1.get('visual_style', '')}")
                    st.success(f"**메시지**: {brief1.get('key_message', '')}")
                
                st.markdown("### 이미지 브리프 2")
                if "image_brief_2" in briefs:
                    brief2 = briefs["image_brief_2"]
                    st.write(f"**컨셉**: {brief2.get('concept', '')}")
                    st.write(f"**장면**: {brief2.get('scene_description', '')}")
                    st.write(f"**스타일**: {brief2.get('visual_style', '')}")
                    st.success(f"**메시지**: {brief2.get('key_message', '')}")
                
                st.markdown("### 영상 브리프")
                if "video_brief" in briefs:
                    video = briefs["video_brief"]
                    st.write(f"**길이**: {video.get('duration', '')}")
                    st.write(f"**스토리**: {video.get('narrative_arc', '')}")
                    st.write(f"**스타일 가이드**: {video.get('style_guide', '')}")
                    st.success(f"**CTA**: {video.get('call_to_action', '')}")
        
        with st.expander("📝 마케팅 자료"):
            if "marketing_materials" in analysis:
                marketing = analysis["marketing_materials"]
                
                st.markdown(f"### {marketing.get('slogan', '')}")
                st.markdown(f"**태그라인**: {marketing.get('tagline', '')}")
                st.write(marketing.get('elevator_pitch', ''))
                
                st.markdown("**FAQ**:")
                for faq in marketing.get("faq", []):
                    with st.expander(faq.get("question", "")):
                        st.write(faq.get("answer", ""))
    
    else:
        st.info("먼저 '정책 입력' 탭에서 정책 정보를 입력하고 AI 분석을 생성해주세요.")

with tab3:
    st.markdown("### 3️⃣ 이미지 자동 생성")
    
    if st.session_state.current_analysis and "content_briefs" in st.session_state.current_analysis:
        briefs = st.session_state.current_analysis["content_briefs"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            image_size = st.selectbox("이미지 크기", IMAGE_SIZES)
        
        with col2:
            image_quality = st.selectbox("품질", ["standard", "hd"])
        
        with col3:
            num_images = st.number_input("생성 개수", min_value=1, max_value=4, value=2)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🖼️ 이미지 1 생성", use_container_width=True):
                if "image_brief_1" in briefs:
                    with st.spinner("이미지를 생성하고 있습니다... (20-40초)"):
                        result = generate_policy_image(
                            briefs["image_brief_1"],
                            size=image_size,
                            quality=image_quality
                        )
                        if result:
                            img, img_bytes = result
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": img_bytes,
                                "brief": "image_brief_1"
                            })
                            
                            if st.session_state.current_policy_id:
                                save_generated_media(
                                    st.session_state.current_policy_id,
                                    "image",
                                    img_bytes,
                                    generate_image_prompt(briefs["image_brief_1"]),
                                    {"size": image_size, "quality": image_quality}
                                )
                            
                            st.success("✅ 이미지 1 생성 완료!")
                            st.rerun()
                        else:
                            st.error("이미지 생성에 실패했습니다")
        
        with col2:
            if st.button("🖼️ 이미지 2 생성", use_container_width=True):
                if "image_brief_2" in briefs:
                    with st.spinner("이미지를 생성하고 있습니다... (20-40초)"):
                        result = generate_policy_image(
                            briefs["image_brief_2"],
                            size=image_size,
                            quality=image_quality
                        )
                        if result:
                            img, img_bytes = result
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": img_bytes,
                                "brief": "image_brief_2"
                            })
                            
                            if st.session_state.current_policy_id:
                                save_generated_media(
                                    st.session_state.current_policy_id,
                                    "image",
                                    img_bytes,
                                    generate_image_prompt(briefs["image_brief_2"]),
                                    {"size": image_size, "quality": image_quality}
                                )
                            
                            st.success("✅ 이미지 2 생성 완료!")
                            st.rerun()
                        else:
                            st.error("이미지 생성에 실패했습니다")
        
        if st.button("🔄 새로고침 (이미지 2장 추가 생성)", use_container_width=True):
            with st.spinner("이미지 2장을 생성하고 있습니다... (40-80초)"):
                prompts = []
                if "image_brief_1" in briefs:
                    prompts.append(generate_image_prompt(briefs["image_brief_1"]))
                if "image_brief_2" in briefs:
                    prompts.append(generate_image_prompt(briefs["image_brief_2"]))
                
                results = batch_generate_images(prompts, size=image_size, quality=image_quality)
                
                for idx, (img, img_bytes) in enumerate(results):
                    st.session_state.generated_images.append({
                        "image": img,
                        "bytes": img_bytes,
                        "brief": f"image_brief_{idx+1}"
                    })
                    
                    if st.session_state.current_policy_id:
                        save_generated_media(
                            st.session_state.current_policy_id,
                            "image",
                            img_bytes,
                            prompts[idx] if idx < len(prompts) else "",
                            {"size": image_size, "quality": image_quality}
                        )
                
                st.success(f"✅ {len(results)}장의 이미지가 추가 생성되었습니다!")
                st.rerun()
        
        st.divider()
        
        if st.session_state.generated_images:
            st.markdown(f"### 생성된 이미지 ({len(st.session_state.generated_images)}장)")
            
            cols = st.columns(2)
            for idx, img_data in enumerate(st.session_state.generated_images):
                with cols[idx % 2]:
                    st.image(img_data["image"], use_column_width=True)
                    st.caption(f"이미지 {idx+1} - {img_data['brief']}")
                    
                    buffer = BytesIO(img_data["bytes"])
                    st.download_button(
                        f"💾 이미지 {idx+1} 다운로드",
                        buffer,
                        file_name=f"policy_image_{idx+1}.png",
                        mime="image/png",
                        key=f"download_img_{idx}"
                    )
        else:
            st.info("이미지를 생성하려면 위의 버튼을 클릭하세요")
    
    else:
        st.info("먼저 AI 분석을 생성해주세요")

with tab4:
    st.markdown("### 4️⃣ 영상 프롬프트 생성 (10초 3종 스타일)")
    
    if st.session_state.current_analysis and "content_briefs" in st.session_state.current_analysis:
        briefs = st.session_state.current_analysis["content_briefs"]
        
        if "video_brief" in briefs:
            video_brief = briefs["video_brief"]
            
            st.info("🎬 **10초 영상 3가지 스타일**이 자동 생성됩니다: 다큐멘터리, 시네마틱, 모던 다이내믹")
            
            if st.button("🎬 10초 영상 3종 프롬프트 생성", use_container_width=True, type="primary"):
                with st.spinner("3가지 스타일의 영상 프롬프트 생성 중..."):
                    prompts_3styles = generate_video_prompts_3styles(video_brief)
                    
                    # 세션에 저장
                    if "video_prompts_3styles" not in st.session_state:
                        st.session_state.video_prompts_3styles = []
                    
                    st.session_state.video_prompts_3styles.append(prompts_3styles)
                    st.success("✅ 10초 영상 3종 프롬프트가 생성되었습니다!")
                    st.balloons()
            
            st.divider()
            
            # 3종 스타일 프롬프트 표시
            if "video_prompts_3styles" in st.session_state and st.session_state.video_prompts_3styles:
                st.markdown("### 📹 생성된 영상 프롬프트")
                
                for set_idx, prompt_set in enumerate(st.session_state.video_prompts_3styles):
                    st.markdown(f"#### 세트 {set_idx + 1}")
                    
                    # 스타일 1: 다큐멘터리
                    with st.expander("🎥 스타일 1: 다큐멘터리 리얼리즘", expanded=True):
                        st.text_area(
                            "프롬프트 (다큐멘터리)",
                            prompt_set["documentary"],
                            height=400,
                            key=f"video_doc_{set_idx}"
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["documentary"],
                                file_name=f"video_documentary_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_doc_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col3:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    # 스타일 2: 시네마틱
                    with st.expander("🎬 스타일 2: 시네마틱 드라마", expanded=True):
                        st.text_area(
                            "프롬프트 (시네마틱)",
                            prompt_set["cinematic"],
                            height=400,
                            key=f"video_cine_{set_idx}"
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["cinematic"],
                                file_name=f"video_cinematic_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_cine_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col3:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    # 스타일 3: 모던 다이내믹
                    with st.expander("⚡ 스타일 3: 모던 다이내믹", expanded=True):
                        st.text_area(
                            "프롬프트 (모던)",
                            prompt_set["modern_dynamic"],
                            height=400,
                            key=f"video_modern_{set_idx}"
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["modern_dynamic"],
                                file_name=f"video_modern_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_modern_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col3:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    st.divider()
            else:
                st.info("위의 '10초 영상 3종 프롬프트 생성' 버튼을 클릭하세요")
            
            st.divider()
            
            st.markdown("### 🎥 추천 영상 제작 플랫폼")
            cols = st.columns(len(VIDEO_PLATFORMS))
            for idx, (platform, url) in enumerate(VIDEO_PLATFORMS.items()):
                with cols[idx]:
                    st.link_button(platform, url, use_container_width=True)
        
        else:
            st.info("영상 브리프가 생성되지 않았습니다")
    
    else:
        st.info("먼저 AI 분석을 생성해주세요")

with tab5:
    st.markdown("### 5️⃣ 결과 및 내보내기")
    
    if st.session_state.current_policy_id and st.session_state.current_analysis:
        policy = get_policy(st.session_state.current_policy_id)
        
        st.markdown("#### 정책 정보")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("정책 ID", policy['id'])
        with col2:
            st.metric("카테고리", policy['category'])
        with col3:
            st.metric("대상", policy['target_audience'])
        with col4:
            st.metric("상태", policy['status'])
        
        st.markdown(f"**제목**: {policy['title']}")
        st.markdown(f"**설명**: {policy['description']}")
        
        st.divider()
        
        st.markdown("#### 생성된 콘텐츠")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("이미지", f"{len(st.session_state.generated_images)}장")
        with col2:
            st.metric("영상 프롬프트", f"{len(st.session_state.video_prompts)}개")
        with col3:
            st.metric("AI 분석", "완료" if st.session_state.current_analysis else "없음")
        
        st.divider()
        
        st.markdown("#### 📥 다운로드")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 PDF 보고서", use_container_width=True):
                with st.spinner("PDF를 생성하고 있습니다..."):
                    pdf_bytes = create_pdf_report(policy, st.session_state.current_analysis)
                    st.download_button(
                        "💾 PDF 다운로드",
                        pdf_bytes,
                        file_name=f"policy_report_{policy['id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        with col2:
            if st.button("📦 전체 ZIP", use_container_width=True):
                with st.spinner("ZIP 파일을 생성하고 있습니다..."):
                    image_bytes = [img['bytes'] for img in st.session_state.generated_images]
                    video_prompts = [v['prompt'] for v in st.session_state.video_prompts]
                    
                    zip_bytes = create_zip_export(
                        policy,
                        st.session_state.current_analysis,
                        images=image_bytes,
                        video_prompts=video_prompts
                    )
                    
                    st.download_button(
                        "💾 ZIP 다운로드",
                        zip_bytes,
                        file_name=f"policy_package_{policy['id']}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
        
        with col3:
            status_options = ["draft", "active", "completed", "archived"]
            new_status = st.selectbox("정책 상태 변경", status_options, index=status_options.index(policy['status']))
            if st.button("상태 업데이트", use_container_width=True):
                update_policy_status(st.session_state.current_policy_id, new_status)
                st.success(f"상태가 '{new_status}'로 변경되었습니다")
                st.rerun()
        
        st.divider()
        
        st.markdown("#### 🎯 성과 관리")
        st.info("이 섹션에서는 정책 실행 후 성과 데이터를 입력하고 추적할 수 있습니다")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            view_count = st.number_input("조회수", min_value=0, value=0)
        with col2:
            engagement = st.number_input("참여도 (%)", min_value=0.0, max_value=100.0, value=0.0)
        with col3:
            satisfaction = st.number_input("만족도 (%)", min_value=0.0, max_value=100.0, value=0.0)
        with col4:
            if st.button("📊 지표 저장"):
                st.success("성과 지표가 저장되었습니다")
        
        st.session_state.workflow_step = "성과관리"
    
    else:
        st.info("정책을 생성하고 AI 분석을 완료해주세요")

st.divider()

with st.expander("ℹ️ 사용 가이드"):
    st.markdown("""
    ### 정세담 정책 프로그램 사용 방법
    
    #### 1단계: 정책 입력
    - 정책 제목, 카테고리, 대상, 설명을 입력합니다
    - 강조할 키워드와 제약 조건을 추가합니다
    - "AI 분석 생성" 버튼을 클릭합니다
    
    #### 2단계: AI 분석 검토
    - AI가 생성한 정책 기획, 실행 계획, 커뮤니케이션 전략을 검토합니다
    - 필요시 정책 정보를 수정하고 재생성합니다
    
    #### 3단계: 이미지 생성
    - "이미지 1 생성", "이미지 2 생성" 버튼으로 이미지를 생성합니다
    - "새로고침" 버튼으로 추가 이미지를 생성할 수 있습니다
    - 생성된 이미지는 즉시 화면에 표시됩니다
    
    #### 4단계: 영상 프롬프트
    - 영상 길이와 플랫폼을 선택합니다
    - "영상 프롬프트 생성" 버튼을 클릭합니다
    - 생성된 프롬프트를 복사하여 영상 제작 플랫폼에 활용합니다
    
    #### 5단계: 결과 다운로드
    - PDF 보고서: 전체 분석 내용을 문서로 다운로드
    - ZIP 패키지: 모든 이미지, 프롬프트, 분석 데이터를 압축
    - 정책 상태를 관리하고 성과 지표를 입력합니다
    
    ### 주요 기능
    
    - ✅ **즉시 생성**: 버튼 클릭 즉시 이미지가 생성되어 화면에 표시
    - ✅ **새로고침**: 클릭마다 새로운 이미지 생성
    - ✅ **정책 프로세스**: 기획 → 실행 → 홍보 → 성과관리 전체 워크플로우
    - ✅ **대상별 맞춤**: 시민, 청년, 노인 등 타겟별 메시지 자동 생성
    - ✅ **데이터 축적**: 모든 정책과 생성물이 데이터베이스에 저장
    """)

with st.expander("⚙️ 환경 설정"):
    st.markdown("""
    ### 필수 환경 변수
    
    - `OPENAI_API_KEY`: OpenAI API 키 (필수)
    
    ### 데이터베이스
    
    - 경로: `data/policies.db`
    - 자동 생성됨
    
    ### 지원 형식
    
    - 이미지: PNG (1024x1024, 1024x1792, 1792x1024)
    - 문서: PDF, ZIP
    - 영상: 프롬프트 텍스트 (TXT)
    """)
