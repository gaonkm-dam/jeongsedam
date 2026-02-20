import config
import openai_helper as ai

print("=" * 50)
print("OpenAI ON/OFF 제어 테스트")
print("=" * 50)

print(f"\n현재 설정: config.USE_OPENAI = {config.USE_OPENAI}")

if config.USE_OPENAI:
    print("✅ OpenAI ON - 실제 AI 사용 모드")
else:
    print("⚠️  OpenAI OFF - 개발 모드 (Mock 데이터)")

print("\n" + "=" * 50)
print("Mock 데이터 테스트 (USE_OPENAI = False)")
print("=" * 50)

original_setting = config.USE_OPENAI
config.USE_OPENAI = False

print("\n1. 문제 생성 테스트")
questions = ai.generate_questions('수학', '중1', 10, 20, '보통', '중간', 3)
if questions:
    print(f"✅ Mock 문제 {len(questions)}개 생성됨")
    for i, q in enumerate(questions, 1):
        print(f"  문제 {i}: {q['question'][:50]}...")
else:
    print("❌ 문제 생성 실패")

print("\n2. 검색 기능 테스트")
search_result = ai.search_content('영어', 'apple')
print(f"✅ Mock 검색 결과: {search_result}")

print("\n3. 동기부여 메시지 테스트")
motivation = ai.generate_motivation_message("시작")
print(f"✅ Mock 동기부여: {motivation}")

print("\n4. 추천 도서 테스트")
books = ai.generate_book_recommendations()
if books:
    print(f"✅ Mock 도서 {len(books)}권 생성됨")
    for i, book in enumerate(books[:3], 1):
        print(f"  {i}. {book}")
    print(f"  ... (총 {len(books)}권)")
else:
    print("❌ 도서 생성 실패")

config.USE_OPENAI = original_setting

print("\n" + "=" * 50)
print(f"테스트 완료 (설정 복원: {config.USE_OPENAI})")
print("=" * 50)

print("\n📋 설정 변경 방법:")
print("config.py 파일에서 USE_OPENAI 값을 변경하세요")
print("  - True: 실제 OpenAI 사용 (크레딧 소비)")
print("  - False: Mock 데이터 사용 (크레딧 절약)")
