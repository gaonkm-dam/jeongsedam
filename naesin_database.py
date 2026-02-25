import sqlite3
import datetime
import json

DB_PATH = "student_system.db"


def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_naesin_database():
    con = get_connection()
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS edu_users (
        user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        role      TEXT NOT NULL CHECK(role IN ('student','parent','teacher','policy')),
        name      TEXT NOT NULL,
        login_id  TEXT UNIQUE NOT NULL,
        password  TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS edu_students (
        student_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        school_id       INTEGER,
        region_code     TEXT DEFAULT 'seoul',
        grade_level     INTEGER DEFAULT 2,
        track_preference TEXT DEFAULT 'mixed' CHECK(track_preference IN ('suneung','naesin','mixed')),
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS edu_student_links (
        link_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        relation   TEXT NOT NULL CHECK(relation IN ('parent','teacher')),
        class_id   INTEGER,
        is_active  INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS schools (
        school_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        school_name TEXT NOT NULL,
        region_code TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        class_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        school_id   INTEGER,
        grade_level INTEGER,
        class_name  TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        subject_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_name TEXT UNIQUE NOT NULL,
        category     TEXT DEFAULT '공통' CHECK(category IN ('공통','사탐','과탐','기타')),
        is_active    INTEGER DEFAULT 1
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS terms (
        term_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        school_year INTEGER NOT NULL,
        grade_level INTEGER NOT NULL,
        semester    INTEGER NOT NULL CHECK(semester IN (1,2)),
        UNIQUE(school_year, grade_level, semester)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_grades (
        grade_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id        INTEGER NOT NULL,
        term_id           INTEGER NOT NULL,
        subject_id        INTEGER NOT NULL,
        grade_level_num   INTEGER NOT NULL CHECK(grade_level_num BETWEEN 1 AND 9),
        raw_score         REAL,
        rank_in_class     INTEGER,
        entered_by        TEXT DEFAULT 'student' CHECK(entered_by IN ('student','teacher')),
        verified_by_teacher INTEGER DEFAULT 0,
        verified_at       TIMESTAMP,
        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, term_id, subject_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_types (
        activity_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT UNIQUE NOT NULL,
        is_active        INTEGER DEFAULT 1
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_activities (
        activity_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id       INTEGER NOT NULL,
        activity_type_id INTEGER NOT NULL,
        title            TEXT NOT NULL,
        summary          TEXT,
        detail           TEXT,
        learned          TEXT,
        role             TEXT DEFAULT '개인' CHECK(role IN ('리더','팀원','개인')),
        major_related    INTEGER DEFAULT 0,
        start_date       TEXT,
        end_date         TEXT,
        hours            REAL,
        evidence_url     TEXT,
        tags             TEXT,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS teacher_activity_reviews (
        review_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER NOT NULL,
        teacher_id  INTEGER NOT NULL,
        status      TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
        score       REAL,
        comment     TEXT,
        reviewed_at TIMESTAMP,
        UNIQUE(activity_id, teacher_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_learning_logs (
        log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id       INTEGER NOT NULL,
        date             TEXT NOT NULL,
        study_minutes    INTEGER DEFAULT 0,
        study_subject_ids TEXT,
        study_type       TEXT DEFAULT 'other' CHECK(study_type IN ('problems','concept','review','mock','other')),
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, date)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_state_checks (
        check_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date       TEXT NOT NULL,
        focus      INTEGER CHECK(focus BETWEEN 1 AND 5),
        stress     INTEGER CHECK(stress BETWEEN 1 AND 5),
        fatigue    INTEGER CHECK(fatigue BETWEEN 1 AND 5),
        motivation INTEGER CHECK(motivation BETWEEN 1 AND 5),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, date)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_self_assessments (
        assessment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id         INTEGER NOT NULL,
        date               TEXT NOT NULL,
        performance_level  INTEGER CHECK(performance_level BETWEEN 1 AND 5),
        understanding_level INTEGER CHECK(understanding_level BETWEEN 1 AND 5),
        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, date)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS universities (
        university_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT UNIQUE NOT NULL,
        degree_type   TEXT DEFAULT 'four_year' CHECK(degree_type IN ('four_year','two_year')),
        region_code   TEXT,
        homepage_url  TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        department_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        university_id  INTEGER NOT NULL,
        name           TEXT NOT NULL,
        category       TEXT DEFAULT '기타' CHECK(category IN ('인문','이공','의약','예체능','기타')),
        department_url TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admissions_cutoffs (
        cutoff_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id  INTEGER NOT NULL,
        admission_type TEXT NOT NULL CHECK(admission_type IN ('naesin','holistic','suneung')),
        year           INTEGER NOT NULL,
        cutoff_value   TEXT,
        source         TEXT DEFAULT 'manual' CHECK(source IN ('official','manual','scraped')),
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_recommendation_snapshots (
        snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id   INTEGER NOT NULL,
        date         TEXT NOT NULL,
        track        TEXT NOT NULL CHECK(track IN ('naesin','holistic','suneung')),
        mode         TEXT DEFAULT 'demo_instant' CHECK(mode IN ('demo_instant','live_3day_avg')),
        filters      TEXT,
        results      TEXT,
        generated_by TEXT DEFAULT 'rules' CHECK(generated_by IN ('rules','ai','hybrid')),
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshots ON student_recommendation_snapshots(student_id, date, track)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_forecasts (
        forecast_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id       INTEGER NOT NULL,
        date             TEXT NOT NULL,
        metric           TEXT NOT NULL CHECK(metric IN ('naesin_avg','activity_strength','burnout_risk','admission_readiness')),
        window           TEXT NOT NULL CHECK(window IN ('d7','d30','ai')),
        value            TEXT,
        confidence_level TEXT DEFAULT 'mid' CHECK(confidence_level IN ('low','mid','high')),
        disclaimer       TEXT,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS policy_aggregates_daily (
        agg_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,
        region_code TEXT,
        school_id   INTEGER,
        class_id    INTEGER,
        metrics     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    con.commit()

    # ── 기존 중복 데이터 정리 (UNIQUE INDEX 생성 전에 먼저 실행) ──
    cur.execute("""
        DELETE FROM edu_students WHERE student_id NOT IN (
            SELECT MIN(student_id) FROM edu_students GROUP BY user_id
        )
    """)
    cur.execute("""
        DELETE FROM edu_student_links WHERE link_id NOT IN (
            SELECT MIN(link_id) FROM edu_student_links GROUP BY student_id, user_id, relation
        )
    """)
    cur.execute("""
        DELETE FROM student_activities WHERE activity_id NOT IN (
            SELECT MIN(activity_id) FROM student_activities GROUP BY student_id, activity_type_id, title
        )
    """)
    con.commit()

    # ── 중복 방지 UNIQUE INDEX ──
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_students_user ON edu_students(user_id)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_links_unique ON edu_student_links(student_id, user_id, relation)")
    con.commit()

    _seed_users(cur, con)
    _seed_subjects(cur, con)
    _seed_activity_types(cur, con)
    _seed_terms(cur, con)
    _seed_schools(cur, con)
    _seed_universities(cur, con)
    _seed_demo_data(cur, con)

    con.commit()
    con.close()


def _seed_users(cur, con):
    users = [
        ('student', '학생1(데모)', 'student1', 'pass1'),
        ('student', '학생2(데모)', 'student2', 'pass2'),
        ('student', '학생3(데모)', 'student3', 'pass3'),
        ('parent',  '학부모1(데모)', 'parent1', 'pass1'),
        ('teacher', '교사1(데모)', 'teacher1', 'pass1'),
        ('policy',  '정책담당자(데모)', 'policy1', 'pass1'),
    ]
    for role, name, login_id, pw in users:
        cur.execute(
            "INSERT OR IGNORE INTO edu_users (role,name,login_id,password) VALUES (?,?,?,?)",
            (role, name, login_id, pw)
        )
    con.commit()

    for i in range(1, 4):
        u = cur.execute("SELECT user_id FROM edu_users WHERE login_id=?", (f'student{i}',)).fetchone()
        if u:
            cur.execute(
                "INSERT OR IGNORE INTO edu_students (user_id, school_id, region_code, grade_level, track_preference) VALUES (?,1,'seoul',2,'mixed')",
                (u['user_id'],)
            )
    con.commit()

    parent = cur.execute("SELECT user_id FROM edu_users WHERE login_id='parent1'").fetchone()
    teacher = cur.execute("SELECT user_id FROM edu_users WHERE login_id='teacher1'").fetchone()
    if parent:
        for sid in [1, 2]:
            cur.execute(
                "INSERT OR IGNORE INTO edu_student_links (student_id,user_id,relation) VALUES (?,?,'parent')",
                (sid, parent['user_id'])
            )
    if teacher:
        for sid in [1, 2, 3]:
            cur.execute(
                "INSERT OR IGNORE INTO edu_student_links (student_id,user_id,relation,class_id) VALUES (?,?,'teacher',1)",
                (sid, teacher['user_id'])
            )
    con.commit()


def _seed_subjects(cur, con):
    subjects = [
        ('국어', '공통'), ('영어', '공통'), ('수학', '공통'), ('한국사', '공통'),
        ('물리학', '과탐'), ('화학', '과탐'), ('생명과학', '과탐'), ('지구과학', '과탐'),
        ('세계사', '사탐'), ('한국지리', '사탐'), ('세계지리', '사탐'), ('경제', '사탐'),
        ('정치와법', '사탐'), ('사회문화', '사탐'), ('생활과윤리', '사탐'), ('윤리와사상', '사탐'),
        ('제2외국어', '기타'), ('정보', '기타'), ('진로선택', '기타'),
    ]
    for name, cat in subjects:
        cur.execute(
            "INSERT OR IGNORE INTO subjects (subject_name, category) VALUES (?,?)",
            (name, cat)
        )
    con.commit()


def _seed_activity_types(cur, con):
    types = ['동아리', '봉사', '독서', '수상', '진로', '자율', '프로젝트', '대회', '기타']
    for t in types:
        cur.execute("INSERT OR IGNORE INTO activity_types (name) VALUES (?)", (t,))
    con.commit()


def _seed_terms(cur, con):
    for year in [2023, 2024, 2025]:
        for grade in [1, 2, 3]:
            for sem in [1, 2]:
                cur.execute(
                    "INSERT OR IGNORE INTO terms (school_year, grade_level, semester) VALUES (?,?,?)",
                    (year, grade, sem)
                )
    con.commit()


def _seed_schools(cur, con):
    cur.execute("INSERT OR IGNORE INTO schools (school_id, school_name, region_code) VALUES (1,'정세담고등학교','seoul')")
    cur.execute("INSERT OR IGNORE INTO classes (class_id, school_id, grade_level, class_name) VALUES (1,1,2,'2-1반')")
    cur.execute("INSERT OR IGNORE INTO classes (class_id, school_id, grade_level, class_name) VALUES (2,1,2,'2-2반')")
    cur.execute("INSERT OR IGNORE INTO classes (class_id, school_id, grade_level, class_name) VALUES (3,1,3,'3-1반')")
    con.commit()


def _seed_universities(cur, con):
    unis = [
        ('서울대학교',   'four_year', 'seoul',    'https://www.snu.ac.kr'),
        ('연세대학교',   'four_year', 'seoul',    'https://www.yonsei.ac.kr'),
        ('고려대학교',   'four_year', 'seoul',    'https://www.korea.ac.kr'),
        ('성균관대학교', 'four_year', 'seoul',    'https://www.skku.edu'),
        ('한양대학교',   'four_year', 'seoul',    'https://www.hanyang.ac.kr'),
        ('서강대학교',   'four_year', 'seoul',    'https://www.sogang.ac.kr'),
        ('중앙대학교',   'four_year', 'seoul',    'https://www.cau.ac.kr'),
        ('이화여자대학교','four_year','seoul',    'https://www.ewha.ac.kr'),
        ('경희대학교',   'four_year', 'seoul',    'https://www.khu.ac.kr'),
        ('한국외국어대학교','four_year','seoul',  'https://www.hufs.ac.kr'),
        ('서울시립대학교','four_year','seoul',    'https://www.uos.ac.kr'),
        ('건국대학교',   'four_year', 'seoul',    'https://www.konkuk.ac.kr'),
        ('동국대학교',   'four_year', 'seoul',    'https://www.dongguk.edu'),
        ('홍익대학교',   'four_year', 'seoul',    'https://www.hongik.ac.kr'),
        ('숙명여자대학교','four_year','seoul',    'https://www.sookmyung.ac.kr'),
        ('KAIST',        'four_year', 'daejeon',  'https://www.kaist.ac.kr'),
        ('POSTECH',      'four_year', 'gyeongbuk','https://www.postech.ac.kr'),
        ('부산대학교',   'four_year', 'busan',    'https://www.pusan.ac.kr'),
        ('경북대학교',   'four_year', 'gyeongbuk','https://www.knu.ac.kr'),
        ('전남대학교',   'four_year', 'jeonnam',  'https://www.jnu.ac.kr'),
        ('충남대학교',   'four_year', 'chungnam', 'https://www.cnu.ac.kr'),
        ('인하대학교',   'four_year', 'incheon',  'https://www.inha.ac.kr'),
        ('아주대학교',   'four_year', 'gyeonggi', 'https://www.ajou.ac.kr'),
        ('세종대학교',   'four_year', 'seoul',    'https://www.sejong.ac.kr'),
        ('단국대학교',   'four_year', 'chungnam', 'https://www.dankook.ac.kr'),
        ('동서울대학교', 'two_year',  'gyeonggi', 'https://www.du.ac.kr'),
        ('수원여자대학교','two_year', 'gyeonggi', 'https://www.swc.ac.kr'),
        ('인천재능대학교','two_year', 'incheon',  'https://www.jeiu.ac.kr'),
        ('경기과학기술대학교','two_year','gyeonggi','https://www.gtec.ac.kr'),
        ('한국폴리텍대학교','two_year','seoul',   'https://www.kopo.ac.kr'),
    ]
    for name, dtype, region, url in unis:
        cur.execute(
            "INSERT OR IGNORE INTO universities (name, degree_type, region_code, homepage_url) VALUES (?,?,?,?)",
            (name, dtype, region, url)
        )
    con.commit()

    dept_map = {
        '서울대학교': [
            ('국어국문학과','인문',1.0,70),('컴퓨터공학부','이공',1.1,80),
            ('경영학과','기타',1.2,75),('의학과','의약',1.0,85),
            ('법학과','기타',1.1,75),('수학과','이공',1.2,72),
            ('사회학과','기타',1.3,68),
        ],
        '연세대학교': [
            ('영어영문학과','인문',1.3,65),('전기전자공학부','이공',1.4,72),
            ('경영학과','기타',1.3,70),('의학과','의약',1.1,82),
            ('법학과','기타',1.4,68),('화학과','이공',1.5,65),
            ('심리학과','인문',1.4,67),
        ],
        '고려대학교': [
            ('국어국문학과','인문',1.4,63),('컴퓨터학과','이공',1.5,70),
            ('경영학과','기타',1.4,68),('의학과','의약',1.2,80),
            ('법학과','기타',1.5,66),('기계공학과','이공',1.5,65),
            ('사학과','인문',1.6,60),
        ],
        '성균관대학교': [
            ('한국어문학부','인문',1.6,60),('소프트웨어학과','이공',1.5,68),
            ('경영학과','기타',1.5,65),('의학과','의약',1.3,78),
            ('전자전기공학부','이공',1.6,65),('화학공학부','이공',1.7,62),
        ],
        '한양대학교': [
            ('국어국문학과','인문',1.7,58),('컴퓨터소프트웨어학부','이공',1.6,65),
            ('경영학부','기타',1.6,63),('의학과','의약',1.3,77),
            ('전기·생체공학부','이공',1.7,63),('화학공학과','이공',1.8,60),
        ],
        '서강대학교': [
            ('국어국문학과','인문',1.8,57),('컴퓨터공학과','이공',1.7,63),
            ('경영학부','기타',1.7,62),('전자공학과','이공',1.8,61),
            ('화학과','이공',1.9,58),('심리학과','인문',1.8,59),
        ],
        '중앙대학교': [
            ('국어국문학과','인문',2.0,55),('소프트웨어학부','이공',1.9,60),
            ('경영학부','기타',1.9,58),('의학부','의약',1.5,74),
            ('전자전기공학부','이공',2.0,58),('사회복지학과','기타',2.1,53),
        ],
        '이화여자대학교': [
            ('국어국문학과','인문',1.9,56),('컴퓨터공학과','이공',1.8,62),
            ('경영학부','기타',1.8,60),('의학과','의약',1.4,75),
            ('음악학부','예체능',2.0,54),('간호학과','의약',1.9,58),
        ],
        '경희대학교': [
            ('국어국문학과','인문',2.1,53),('소프트웨어융합학과','이공',2.0,58),
            ('경영학과','기타',2.0,57),('의학과','의약',1.5,73),
            ('한의학과','의약',1.6,70),('간호학과','의약',2.1,55),
        ],
        '한국외국어대학교': [
            ('영어학부','인문',2.0,55),('국제경영학과','기타',2.0,57),
            ('중국어학부','인문',2.1,53),('프랑스어학부','인문',2.2,51),
            ('일본어학부','인문',2.2,51),('독일어학부','인문',2.3,49),
        ],
        '서울시립대학교': [
            ('국어국문학과','인문',2.2,50),('컴퓨터과학부','이공',2.1,55),
            ('경영학과','기타',2.1,54),('전자전기컴퓨터공학부','이공',2.2,53),
            ('도시공학과','이공',2.3,50),
        ],
        '건국대학교': [
            ('국어국문학과','인문',2.3,49),('컴퓨터공학과','이공',2.2,54),
            ('경영학과','기타',2.2,52),('수의학과','의약',1.7,68),
            ('전자공학과','이공',2.3,51),('화학공학과','이공',2.4,48),
        ],
        '동국대학교': [
            ('국어국문학과','인문',2.4,47),('컴퓨터공학과','이공',2.3,52),
            ('경영학과','기타',2.3,50),('불교학과','인문',2.5,45),
            ('영화학과','예체능',2.4,47),('전자전기공학부','이공',2.4,49),
        ],
        '홍익대학교': [
            ('국어국문학과','인문',2.4,47),('컴퓨터공학과','이공',2.3,51),
            ('경영학과','기타',2.3,50),('회화학과','예체능',2.2,53),
            ('건축학과','이공',2.3,50),('산업디자인학과','예체능',2.2,52),
        ],
        '숙명여자대학교': [
            ('국어국문학과','인문',2.3,49),('IT공학과','이공',2.2,54),
            ('경영학부','기타',2.2,52),('약학과','의약',1.8,66),
            ('음악학부','예체능',2.3,49),('교육학과','기타',2.3,50),
        ],
        'KAIST': [
            ('수학과','이공',1.0,75),('물리학과','이공',1.1,73),
            ('전기및전자공학부','이공',1.1,78),('컴퓨터과학과','이공',1.0,80),
            ('화학과','이공',1.2,70),('기계공학과','이공',1.2,72),
        ],
        'POSTECH': [
            ('수학과','이공',1.1,74),('물리학과','이공',1.2,72),
            ('전자전기공학과','이공',1.2,76),('컴퓨터공학과','이공',1.1,78),
            ('화학공학과','이공',1.3,70),('기계공학과','이공',1.3,71),
        ],
        '부산대학교': [
            ('국어국문학과','인문',2.5,47),('전기공학과','이공',2.4,50),
            ('경영학과','기타',2.4,49),('의학과','의약',1.7,67),
            ('컴퓨터공학과','이공',2.4,50),('간호학과','의약',2.5,48),
        ],
        '경북대학교': [
            ('국어국문학과','인문',2.6,45),('전자공학부','이공',2.5,49),
            ('경영학부','기타',2.5,48),('의학과','의약',1.7,67),
            ('컴퓨터학부','이공',2.5,49),('수의학과','의약',1.9,63),
        ],
        '전남대학교': [
            ('국어국문학과','인문',2.7,43),('전기공학과','이공',2.6,47),
            ('경영학부','기타',2.6,46),('의학과','의약',1.8,65),
            ('컴퓨터정보통신공학부','이공',2.6,47),('간호학과','의약',2.6,46),
        ],
        '충남대학교': [
            ('국어국문학과','인문',2.7,43),('전기공학과','이공',2.6,47),
            ('경영학부','기타',2.6,46),('의학과','의약',1.8,65),
            ('컴퓨터공학과','이공',2.6,47),('수의학과','의약',2.0,62),
        ],
        '인하대학교': [
            ('국어교육과','인문',2.5,47),('전기컴퓨터공학부','이공',2.4,50),
            ('경영학과','기타',2.4,49),('의학과','의약',1.8,65),
            ('컴퓨터공학과','이공',2.4,51),('항공우주공학과','이공',2.3,52),
        ],
        '아주대학교': [
            ('국어국문학과','인문',2.6,45),('전자공학과','이공',2.5,49),
            ('경영학과','기타',2.5,48),('의학과','의약',1.9,63),
            ('소프트웨어학과','이공',2.5,50),('기계공학과','이공',2.5,49),
        ],
        '세종대학교': [
            ('국어국문학과','인문',2.8,42),('컴퓨터공학과','이공',2.7,46),
            ('경영학부','기타',2.7,45),('전자정보통신공학과','이공',2.7,46),
            ('데이터사이언스학과','이공',2.6,48),('호텔관광학부','기타',2.8,43),
        ],
        '단국대학교': [
            ('국어국문학과','인문',2.8,42),('소프트웨어학과','이공',2.7,46),
            ('경영학과','기타',2.7,45),('의학과','의약',1.9,63),
            ('전자전기공학부','이공',2.7,46),('치의학과','의약',2.0,60),
        ],
        '동서울대학교': [
            ('컴퓨터소프트웨어학과','이공',4.5,30),('간호학과','의약',4.0,35),
            ('경영학과','기타',4.8,27),('디자인학과','예체능',4.5,30),
        ],
        '수원여자대학교': [
            ('간호학과','의약',4.0,35),('유아교육과','기타',4.5,30),
            ('뷰티디자인학과','예체능',4.8,27),('식품영양학과','기타',4.7,28),
        ],
        '인천재능대학교': [
            ('컴퓨터응용학과','이공',4.6,29),('간호학과','의약',4.1,34),
            ('비즈니스영어학과','인문',4.9,26),('사회복지학과','기타',5.0,25),
        ],
        '경기과학기술대학교': [
            ('컴퓨터모바일학과','이공',4.5,30),('기계설계과','이공',4.7,28),
            ('전기과','이공',4.8,27),('토목환경과','이공',4.9,26),
        ],
        '한국폴리텍대학교': [
            ('컴퓨터응용제어과','이공',5.0,25),('기계과','이공',5.0,25),
            ('전기과','이공',5.0,25),('메카트로닉스과','이공',5.0,25),
        ],
    }

    for uni_name, depts in dept_map.items():
        uni = cur.execute("SELECT university_id FROM universities WHERE name=?", (uni_name,)).fetchone()
        if not uni:
            continue
        uid = uni['university_id']
        for dname, dcat, naesin_cut, hol_score_min in depts:
            existing = cur.execute(
                "SELECT department_id FROM departments WHERE university_id=? AND name=?", (uid, dname)
            ).fetchone()
            if existing:
                did = existing['department_id']
            else:
                cur.execute(
                    "INSERT INTO departments (university_id, name, category) VALUES (?,?,?)",
                    (uid, dname, dcat)
                )
                did = cur.lastrowid
            cur.execute(
                "INSERT OR IGNORE INTO admissions_cutoffs (department_id, admission_type, year, cutoff_value, source) VALUES (?,?,?,?,?)",
                (did, 'naesin', 2024, json.dumps({'naesin_avg': naesin_cut, 'notes': '내신 평균 등급 기준'}), 'manual')
            )
            cur.execute(
                "INSERT OR IGNORE INTO admissions_cutoffs (department_id, admission_type, year, cutoff_value, source) VALUES (?,?,?,?,?)",
                (did, 'holistic', 2024,
                 json.dumps({'activity_score_min': hol_score_min, 'notes': '학종 활동점수 기준'}), 'manual')
            )
    con.commit()


def _seed_demo_data(cur, con):
    today = datetime.date.today()
    for student_id in [1, 2, 3]:
        subj_rows = cur.execute("SELECT subject_id FROM subjects LIMIT 8").fetchall()
        subj_ids = [r['subject_id'] for r in subj_rows]
        term = cur.execute("SELECT term_id FROM terms WHERE school_year=2024 AND grade_level=2 AND semester=1").fetchone()
        if term:
            tid = term['term_id']
            base_grade = [2, 3, 4][student_id - 1]
            for i, sid in enumerate(subj_ids):
                g = min(9, max(1, base_grade + (i % 3) - 1))
                cur.execute(
                    "INSERT OR IGNORE INTO student_grades (student_id,term_id,subject_id,grade_level_num,entered_by) VALUES (?,?,?,?,'student')",
                    (student_id, tid, sid, g)
                )
        term2 = cur.execute("SELECT term_id FROM terms WHERE school_year=2024 AND grade_level=2 AND semester=2").fetchone()
        if term2:
            tid2 = term2['term_id']
            base_grade = [2, 3, 4][student_id - 1]
            for i, sid in enumerate(subj_ids[:6]):
                g = min(9, max(1, base_grade + (i % 2)))
                cur.execute(
                    "INSERT OR IGNORE INTO student_grades (student_id,term_id,subject_id,grade_level_num,entered_by) VALUES (?,?,?,?,'student')",
                    (student_id, tid2, sid, g)
                )

        act_type = cur.execute("SELECT activity_type_id FROM activity_types WHERE name='동아리'").fetchone()
        if act_type:
            cur.execute("""
                INSERT OR IGNORE INTO student_activities
                (student_id,activity_type_id,title,summary,detail,learned,role,major_related,start_date,end_date,hours,tags)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (student_id, act_type['activity_type_id'],
                  f'수학탐구동아리(데모{student_id})', '수학 심화 탐구 활동',
                  '매주 수요일 수학 문제 풀이 및 토론', '협동의 중요성을 배웠습니다',
                  '팀원', 1, '2024-03-01', '2024-12-31', 40.0,
                  json.dumps(['수학', '탐구', '협동'])))

        for d in range(30, 0, -1):
            dt = (today - datetime.timedelta(days=d)).isoformat()
            import random
            minutes = random.randint(60, 240)
            cur.execute(
                "INSERT OR IGNORE INTO daily_learning_logs (student_id,date,study_minutes,study_subject_ids,study_type) VALUES (?,?,?,?,'concept')",
                (student_id, dt, minutes, json.dumps(subj_ids[:3]))
            )
            focus = random.randint(2, 5)
            stress = random.randint(1, 4)
            fatigue = random.randint(1, 4)
            motivation = random.randint(2, 5)
            cur.execute(
                "INSERT OR IGNORE INTO daily_state_checks (student_id,date,focus,stress,fatigue,motivation) VALUES (?,?,?,?,?,?)",
                (student_id, dt, focus, stress, fatigue, motivation)
            )
            perf = random.randint(1, 4)
            under = random.randint(1, 3)
            cur.execute(
                "INSERT OR IGNORE INTO daily_self_assessments (student_id,date,performance_level,understanding_level) VALUES (?,?,?,?)",
                (student_id, dt, perf, under)
            )
    con.commit()


# ─────────────────────────────────────────────────────────
# 로그인
# ─────────────────────────────────────────────────────────

def get_edu_user(login_id: str, password: str):
    con = get_connection()
    row = con.execute(
        "SELECT * FROM edu_users WHERE login_id=? AND password=?", (login_id, password)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def get_edu_student_by_user_id(user_id: int):
    con = get_connection()
    row = con.execute("SELECT * FROM edu_students WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def get_linked_students(user_id: int, relation: str):
    con = get_connection()
    rows = con.execute("""
        SELECT es.*, eu.name as student_name
        FROM edu_student_links l
        JOIN edu_students es ON l.student_id = es.student_id
        JOIN edu_users eu ON es.user_id = eu.user_id
        WHERE l.user_id=? AND l.relation=? AND l.is_active=1
    """, (user_id, relation)).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────
# 과목 / 학기
# ─────────────────────────────────────────────────────────

def get_subjects():
    con = get_connection()
    rows = con.execute("SELECT * FROM subjects WHERE is_active=1 ORDER BY subject_id").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_terms():
    con = get_connection()
    rows = con.execute("SELECT * FROM terms ORDER BY school_year DESC, grade_level, semester").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_activity_types():
    con = get_connection()
    rows = con.execute("SELECT * FROM activity_types WHERE is_active=1 ORDER BY activity_type_id").fetchall()
    con.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────
# 내신 성적 CRUD
# ─────────────────────────────────────────────────────────

def save_grade(student_id, term_id, subject_id, grade_level_num, raw_score=None, rank_in_class=None, entered_by='student'):
    con = get_connection()
    con.execute("""
        INSERT INTO student_grades (student_id,term_id,subject_id,grade_level_num,raw_score,rank_in_class,entered_by)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(student_id,term_id,subject_id) DO UPDATE SET
            grade_level_num=excluded.grade_level_num,
            raw_score=excluded.raw_score,
            rank_in_class=excluded.rank_in_class,
            entered_by=excluded.entered_by
    """, (student_id, term_id, subject_id, grade_level_num, raw_score, rank_in_class, entered_by))
    con.commit()
    con.close()


def get_grades(student_id, term_id=None):
    con = get_connection()
    if term_id:
        rows = con.execute("""
            SELECT g.*, s.subject_name, s.category, t.school_year, t.grade_level, t.semester
            FROM student_grades g
            JOIN subjects s ON g.subject_id=s.subject_id
            JOIN terms t ON g.term_id=t.term_id
            WHERE g.student_id=? AND g.term_id=?
            ORDER BY s.subject_id
        """, (student_id, term_id)).fetchall()
    else:
        rows = con.execute("""
            SELECT g.*, s.subject_name, s.category, t.school_year, t.grade_level, t.semester
            FROM student_grades g
            JOIN subjects s ON g.subject_id=s.subject_id
            JOIN terms t ON g.term_id=t.term_id
            WHERE g.student_id=?
            ORDER BY t.school_year DESC, t.grade_level, t.semester, s.subject_id
        """, (student_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_naesin_avg(student_id):
    con = get_connection()
    row = con.execute(
        "SELECT AVG(grade_level_num) as avg FROM student_grades WHERE student_id=?",
        (student_id,)
    ).fetchone()
    con.close()
    if row and row['avg'] is not None:
        return round(row['avg'], 2)
    return None


def verify_grade(grade_id, teacher_id_user):
    con = get_connection()
    con.execute(
        "UPDATE student_grades SET verified_by_teacher=1, verified_at=CURRENT_TIMESTAMP WHERE grade_id=?",
        (grade_id,)
    )
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────
# 활동 CRUD
# ─────────────────────────────────────────────────────────

def save_activity(student_id, activity_type_id, title, summary, detail, learned,
                  role, major_related, start_date, end_date, hours, evidence_url, tags_list):
    con = get_connection()
    con.execute("""
        INSERT INTO student_activities
        (student_id,activity_type_id,title,summary,detail,learned,role,major_related,
         start_date,end_date,hours,evidence_url,tags)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (student_id, activity_type_id, title, summary, detail, learned,
          role, 1 if major_related else 0, start_date, end_date, hours,
          evidence_url, json.dumps(tags_list, ensure_ascii=False)))
    con.commit()
    con.close()


def get_activities(student_id):
    con = get_connection()
    rows = con.execute("""
        SELECT a.*, at.name as type_name
        FROM student_activities a
        JOIN activity_types at ON a.activity_type_id=at.activity_type_id
        WHERE a.student_id=?
        ORDER BY a.created_at DESC
    """, (student_id,)).fetchall()
    con.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d['tags'] = json.loads(d['tags']) if d['tags'] else []
        except Exception:
            d['tags'] = []
        result.append(d)
    return result


def get_activity_strength(student_id):
    acts = get_activities(student_id)
    if not acts:
        return 0.0
    type_set = set(a['activity_type_id'] for a in acts)
    major_cnt = sum(1 for a in acts if a['major_related'])
    total_hours = sum(a['hours'] or 0 for a in acts)
    reviews = get_activity_reviews_for_student(student_id)
    approved = [r for r in reviews if r['status'] == 'approved']
    avg_score = sum(r['score'] or 50 for r in approved) / len(approved) if approved else 50.0
    score = (len(acts) * 5) + (len(type_set) * 8) + (major_cnt * 6) + min(total_hours * 0.3, 20) + (avg_score * 0.2)
    return round(min(score, 100.0), 1)


def get_activity_reviews_for_student(student_id):
    con = get_connection()
    rows = con.execute("""
        SELECT r.*, a.title, a.student_id
        FROM teacher_activity_reviews r
        JOIN student_activities a ON r.activity_id=a.activity_id
        WHERE a.student_id=?
    """, (student_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_activity_review(activity_id, teacher_user_id, status, score, comment):
    con = get_connection()
    con.execute("""
        INSERT INTO teacher_activity_reviews (activity_id, teacher_id, status, score, comment, reviewed_at)
        VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id, teacher_id) DO UPDATE SET
            status=excluded.status, score=excluded.score,
            comment=excluded.comment, reviewed_at=CURRENT_TIMESTAMP
    """, (activity_id, teacher_user_id, status, score, comment))
    con.commit()
    con.close()


def get_pending_activities_for_teacher(teacher_user_id):
    con = get_connection()
    rows = con.execute("""
        SELECT a.activity_id, a.student_id, a.title, a.summary, a.detail, a.learned,
               a.role, a.major_related, a.start_date, a.end_date, a.hours, a.evidence_url,
               a.tags, a.created_at,
               at.name as type_name, eu.name as student_name,
               r.status as review_status, r.score as review_score, r.comment as review_comment
        FROM student_activities a
        JOIN activity_types at ON a.activity_type_id = at.activity_type_id
        JOIN edu_students es   ON a.student_id = es.student_id
        JOIN edu_users eu       ON es.user_id = eu.user_id
        LEFT JOIN teacher_activity_reviews r
               ON r.activity_id = a.activity_id AND r.teacher_id = ?
        WHERE a.student_id IN (
            SELECT DISTINCT l.student_id FROM edu_student_links l
            WHERE l.user_id = ? AND l.relation = 'teacher' AND l.is_active = 1
        )
        ORDER BY a.created_at DESC
    """, (teacher_user_id, teacher_user_id)).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────
# 매일 기록
# ─────────────────────────────────────────────────────────

def save_learning_log(student_id, date, study_minutes, subject_ids, study_type):
    con = get_connection()
    con.execute("""
        INSERT INTO daily_learning_logs (student_id,date,study_minutes,study_subject_ids,study_type)
        VALUES (?,?,?,?,?)
        ON CONFLICT(student_id,date) DO UPDATE SET
            study_minutes=excluded.study_minutes,
            study_subject_ids=excluded.study_subject_ids,
            study_type=excluded.study_type
    """, (student_id, date, study_minutes, json.dumps(subject_ids), study_type))
    con.commit()
    con.close()


def save_state_check(student_id, date, focus, stress, fatigue, motivation):
    con = get_connection()
    con.execute("""
        INSERT INTO daily_state_checks (student_id,date,focus,stress,fatigue,motivation)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(student_id,date) DO UPDATE SET
            focus=excluded.focus, stress=excluded.stress,
            fatigue=excluded.fatigue, motivation=excluded.motivation
    """, (student_id, date, focus, stress, fatigue, motivation))
    con.commit()
    con.close()


def save_self_assessment(student_id, date, performance_level, understanding_level):
    con = get_connection()
    con.execute("""
        INSERT INTO daily_self_assessments (student_id,date,performance_level,understanding_level)
        VALUES (?,?,?,?)
        ON CONFLICT(student_id,date) DO UPDATE SET
            performance_level=excluded.performance_level,
            understanding_level=excluded.understanding_level
    """, (student_id, date, performance_level, understanding_level))
    con.commit()
    con.close()


def get_learning_logs(student_id, days=30):
    con = get_connection()
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = con.execute(
        "SELECT * FROM daily_learning_logs WHERE student_id=? AND date>=? ORDER BY date",
        (student_id, since)
    ).fetchall()
    con.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d['study_subject_ids'] = json.loads(d['study_subject_ids']) if d['study_subject_ids'] else []
        except Exception:
            d['study_subject_ids'] = []
        result.append(d)
    return result


def get_state_checks(student_id, days=30):
    con = get_connection()
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = con.execute(
        "SELECT * FROM daily_state_checks WHERE student_id=? AND date>=? ORDER BY date",
        (student_id, since)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_self_assessments(student_id, days=30):
    con = get_connection()
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = con.execute(
        "SELECT * FROM daily_self_assessments WHERE student_id=? AND date>=? ORDER BY date",
        (student_id, since)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def check_today_logs(student_id):
    today = datetime.date.today().isoformat()
    con = get_connection()
    log = con.execute(
        "SELECT 1 FROM daily_learning_logs WHERE student_id=? AND date=?", (student_id, today)
    ).fetchone()
    state = con.execute(
        "SELECT 1 FROM daily_state_checks WHERE student_id=? AND date=?", (student_id, today)
    ).fetchone()
    assess = con.execute(
        "SELECT 1 FROM daily_self_assessments WHERE student_id=? AND date=?", (student_id, today)
    ).fetchone()
    con.close()
    return {
        'learning': bool(log),
        'state': bool(state),
        'assessment': bool(assess),
    }


# ─────────────────────────────────────────────────────────
# 대학 / 학과 조회
# ─────────────────────────────────────────────────────────

def get_universities(degree_type=None, region_code=None):
    con = get_connection()
    q = "SELECT * FROM universities WHERE 1=1"
    params = []
    if degree_type:
        q += " AND degree_type=?"
        params.append(degree_type)
    if region_code:
        q += " AND region_code=?"
        params.append(region_code)
    rows = con.execute(q, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_departments(university_id=None, category=None):
    con = get_connection()
    q = "SELECT d.*, u.name as university_name, u.degree_type, u.region_code, u.homepage_url FROM departments d JOIN universities u ON d.university_id=u.university_id WHERE 1=1"
    params = []
    if university_id:
        q += " AND d.university_id=?"
        params.append(university_id)
    if category:
        q += " AND d.category=?"
        params.append(category)
    rows = con.execute(q, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_cutoffs(department_id, admission_type, year=2024):
    con = get_connection()
    row = con.execute(
        "SELECT * FROM admissions_cutoffs WHERE department_id=? AND admission_type=? AND year=?",
        (department_id, admission_type, year)
    ).fetchone()
    con.close()
    if row:
        d = dict(row)
        try:
            d['cutoff_value'] = json.loads(d['cutoff_value'])
        except Exception:
            d['cutoff_value'] = {}
        return d
    return None


# ─────────────────────────────────────────────────────────
# 스냅샷 저장/조회
# ─────────────────────────────────────────────────────────

def save_snapshot(student_id, track, results_list, filters_dict=None, mode='demo_instant'):
    today = datetime.date.today().isoformat()
    con = get_connection()
    con.execute("""
        INSERT INTO student_recommendation_snapshots
        (student_id, date, track, mode, filters, results, generated_by)
        VALUES (?,?,?,?,?,?,'rules')
    """, (student_id, today, track, mode,
          json.dumps(filters_dict or {}, ensure_ascii=False),
          json.dumps(results_list, ensure_ascii=False)))
    con.commit()
    con.close()


def get_latest_snapshot(student_id, track, date=None):
    con = get_connection()
    if date:
        row = con.execute(
            "SELECT * FROM student_recommendation_snapshots WHERE student_id=? AND track=? AND date=? ORDER BY created_at DESC LIMIT 1",
            (student_id, track, date)
        ).fetchone()
    else:
        row = con.execute(
            "SELECT * FROM student_recommendation_snapshots WHERE student_id=? AND track=? ORDER BY date DESC, created_at DESC LIMIT 1",
            (student_id, track)
        ).fetchone()
    con.close()
    if row:
        d = dict(row)
        try:
            d['results'] = json.loads(d['results'])
            d['filters'] = json.loads(d['filters'])
        except Exception:
            d['results'] = []
            d['filters'] = {}
        return d
    return None


# ─────────────────────────────────────────────────────────
# 예측 저장/조회
# ─────────────────────────────────────────────────────────

def save_forecast(student_id, metric, window, value_dict, confidence, disclaimer):
    today = datetime.date.today().isoformat()
    con = get_connection()
    con.execute("""
        INSERT INTO student_forecasts (student_id,date,metric,window,value,confidence_level,disclaimer)
        VALUES (?,?,?,?,?,?,?)
    """, (student_id, today, metric, window,
          json.dumps(value_dict, ensure_ascii=False), confidence, disclaimer))
    con.commit()
    con.close()


def get_latest_forecasts(student_id):
    con = get_connection()
    rows = con.execute("""
        SELECT f1.*
        FROM student_forecasts f1
        INNER JOIN (
            SELECT metric, window, MAX(created_at) as max_at
            FROM student_forecasts WHERE student_id=?
            GROUP BY metric, window
        ) f2 ON f1.metric=f2.metric AND f1.window=f2.window AND f1.created_at=f2.max_at
        WHERE f1.student_id=?
        ORDER BY f1.metric, f1.window
    """, (student_id, student_id)).fetchall()
    con.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d['value'] = json.loads(d['value'])
        except Exception:
            d['value'] = {}
        result.append(d)
    return result


# ─────────────────────────────────────────────────────────
# 교사 - 학급 학생 전체 조회
# ─────────────────────────────────────────────────────────

def get_class_students(teacher_user_id):
    con = get_connection()
    rows = con.execute("""
        SELECT es.student_id, eu.name as student_name, es.grade_level, es.track_preference
        FROM edu_student_links l
        JOIN edu_students es ON l.student_id=es.student_id
        JOIN edu_users eu ON es.user_id=eu.user_id
        WHERE l.user_id=? AND l.relation='teacher' AND l.is_active=1
        ORDER BY eu.name
    """, (teacher_user_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────
# 정책 집계
# ─────────────────────────────────────────────────────────

def compute_policy_aggregates(region_code=None, school_id=None):
    con = get_connection()
    today = datetime.date.today().isoformat()
    since30 = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

    q_students = "SELECT es.student_id FROM edu_students es WHERE 1=1"
    params = []
    if school_id:
        q_students += " AND es.school_id=?"
        params.append(school_id)
    elif region_code:
        q_students += " AND es.region_code=?"
        params.append(region_code)

    students = con.execute(q_students, params).fetchall()
    total = len(students)
    if total == 0:
        con.close()
        return {}

    student_ids = [s['student_id'] for s in students]
    ph = ','.join('?' * len(student_ids))

    log_today = con.execute(
        f"SELECT COUNT(DISTINCT student_id) as c FROM daily_learning_logs WHERE student_id IN ({ph}) AND date=?",
        student_ids + [today]
    ).fetchone()['c']

    state_today = con.execute(
        f"SELECT COUNT(DISTINCT student_id) as c FROM daily_state_checks WHERE student_id IN ({ph}) AND date=?",
        student_ids + [today]
    ).fetchone()['c']

    act_students = con.execute(
        f"SELECT COUNT(DISTINCT student_id) as c FROM student_activities WHERE student_id IN ({ph})",
        student_ids
    ).fetchone()['c']

    avg_grade_row = con.execute(
        f"SELECT AVG(grade_level_num) as avg FROM student_grades WHERE student_id IN ({ph})",
        student_ids
    ).fetchone()
    avg_grade = round(avg_grade_row['avg'], 2) if avg_grade_row and avg_grade_row['avg'] else None

    dist_rows = con.execute(
        f"SELECT grade_level_num, COUNT(*) as cnt FROM student_grades WHERE student_id IN ({ph}) GROUP BY grade_level_num",
        student_ids
    ).fetchall()
    grade_dist = {str(r['grade_level_num']): r['cnt'] for r in dist_rows}

    avg_log_row = con.execute(
        f"SELECT AVG(study_minutes) as avg FROM daily_learning_logs WHERE student_id IN ({ph}) AND date>=?",
        student_ids + [since30]
    ).fetchone()
    avg_study = round(avg_log_row['avg'] or 0, 1)

    track_rows = con.execute(
        f"SELECT track_preference, COUNT(*) as cnt FROM edu_students WHERE student_id IN ({ph}) GROUP BY track_preference",
        student_ids
    ).fetchall()
    track_dist = {r['track_preference']: r['cnt'] for r in track_rows}

    risk_rows = con.execute(
        f"""SELECT COUNT(*) as c FROM daily_state_checks
            WHERE student_id IN ({ph}) AND date>=?
            AND (stress>=4 OR fatigue>=4 OR motivation<=2)
            GROUP BY student_id
        """, student_ids + [since30]
    ).fetchall()
    risk_count = len(risk_rows)

    metrics = {
        'total_students': total,
        'log_input_rate_today': round(log_today / total * 100, 1),
        'state_input_rate_today': round(state_today / total * 100, 1),
        'activity_participation_rate': round(act_students / total * 100, 1),
        'naesin_avg': avg_grade,
        'naesin_grade_distribution': grade_dist,
        'avg_study_minutes_30d': avg_study,
        'track_preference_distribution': track_dist,
        'risk_student_count': risk_count,
        'risk_rate': round(risk_count / total * 100, 1),
    }
    con.close()
    return metrics


def get_policy_aggregates_history(region_code=None, days=30):
    con = get_connection()
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    q = "SELECT * FROM policy_aggregates_daily WHERE date>=?"
    params = [since]
    if region_code:
        q += " AND region_code=?"
        params.append(region_code)
    q += " ORDER BY date"
    rows = con.execute(q, params).fetchall()
    con.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d['metrics'] = json.loads(d['metrics'])
        except Exception:
            d['metrics'] = {}
        result.append(d)
    return result


def save_policy_aggregate(region_code, school_id, metrics):
    today = datetime.date.today().isoformat()
    con = get_connection()
    con.execute(
        "INSERT INTO policy_aggregates_daily (date,region_code,school_id,metrics) VALUES (?,?,?,?)",
        (today, region_code, school_id, json.dumps(metrics, ensure_ascii=False))
    )
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────
# CSV Import
# ─────────────────────────────────────────────────────────

def import_universities_from_df(df):
    con = get_connection()
    inserted = 0
    for _, row in df.iterrows():
        try:
            con.execute(
                "INSERT OR IGNORE INTO universities (name,degree_type,region_code,homepage_url) VALUES (?,?,?,?)",
                (str(row.get('name', '')), str(row.get('degree_type', 'four_year')),
                 str(row.get('region_code', '')), str(row.get('homepage_url', '')))
            )
            inserted += 1
        except Exception:
            pass
    con.commit()
    con.close()
    return inserted


def import_departments_from_df(df):
    con = get_connection()
    inserted = 0
    for _, row in df.iterrows():
        try:
            uni = con.execute("SELECT university_id FROM universities WHERE name=?",
                              (str(row.get('university_name', '')),)).fetchone()
            if not uni:
                continue
            con.execute(
                "INSERT OR IGNORE INTO departments (university_id,name,category,department_url) VALUES (?,?,?,?)",
                (uni['university_id'], str(row.get('name', '')),
                 str(row.get('category', '기타')), str(row.get('department_url', '')))
            )
            inserted += 1
        except Exception:
            pass
    con.commit()
    con.close()
    return inserted


def import_cutoffs_from_df(df):
    con = get_connection()
    inserted = 0
    for _, row in df.iterrows():
        try:
            dept = con.execute("""
                SELECT d.department_id FROM departments d
                JOIN universities u ON d.university_id=u.university_id
                WHERE u.name=? AND d.name=?
            """, (str(row.get('university_name', '')), str(row.get('department_name', '')))).fetchone()
            if not dept:
                continue
            val = json.dumps({'naesin_avg': float(row.get('naesin_avg', 3.0)),
                              'notes': str(row.get('notes', ''))})
            con.execute(
                "INSERT OR IGNORE INTO admissions_cutoffs (department_id,admission_type,year,cutoff_value,source) VALUES (?,?,?,?,'manual')",
                (dept['department_id'], str(row.get('admission_type', 'naesin')),
                 int(row.get('year', 2024)), val)
            )
            inserted += 1
        except Exception:
            pass
    con.commit()
    con.close()
    return inserted
