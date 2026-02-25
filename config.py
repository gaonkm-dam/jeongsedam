# 정세담 프로젝트 - OpenAI ON/OFF 전역 제어 설정

# OpenAI 사용 여부
# True: OpenAI API 실제 사용 (크레딧 소비)
# False: Mock 데이터 사용 (개발 모드, 크레딧 소비 없음)

USE_OPENAI = False

# 설명:
# - 개발 단계: False로 설정하여 크레딧 절약
# - 시연/운영: True로 설정하여 실제 AI 기능 사용
# - 기존 OpenAI 기능은 그대로 유지되며, 이 설정으로만 제어됨
