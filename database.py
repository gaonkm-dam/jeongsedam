import sqlite3
import datetime

DB_PATH = "student_system.db"


def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_database():
    con = get_connection()
    cur = con.cursor()

    # ── 학생 ──────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT    NOT NULL,
        login_id           TEXT    UNIQUE NOT NULL,
        password           TEXT    NOT NULL,
        grade              TEXT,
        target_university  TEXT,
        target_department  TEXT
    )
    """)

    # ── 학습 세션 ───────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_sessions (
        id              INTEGER   PRIMARY KEY AUTOINCREMENT,
        student_id      INTEGER   NOT NULL,
        subject         TEXT      NOT NULL,
        grade           TEXT      NOT NULL,
        page_start      INTEGER,
        page_end        INTEGER,
        difficulty      TEXT      NOT NULL,
        exam_type       TEXT      NOT NULL,
        total_questions INTEGER   NOT NULL,
        correct_count   INTEGER   DEFAULT 0,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── 문제 ───────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      INTEGER NOT NULL,
        question_number INTEGER NOT NULL,
        question_text   TEXT,
        answer          TEXT,
        explanation     TEXT,
        is_correct      INTEGER DEFAULT 0
    )
    """)

    # ── 심리 테스트 ─────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS psychological_tests (
        id          INTEGER   PRIMARY KEY AUTOINCREMENT,
        student_id  INTEGER   NOT NULL,
        q1  INTEGER, q2  INTEGER, q3  INTEGER, q4  INTEGER, q5  INTEGER,
        q6  INTEGER, q7  INTEGER, q8  INTEGER, q9  INTEGER, q10 INTEGER,
        q11 INTEGER, q12 INTEGER, q13 INTEGER, q14 INTEGER, q15 INTEGER,
        q16 INTEGER, q17 INTEGER, q18 INTEGER, q19 INTEGER, q20 INTEGER,
        total_score INTEGER,
        test_date   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── 검색 이력(단어장) ────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
        id          INTEGER   PRIMARY KEY AUTOINCREMENT,
        student_id  INTEGER   NOT NULL,
        subject     TEXT,
        search_term TEXT,
        result_text TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── 순위 캐시 ───────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rank_cache (
        student_id    INTEGER PRIMARY KEY,
        total_score   REAL    DEFAULT 0,
        total_correct INTEGER DEFAULT 0,
        updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── 학부모 테이블 ────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parents (
        id          INTEGER   PRIMARY KEY AUTOINCREMENT,
        parent_name TEXT,
        email       TEXT      UNIQUE,
        password    TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_student (
        id         INTEGER   PRIMARY KEY AUTOINCREMENT,
        parent_id  INTEGER,
        student_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_summary (
        student_id      INTEGER PRIMARY KEY,
        total_questions INTEGER,
        correct_rate    REAL,
        study_days      INTEGER,
        level           TEXT,
        last_study_date TEXT,
        updated_at      TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subject_stats (
        id              INTEGER   PRIMARY KEY AUTOINCREMENT,
        student_id      INTEGER,
        subject         TEXT,
        total_questions INTEGER,
        correct_rate    REAL,
        updated_at      TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS psychology_status (
        student_id  INTEGER PRIMARY KEY,
        total_score INTEGER,
        risk_level  TEXT,
        note        TEXT,
        updated_at  TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS university_prediction (
        id              INTEGER   PRIMARY KEY AUTOINCREMENT,
        student_id      INTEGER,
        score_input     INTEGER,
        university_name TEXT,
        department      TEXT,
        degree_type     TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_motivation_log (
        id         INTEGER   PRIMARY KEY AUTOINCREMENT,
        parent_id  INTEGER,
        message    TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS parent_book_reco_log (
        id         INTEGER   PRIMARY KEY AUTOINCREMENT,
        parent_id  INTEGER,
        year_month TEXT,
        title      TEXT,
        author     TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    con.commit()

    # ── 기본 학생 3명 삽입 ───────────────────────────────────
    students = [
        ("학생1", "student1", "pass1", "고1"),
        ("학생2", "student2", "pass2", "고2"),
        ("학생3", "student3", "pass3", "고3"),
    ]
    for name, login_id, password, grade in students:
        cur.execute(
            "INSERT OR IGNORE INTO students (name, login_id, password, grade) VALUES (?,?,?,?)",
            (name, login_id, password, grade)
        )

    # ── 기본 학부모 3명 삽입 ─────────────────────────────────
    parents = [
        ("학부모1", "parent1@test.com", "pass1"),
        ("학부모2", "parent2@test.com", "pass2"),
        ("학부모3", "parent3@test.com", "pass3"),
    ]
    for pname, email, pw in parents:
        cur.execute(
            "INSERT OR IGNORE INTO parents (parent_name, email, password) VALUES (?,?,?)",
            (pname, email, pw)
        )

    # ── 학부모-학생 연결 (중복 방지: UNIQUE 제약 + INSERT OR IGNORE) ──────
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_parent_student ON parent_student(parent_id, student_id)")
    except Exception:
        pass
    for i in range(1, 4):
        cur.execute(
            "INSERT OR IGNORE INTO parent_student (parent_id, student_id) VALUES (?,?)",
            (i, i)
        )

    # ── 순위 캐시 초기화 ─────────────────────────────────────
    cur.execute("SELECT id FROM students")
    for row in cur.fetchall():
        cur.execute(
            "INSERT OR IGNORE INTO rank_cache (student_id, total_score, total_correct) VALUES (?,0,0)",
            (row[0],)
        )

    con.commit()
    con.close()


# ── 학생 조회 ────────────────────────────────────────────────

def get_student_by_login(login_id: str, password: str):
    con = get_connection()
    row = con.execute(
        "SELECT * FROM students WHERE login_id=? AND password=?",
        (login_id, password)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def get_student_by_id(student_id: int):
    con = get_connection()
    row = con.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_student_stats(student_id: int) -> dict:
    con = get_connection()

    total_row = con.execute(
        "SELECT COALESCE(SUM(total_questions),0) AS tq, COALESCE(SUM(correct_count),0) AS cc FROM study_sessions WHERE student_id=?",
        (student_id,)
    ).fetchone()
    total_questions = total_row["tq"] if total_row else 0
    total_correct   = total_row["cc"] if total_row else 0
    accuracy = round(total_correct / total_questions * 100, 1) if total_questions > 0 else 0.0

    last_row = con.execute(
        "SELECT MAX(created_at) AS ld FROM study_sessions WHERE student_id=?",
        (student_id,)
    ).fetchone()
    last_study_date = last_row["ld"] if last_row else None

    level = 1
    if total_questions >= 200:
        level = 5
    elif total_questions >= 100:
        level = 4
    elif total_questions >= 50:
        level = 3
    elif total_questions >= 20:
        level = 2

    con.close()
    return {
        "total_questions": total_questions,
        "total_correct": total_correct,
        "accuracy": accuracy,
        "last_study_date": last_study_date,
        "level": level,
    }


def update_target_university(student_id: int, university: str, department: str):
    con = get_connection()
    con.execute(
        "UPDATE students SET target_university=?, target_department=? WHERE id=?",
        (university, department, student_id)
    )
    con.commit()
    con.close()


# ── 학습 세션 ────────────────────────────────────────────────

def create_study_session(student_id, subject, grade, page_start, page_end,
                          difficulty, exam_type, total_questions) -> int:
    con = get_connection()
    cur = con.execute(
        """INSERT INTO study_sessions
           (student_id, subject, grade, page_start, page_end, difficulty, exam_type, total_questions)
           VALUES (?,?,?,?,?,?,?,?)""",
        (student_id, subject, grade, page_start, page_end, difficulty, exam_type, total_questions)
    )
    session_id = cur.lastrowid
    con.commit()
    con.close()
    return session_id


def save_questions(session_id: int, questions: list):
    con = get_connection()
    for q in questions:
        con.execute(
            """INSERT INTO questions (session_id, question_number, question_text, answer, explanation)
               VALUES (?,?,?,?,?)""",
            (
                session_id,
                q.get("question_number", 0),
                q.get("question_text", ""),
                q.get("answer", ""),
                q.get("explanation", ""),
            )
        )
    con.commit()
    con.close()


def get_session_questions(session_id: int) -> list:
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM questions WHERE session_id=? ORDER BY question_number",
        (session_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def submit_answers(session_id: int, user_answers: dict) -> int:
    """사용자 답변을 채점하고 정답 수를 반환."""
    con = get_connection()
    questions = con.execute(
        "SELECT * FROM questions WHERE session_id=?", (session_id,)
    ).fetchall()

    correct_count = 0
    for q in questions:
        num = q["question_number"]
        user_ans = str(user_answers.get(num, "")).strip()
        correct_ans = str(q["answer"]).strip()
        is_correct = 1 if user_ans == correct_ans else 0
        if is_correct:
            correct_count += 1
        con.execute(
            "UPDATE questions SET is_correct=? WHERE id=?",
            (is_correct, q["id"])
        )

    con.execute(
        "UPDATE study_sessions SET correct_count=? WHERE id=?",
        (correct_count, session_id)
    )

    # 순위 캐시 갱신
    session = con.execute(
        "SELECT student_id, total_questions FROM study_sessions WHERE id=?",
        (session_id,)
    ).fetchone()
    if session:
        sid = session["student_id"]
        tq  = session["total_questions"]
        score = round((correct_count / tq * 100), 1) if tq > 0 else 0
        con.execute("""
            INSERT INTO rank_cache (student_id, total_score, total_correct)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
              total_score   = total_score   + excluded.total_score,
              total_correct = total_correct + excluded.total_correct,
              updated_at    = CURRENT_TIMESTAMP
        """, (sid, score, correct_count))

    con.commit()
    con.close()
    return correct_count


def get_study_history(student_id: int) -> list:
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM study_sessions WHERE student_id=? ORDER BY created_at DESC",
        (student_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── 심리 테스트 ──────────────────────────────────────────────

def save_psychological_test(student_id: int, answers: dict):
    total = sum(answers.values())
    cols = ", ".join([f"q{i}" for i in range(1, 21)])
    vals = ", ".join(["?" for _ in range(20)])
    q_vals = [answers.get(f"q{i}", 0) for i in range(1, 21)]
    con = get_connection()
    con.execute(
        f"INSERT INTO psychological_tests (student_id, {cols}, total_score) VALUES (?, {vals}, ?)",
        [student_id] + q_vals + [total]
    )
    con.commit()
    con.close()


# ── 검색 이력(단어장) ─────────────────────────────────────────

def save_search_history(student_id: int, subject: str, search_term: str, result_text: str):
    con = get_connection()
    con.execute(
        "INSERT INTO search_history (student_id, subject, search_term, result_text) VALUES (?,?,?,?)",
        (student_id, subject, search_term, result_text)
    )
    con.commit()
    con.close()


def get_search_history(student_id: int, subject: str = None) -> list:
    con = get_connection()
    if subject:
        rows = con.execute(
            "SELECT * FROM search_history WHERE student_id=? AND subject=? ORDER BY created_at DESC",
            (student_id, subject)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM search_history WHERE student_id=? ORDER BY created_at DESC",
            (student_id,)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── 순위 ────────────────────────────────────────────────────

def get_rankings() -> list:
    con = get_connection()
    rows = con.execute("""
        SELECT s.id, s.name, COALESCE(r.total_score,0) AS total_score, COALESCE(r.total_correct,0) AS total_correct
        FROM students s
        LEFT JOIN rank_cache r ON s.id = r.student_id
        ORDER BY total_score DESC, total_correct DESC
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]
