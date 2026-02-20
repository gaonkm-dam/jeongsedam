import sys
import importlib.util

print("Python 모듈 체크...")
print(f"Python 버전: {sys.version}")

modules = ['streamlit', 'openai', 'pandas', 'sqlite3']
for module in modules:
    try:
        if module == 'sqlite3':
            import sqlite3
            print(f"✓ {module}: 설치됨 (내장)")
        else:
            spec = importlib.util.find_spec(module)
            if spec:
                print(f"✓ {module}: 설치됨")
            else:
                print(f"✗ {module}: 미설치")
    except Exception as e:
        print(f"✗ {module}: 오류 - {e}")

print("\n파일 체크...")
import os
files = ['app.py', 'database.py', 'openai_helper.py', 'requirements.txt']
for file in files:
    if os.path.exists(file):
        print(f"✓ {file}: 존재")
    else:
        print(f"✗ {file}: 없음")

print("\n데이터베이스 체크...")
import database
database.init_database()
conn = database.get_connection()
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"테이블 수: {len(tables)}")
for table in tables:
    print(f"  - {table[0]}")

print("\n학생 데이터 체크...")
students = conn.execute('SELECT * FROM students').fetchall()
print(f"학생 수: {len(students)}")

print("\n✅ 모든 기본 체크 완료!")
