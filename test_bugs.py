import database as db

db.init_database()

print("=== 문제 생성 테스트 ===")

session_id = db.create_study_session(
    student_id=1,
    subject='수학',
    grade='중1',
    page_start=10,
    page_end=20,
    difficulty='보통',
    exam_type='중간',
    total_questions=3
)

print(f"세션 ID: {session_id}")

test_questions = [
    {
        'question': '1 + 1 = ?',
        'answer': '2',
        'explanation': '1과 1을 더하면 2입니다.'
    },
    {
        'question': '2 x 3 = ?',
        'answer': '6',
        'explanation': '2에 3을 곱하면 6입니다.'
    },
    {
        'question': '10 - 5 = ?',
        'answer': '5',
        'explanation': '10에서 5를 빼면 5입니다.'
    }
]

db.save_questions(session_id, test_questions)
print("✅ 문제 저장 완료")

print("\n=== 저장된 문제 확인 ===")
questions = db.get_session_questions(session_id)

for q in questions:
    print(f"\n문제 {q['question_number']}:")
    print(f"  question_text: {q['question_text']}")
    print(f"  answer: {q['answer']}")
    print(f"  explanation: {q['explanation']}")

print("\n=== 단어장 테스트 ===")

db.save_search_history(1, '수학', '공식', '피타고라스 정리입니다.')
db.save_search_history(2, '영어', 'apple', 'apple은 사과입니다.')
db.save_search_history(1, '영어', 'book', 'book은 책입니다.')

print("\n학생 1의 단어장:")
history1 = db.get_search_history(1)
for item in history1:
    print(f"  [{item['subject']}] {item['search_term']}: {item['result_text']}")

print("\n학생 2의 단어장:")
history2 = db.get_search_history(2)
for item in history2:
    print(f"  [{item['subject']}] {item['search_term']}: {item['result_text']}")

print("\n✅ 모든 테스트 완료")
