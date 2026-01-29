# 🚀 Streamlit Cloud 배포 가이드

## 📋 준비 단계

### 1. GitHub 계정 준비
- GitHub 계정이 없다면: https://github.com/join 에서 가입
- GitHub 계정이 있다면: https://github.com 에 로그인

### 2. Streamlit Cloud 계정 생성
- https://share.streamlit.io 접속
- "Sign up" 클릭
- GitHub 계정으로 로그인 (연동)

## 🔧 배포 과정

### 1단계: GitHub 저장소 생성

#### 방법 A: GitHub Desktop 사용 (쉬움)
1. GitHub Desktop 다운로드: https://desktop.github.com
2. 설치 후 GitHub 계정으로 로그인
3. "File" → "Add Local Repository" 클릭
4. 프로젝트 폴더 선택: `C:\Users\pc\Desktop\멍구폴더\멍구폴더\정세담\정세담 프로그램\정세담 정책 프로그램`
5. "Create Repository" 클릭
6. Repository name: `jeongsedam-policy-program`
7. "Publish repository" 클릭
8. ✅ **Private** 체크 해제 (공개 저장소로 설정)
9. "Publish Repository" 클릭

#### 방법 B: Git 명령어 사용
```bash
cd "C:\Users\pc\Desktop\멍구폴더\멍구폴더\정세담\정세담 프로그램\정세담 정책 프로그램"

# Git 초기화
git init

# 모든 파일 추가
git add .

# 첫 커밋
git commit -m "Initial commit: 정세담 정책 프로그램"

# GitHub 저장소 연결 (저장소 생성 후)
git remote add origin https://github.com/YOUR_USERNAME/jeongsedam-policy-program.git

# Push
git branch -M main
git push -u origin main
```

### 2단계: Streamlit Cloud 배포

1. **Streamlit Cloud 접속**: https://share.streamlit.io
2. **"New app" 클릭**
3. **저장소 선택**:
   - Repository: `YOUR_USERNAME/jeongsedam-policy-program`
   - Branch: `main`
   - Main file path: `app.py`
4. **Advanced settings 클릭**
5. **Secrets 추가**:
   ```toml
   OPENAI_API_KEY = "sk-your-actual-api-key-here"
   ```
6. **"Deploy!" 클릭**

### 3단계: 배포 완료 ✅

- 3~5분 후 배포 완료
- 자동으로 URL 생성: `https://your-app-name.streamlit.app`
- 이 URL을 모바일/PC 어디서나 접속 가능!

## 🔐 보안 설정

### OpenAI API 키 보호

**중요**: `.env` 파일은 절대 GitHub에 올리지 마세요!

✅ **안전한 방법**:
1. `.gitignore`에 `.env` 포함 (이미 완료)
2. Streamlit Cloud의 Secrets에서 직접 설정
3. 코드에서 다음과 같이 불러오기:

```python
import os
import streamlit as st

# 로컬 개발
api_key = os.environ.get("OPENAI_API_KEY")

# Streamlit Cloud
if not api_key:
    api_key = st.secrets.get("OPENAI_API_KEY")
```

## 📱 접속 방법

배포 완료 후:

- **PC**: 브라우저에서 `https://your-app.streamlit.app` 접속
- **모바일**: 같은 URL 접속
- **공유**: URL을 친구/동료에게 공유

## 🔄 업데이트 방법

코드를 수정한 후:

### GitHub Desktop 사용
1. GitHub Desktop 열기
2. 변경사항 확인
3. "Commit to main" 클릭
4. "Push origin" 클릭
5. 자동으로 Streamlit Cloud에 재배포 (1~2분)

### Git 명령어
```bash
git add .
git commit -m "업데이트 내용 설명"
git push
```

## ⚙️ 설정 변경

### 앱 URL 변경
1. Streamlit Cloud 대시보드 접속
2. 앱 선택 → Settings
3. "App URL" 수정

### 비밀번호 설정 (유료)
- Streamlit Cloud Pro: $20/month
- 비밀번호 보호, 비공개 앱

### 무료 플랜 제한
- 공개 앱만 가능
- 1개 앱까지 무료
- 리소스: 1GB RAM, 1 CPU

## 🆘 문제 해결

### 배포 실패
1. Streamlit Cloud 로그 확인
2. `requirements.txt` 패키지 확인
3. Python 버전 확인 (`runtime.txt`)

### API 키 오류
1. Streamlit Cloud Secrets 설정 확인
2. API 키가 올바른지 확인
3. OpenAI 계정 크레딧 확인

### 느린 속도
- 무료 플랜은 리소스 제한
- 이미지 생성시 20~40초 소요 (정상)

## 📞 추가 도움

- Streamlit 문서: https://docs.streamlit.io/streamlit-community-cloud
- Streamlit 커뮤니티: https://discuss.streamlit.io
- GitHub 도움말: https://docs.github.com

---

## ✅ 체크리스트

배포 전 확인:
- [ ] `.gitignore` 파일 확인
- [ ] `.env` 파일이 Git에서 제외되었는지 확인
- [ ] `requirements.txt` 모든 패키지 포함
- [ ] `runtime.txt` Python 버전 명시
- [ ] README.md 작성 완료
- [ ] GitHub 저장소 생성
- [ ] Streamlit Cloud Secrets에 API 키 설정
- [ ] 배포 버튼 클릭!

🎉 **성공적인 배포를 기원합니다!**
