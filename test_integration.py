"""
정세담 프로젝트 - 학생↔학부모 데이터 공유 + OpenAI 연결 통합 테스트
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import pandas as pd
from datetime import date

DB_PATH = "student_system.db"
PASS = "✅"
FAIL = "❌"
results = []

def log(label, ok, detail=""):
    mark = PASS if ok else FAIL
    msg = f"  {mark} {label}"
    if detail:
        msg += f"\n     → {detail}"
    print(msg)
    results.append(ok)

def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

print("=" * 60)
print("  정세담 통합 테스트 (학생↔학부모 + OpenAI)")
print("=" * 60)

# ──────────────────────────────────────────────
# [1] DB 기본 구조 확인
# ──────────────────────────────────────────────
print("\n[1] DB 테이블 구조 확인")
import database as db
db.init_database()

con = get_conn()
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
con.close()

required = ["students","study_sessions","questions","psychological_tests",
            "search_history","rank_cache","parents","parent_student",
            "student_summary","subject_stats","psychology_status",
            "university_prediction","parent_motivation_log","parent_book_reco_log"]
for t in required:
    log(f"테이블 존재: {t}", t in tables)

# ──────────────────────────────────────────────
# [2] 학생 로그인 확인
# ──────────────────────────────────────────────
print("\n[2] 학생 로그인")
student = db.get_student_by_login("student1", "pass1")
log("student1 로그인", student is not None, f"id={student['id']}, name={student['name']}" if student else "")
STUDENT_ID = student['id'] if student else 1

# ──────────────────────────────────────────────
# [3] 학습 세션 생성 + 문제 저장 + 채점
# ──────────────────────────────────────────────
print("\n[3] 학생 - 학습 세션 생성 + 문제 저장 + 채점")

session_id = db.create_study_session(
    student_id=STUDENT_ID,
    subject="수학",
    grade="고1",
    page_start=1,
    page_end=10,
    difficulty="보통",
    exam_type="중간",
    total_questions=3
)
log("학습 세션 생성", session_id > 0, f"session_id={session_id}")

questions = [
    {"question_number": 1, "question_text": "1+1=?",   "answer": "2",  "explanation": "덧셈 기본"},
    {"question_number": 2, "question_text": "2×3=?",   "answer": "6",  "explanation": "곱셈 기본"},
    {"question_number": 3, "question_text": "10÷2=?",  "answer": "5",  "explanation": "나눗셈 기본"},
]
db.save_questions(session_id, questions)
saved_q = db.get_session_questions(session_id)
log("문제 저장 (3개)", len(saved_q) == 3, f"저장된 문제 수: {len(saved_q)}")

# 정답 2개, 오답 1개
user_answers = {1: "2", 2: "6", 3: "99"}
correct_count = db.submit_answers(session_id, user_answers)
log("채점 완료", correct_count == 2, f"정답 수: {correct_count}/3")

# ──────────────────────────────────────────────
# [4] 심리 체크 저장
# ──────────────────────────────────────────────
print("\n[4] 학생 - 심리 체크 저장")

psych_answers = {f"q{i}": (3 if i <= 10 else 2) for i in range(1, 21)}
db.save_psychological_test(STUDENT_ID, psych_answers)

con = get_conn()
psy_row = con.execute(
    "SELECT total_score, test_date FROM psychological_tests WHERE student_id=? ORDER BY id DESC LIMIT 1",
    (STUDENT_ID,)
).fetchone()
con.close()
log("심리 체크 저장", psy_row is not None,
    f"total_score={psy_row['total_score']}, test_date={psy_row['test_date'][:10]}" if psy_row else "")

# ──────────────────────────────────────────────
# [5] 단어장 저장
# ──────────────────────────────────────────────
print("\n[5] 학생 - 단어장 저장")

db.save_search_history(STUDENT_ID, "수학", "피타고라스", "직각삼각형의 세 변의 관계를 나타내는 공식")
vocab = db.get_search_history(STUDENT_ID)
log("단어장 저장/조회", len(vocab) > 0, f"저장된 항목: {len(vocab)}개")

# ──────────────────────────────────────────────
# [6] 학부모 측 - 학습 요약 조회
# ──────────────────────────────────────────────
print("\n[6] 학부모 측 - 학습 데이터 조회")

# fetch_session_summary (직접 SQL - 학부모 페이지와 동일 로직)
con = get_conn()
row = con.execute("""
    SELECT
        COALESCE(SUM(total_questions), 0) AS tq,
        COALESCE(SUM(correct_count), 0)   AS cc,
        COUNT(DISTINCT date(created_at))  AS days,
        MAX(created_at)                   AS last_dt
    FROM study_sessions WHERE student_id=?
