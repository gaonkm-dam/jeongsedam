import database

database.init_database()
students = database.get_connection().execute('SELECT * FROM students').fetchall()
print(f'총 학생 수: {len(students)}')
for s in students:
    student_dict = dict(s)
    print(f'ID: {student_dict["id"]}, 이름: {student_dict["name"]}, 로그인: {student_dict["login_id"]}')
