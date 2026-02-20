import openai_helper as ai

print("OpenAI 초기화 테스트...")
result = ai.init_openai()

if result:
    print("✅ OpenAI API 키가 성공적으로 설정되었습니다!")
    print(f"클라이언트 객체: {ai.client}")
else:
    print("❌ OpenAI API 키 설정에 실패했습니다.")