""", (STUDENT_ID,)).fetchone()
con.close()

tq, cc = row[0], row[1]
log("학부모 - 총 문제 수 조회", tq >= 3, f"총 문제={tq}개")
log("학부모 - 정답 수 조회",   cc >= 2, f"총 정답={cc}개")
acc = round(cc / tq * 100, 1) if tq > 0 else 0
log("학부모 - 정답률 계산",    acc > 0, f"정답률={acc}%")

# fetch_sessions (JOIN 방식 - 학부모 페이지와 동일 로직)
con = get_conn()
df = pd.read_sql("""
    SELECT ss.subject, ss.created_at, q.is_correct, q.question_text AS concept
    FROM study_sessions ss
    LEFT JOIN questions q ON q.session_id = ss.id
    WHERE ss.student_id = ?
""", con, params=(STUDENT_ID,))
con.close()
log("학부모 - 과목/정오답 JOIN 조회", len(df) >= 3,
    f"조회된 행 수={len(df)}, 과목={df['subject'].unique().tolist()}")
if not df.empty:
    valid = pd.to_numeric(df["is_correct"], errors="coerce").dropna()
    rate = round(valid.mean() * 100, 1) if len(valid) > 0 else None
    log("학부모 - is_correct 집계", rate is not None, f"집계 정답률={rate}%")

# ──────────────────────────────────────────────
# [7] 학부모 측 - 심리 데이터 조회
# ──────────────────────────────────────────────
print("\n[7] 학부모 측 - 심리 데이터 조회 (test_date 컬럼)")

con = get_conn()
psy_df = pd.read_sql("""
    SELECT test_date, q1, q2, q3, q4, q5, total_score
    FROM psychological_tests
    WHERE student_id=?
    ORDER BY test_date DESC LIMIT 1
""", con, params=(STUDENT_ID,))
con.close()
log("학부모 - 심리 데이터 조회", not psy_df.empty,
    f"total_score={psy_df.iloc[0]['total_score']}" if not psy_df.empty else "")

# ──────────────────────────────────────────────
# [8] AI OFF 상태 - Mock 데이터 반환 확인
# ──────────────────────────────────────────────
print("\n[8] AI OFF 상태 - Mock 데이터 확인")

# session_state 없는 환경이므로 직접 config 조작
import config
original = config.USE_OPENAI
config.USE_OPENAI = False

import openai_helper as ai

# _openai_enabled는 session_state 없으면 config.USE_OPENAI 사용
enabled = ai._openai_enabled()
log("AI OFF 상태 인식", enabled == False, f"_openai_enabled()={enabled}")

mock_q = ai.generate_questions("수학", "고1", 1, 10, "보통", "중간", 2)
log("AI OFF - Mock 문제 생성", mock_q is not None and len(mock_q) == 2,
    f"생성된 문제 수: {len(mock_q) if mock_q else 0}")

mock_m = ai.generate_motivation_message("시작")
log("AI OFF - Mock 동기부여 문구", bool(mock_m), f"'{mock_m[:30]}...'")

mock_b = ai.generate_book_recommendations()
log("AI OFF - Mock 추천 도서", len(mock_b) >= 5, f"{len(mock_b)}권 반환")

# ──────────────────────────────────────────────
# [9] AI ON 상태 - OpenAI 실제 연결 확인
# ──────────────────────────────────────────────
print("\n[9] AI ON 상태 - OpenAI 실제 연결 테스트")

config.USE_OPENAI = True
ai_init = ai.init_openai()
log("OpenAI 클라이언트 초기화", ai_init, "API 키 로드 성공" if ai_init else "API 키 없음")

if ai_init:
    # 문제 1개만 생성 (비용 최소화)
    real_q = ai.generate_questions("수학", "고1", 1, 5, "쉬움", "중간", 1)
    ok = bool(real_q and len(real_q) > 0 and real_q[0].get("question_text") or
               (real_q and real_q[0].get("question")))
    detail = ""
    if real_q and len(real_q) > 0:
        q_text = real_q[0].get("question_text") or real_q[0].get("question", "")
        detail = f"문제 내용: '{q_text[:40]}...'" if len(q_text) > 40 else f"문제 내용: '{q_text}'"
    log("OpenAI 실제 문제 생성 (1개)", ok, detail)

    mot = ai.generate_motivation_message("시작")
    log("OpenAI 동기부여 문구 생성", bool(mot) and "모의" not in mot,
        f"'{mot[:40]}'" if mot else "")

# 원복
config.USE_OPENAI = original

# ──────────────────────────────────────────────
# 최종 결과
# ──────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(results)
total  = len(results)
print(f"  결과: {passed}/{total} 통과")
if passed == total:
    print(f"  {PASS} 모든 테스트 통과 - 학생↔학부모 데이터 연동 정상")
else:
    failed = [i+1 for i, r in enumerate(results) if not r]
    print(f"  {FAIL} 실패 항목 번호: {failed}")
print("=" * 60)
