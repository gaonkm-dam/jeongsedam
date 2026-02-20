@echo off
echo ========================================
echo 정세담 학습 시스템 실행
echo ========================================
echo.

echo 필수 패키지 확인 중...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Streamlit이 설치되지 않았습니다. 설치 중...
    pip install streamlit openai pandas
)

echo.
echo OpenAI API 키 확인...
if not exist .env (
    if not exist api_key.txt (
        echo 경고: .env 또는 api_key.txt 파일이 없습니다!
        echo OPENAI_API_KEY를 설정해주세요.
        echo.
    )
)

echo.
echo Streamlit 앱 실행 중...
streamlit run app.py

pause
