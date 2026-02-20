import os
import random
import streamlit as st
from openai import OpenAI
import config

client = None

def _openai_enabled() -> bool:
    """session_state 토글 우선, 없으면 config.USE_OPENAI 기본값 사용."""
    if "student_use_openai" in st.session_state:
        return bool(st.session_state["student_use_openai"])
    return config.USE_OPENAI

def init_openai():
    global client
    api_key = os.environ.get('OPENAI_API_KEY')
    # Streamlit secrets (클라우드 배포용)
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("OPENAI_API_KEY")
        except Exception:
            pass
    if not api_key:
        for filename in ['.env', 'api_key.txt']:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                filepath = os.path.join(base_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY='):
                            api_key = line.strip().split('=', 1)[1]
                            break
                    if api_key:
                        break
            except:
                pass

    if api_key:
        client = OpenAI(api_key=api_key)

    return client is not None

def generate_questions(subject, grade, page_start, page_end, difficulty, exam_type, num_questions):
    if not _openai_enabled():
        mock_questions = []
        for i in range(num_questions):
            mock_questions.append({
                'question_text': f'[{subject} {grade} {difficulty}] 예시 문제 {i+1}입니다. (페이지 {page_start}-{page_end}, {exam_type})',
                'answer': f'{i+1}',
                'explanation': f'{subject} {grade} 학습 내용에 대한 예시 해설입니다. AI를 활성화하면 실제 해설이 생성됩니다.'
            })
        return mock_questions
    
    if not client:
        return None
    
    difficulty_map = {
        '쉬움': '쉬운',
        '보통': '중간',
        '어려움': '어려운'
    }
    
    prompt = f"""
당신은 {subject} 교육 전문가입니다.

다음 조건에 맞는 문제를 정확히 {num_questions}개 생성해주세요:
- 과목: {subject}
- 학년: {grade}
- 교과서 페이지: {page_start}p ~ {page_end}p
- 난이도: {difficulty_map.get(difficulty, difficulty)}
- 시험 유형: {exam_type}

문제는 객관식, 주관식, 서술형을 혼합하여 출제하세요.

각 문제는 반드시 다음 형식을 따라주세요:

문제 1:
[문제 내용]
정답: [정답]
해설: [해설]

문제 2:
[문제 내용]
정답: [정답]
해설: [해설]

...

정확히 {num_questions}개의 문제를 생성해주세요.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 교육 문제 출제 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        
        content = response.choices[0].message.content
        questions = parse_questions(content)
        
        return questions[:num_questions]
    
    except Exception as e:
        print(f"OpenAI API 오류: {e}")
        return None

def parse_questions(content):
    import re
    questions = []
    lines = content.strip().split('\n')

    current_question = None
    current_text = []

    # "문제 N" 또는 "**문제 N**" 또는 "문제N:" 등 다양한 형식 인식
    question_header = re.compile(r'^\**문제\s*\d+\**[:\.]?\s*$', re.IGNORECASE)

    def flush():
        nonlocal current_text
        if current_question is not None:
            txt = '\n'.join(t for t in current_text if t).strip()
            if txt:
                current_question['question_text'] = txt
            questions.append(current_question)
        current_text = []

    for line in lines:
        clean = line.strip()
        # 마크다운 볼드 제거
        clean_no_md = re.sub(r'\*+', '', clean).strip()

        # 문제 헤더 감지: "문제 N" / "문제 N:" / "**문제 N**" 등
        is_header = bool(question_header.match(clean_no_md)) or (
            re.match(r'^문제\s*\d+', clean_no_md) and (':' in clean or clean_no_md == re.match(r'^문제\s*\d+', clean_no_md).group())
        )

        if is_header:
            if current_question is not None:
                flush()
            current_question = {'question_text': '', 'answer': '', 'explanation': ''}
            current_text = []

        elif re.match(r'^정답\s*:', clean_no_md):
            if current_question is not None:
                txt = '\n'.join(t for t in current_text if t).strip()
                if txt:
                    current_question['question_text'] = txt
                current_text = []
                current_question['answer'] = re.sub(r'^정답\s*:', '', clean_no_md).strip()

        elif re.match(r'^해설\s*:', clean_no_md):
            if current_question is not None:
                exp = re.sub(r'^해설\s*:', '', clean_no_md).strip()
                current_question['explanation'] = exp

        else:
            if current_question is not None:
                if not current_question.get('answer'):
                    current_text.append(clean)
                elif not current_question.get('explanation') and clean:
                    current_question['explanation'] = (current_question.get('explanation', '') + ' ' + clean).strip()

    if current_question is not None:
        txt = '\n'.join(t for t in current_text if t).strip()
        if txt and not current_question.get('question_text'):
            current_question['question_text'] = txt
        questions.append(current_question)

    return questions

def search_content(subject, search_term):
    if not _openai_enabled():
        return f"[{subject}] '{search_term}'에 대한 테스트 설명입니다. OpenAI OFF 상태에서는 Mock 데이터가 표시됩니다."
    
    if not client:
        return "OpenAI API 키가 설정되지 않았습니다."
    
    subject_context = {
        '영어': '영어 단어 또는 문법',
        '수학': '수학 공식',
        '국어': '국어 단어 또는 표현',
        '한자': '한자의 뜻과 음',
        '과학': '과학 개념',
        '사회': '사회 용어',
        '역사': '역사 용어'
    }
    
    context = subject_context.get(subject, '용어')
    
    prompt = f"{subject} 과목에서 '{search_term}'에 대해 학생이 이해하기 쉽게 간단명료하게 설명해주세요. ({context} 중심으로)"
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"당신은 {subject} 교육 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"검색 오류: {e}"

def generate_motivation_message(context="시작"):
    if not _openai_enabled():
        mock_messages = [
            "오늘도 한 문제 더!",
            "포기하지 않는 것이 실력입니다.",
            "꾸준함이 가장 큰 무기입니다.",
            "한 걸음씩 나아가면 됩니다.",
            "실수는 성장의 기회입니다."
        ]
        return random.choice(mock_messages)
    
    if not client:
        return "열심히 공부해봅시다!"
    
    if context == "시작":
        prompt = "학생이 문제를 풀기 시작할 때 동기부여가 되는 짧은 응원 메시지를 하나 생성해주세요. (1-2문장)"
    else:
        prompt = "학생이 문제를 제출한 후 격려하고 동기부여하는 짧은 메시지를 하나 생성해주세요. (1-2문장)"
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 학생을 격려하는 선생님입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return "열심히 공부해봅시다!"

def generate_book_recommendations():
    if not _openai_enabled():
        return [
            "공부의 기술 - 저자미상",
            "메타인지 학습법 - 저자미상",
            "초등 사고력 훈련 - 저자미상",
            "수학 잘하는 습관 - 저자미상",
            "영어 독해 전략 - 저자미상",
            "자기주도 학습법 - 저자미상",
            "집중력 향상 훈련 - 저자미상",
            "기억력 공부법 - 저자미상",
            "1등 공부 습관 - 저자미상",
            "학습 동기 설계 - 저자미상"
        ]
    
    if not client:
        return []
    
    prompt = """
이달의 추천 도서 10권을 추천해주세요.
중고등학생이 읽기 좋은 교양 도서, 자기계발서, 소설 등을 포함해주세요.

다음 형식으로 정확히 10권을 작성해주세요:

1. [도서명] - [저자]
2. [도서명] - [저자]
...
10. [도서명] - [저자]
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 도서 추천 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        books = []
        
        for line in content.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                book_info = line.split('.', 1)[-1].strip() if '.' in line else line
                books.append(book_info)
        
        return books[:10]
    
    except Exception as e:
        return [
            "코스모스 - 칼 세이건",
            "총, 균, 쇠 - 재레드 다이아몬드",
            "사피엔스 - 유발 하라리",
            "아몬드 - 손원평",
            "미움받을 용기 - 기시미 이치로",
            "데미안 - 헤르만 헤세",
            "어린왕자 - 생텍쥐페리",
            "1984 - 조지 오웰",
            "멋진 신세계 - 올더스 헉슬리",
            "호밀밭의 파수꾼 - J.D. 샐린저"
        ]
