"""Regressions for the redesigned workspace and the data-integrity fixes."""
import csv
import io
import datetime
import math
import uuid
import pytest
from app import create_app
from repositories.db_pool import db_pool
from repositories.students import StudentRepository
from repositories.attendance import AttendanceRepository
from repositories.results import ResultRepository
from repositories.fees import FeeRepository
from repositories.admissions import AdmissionsRepository
from repositories.dashboard import DashboardRepository

@pytest.fixture
def admin():
    app = create_app({'TESTING':True, 'SECRET_KEY':'workspace-tests', 'CSRF_ENABLED':False})
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update(user_id=1, username='admin', role='admin')
        yield client

@pytest.fixture
def student():
    app = create_app({'TESTING':True, 'SECRET_KEY':'workspace-tests', 'CSRF_ENABLED':False})
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update(user_id=3, username='student', role='student', student_id=1)
        yield client

@pytest.mark.parametrize('path', ['/students','/fees','/attendance','/results','/enrollments','/insights','/admissions','/faculty','/api/dashboard/stats','/api/dashboard/export-students','/api/admissions/pending','/api/inspect-sql','/api/search?q=Aarav'])
def test_student_cannot_read_staff_data(student, path):
    assert student.get(path).status_code == 403

@pytest.mark.parametrize('path', ['/api/students/create','/api/attendance/mark','/api/results/save','/api/enrollments/enroll','/api/fees/pay','/api/fees/structure/save','/api/admissions/approve','/api/users/reset-password','/api/insights/transaction-demo'])
def test_student_cannot_mutate_staff_data(student, path):
    assert student.post(path, json={}).status_code == 403

def test_student_owns_profile(student):
    assert student.get('/students/1').status_code == 200
    assert student.get('/students/2').status_code == 403
    assert student.get('/dashboard').location.endswith('/students/1')
    assert b'Back to Student Directory' not in student.get('/students/1').data

@pytest.mark.parametrize('path', ['/api/inspect-sql','/api/search?q=a','/api/dashboard/stats'])
def test_anonymous_api_denied(path):
    client = create_app({'TESTING':True}).test_client()
    assert client.get(path).status_code == 401

def test_login_fails_closed_for_invalid_hash(monkeypatch):
    original = db_pool.execute_query
    def query(sql, params=None, fetch='all'):
        if 'SELECT * FROM app_user' in sql:
            return {'user_id': 9999, 'username':'broken', 'password_hash':'not-a-valid-hash', 'role':'admin'}
        return original(sql,params,fetch)
    monkeypatch.setattr(db_pool,'execute_query',query)
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    response = client.post('/api/auth/login',json={'username':'broken','password':'admin123'})
    assert response.status_code == 401
    with client.session_transaction() as session:
        assert 'user_id' not in session

def test_csrf_and_token_rotation():
    client = create_app({'TESTING':True,'CSRF_ENABLED':True,'SECRET_KEY':'csrf-tests'}).test_client()
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf_token']
    payload = {'username':'admin','password':'admin123'}
    assert client.post('/api/auth/login',json=payload).status_code == 400
    assert client.post('/api/auth/login',json=payload,headers={'X-CSRF-Token':'wrong'}).status_code == 400
    assert client.post('/api/auth/login',json=payload,headers={'X-CSRF-Token':token}).status_code == 200
    with client.session_transaction() as session:
        assert token != session['csrf_token']
        new_token = session['csrf_token']
    assert client.get('/logout').status_code == 405
    assert client.post('/logout',headers={'X-CSRF-Token':new_token}).status_code == 302
    assert client.get('/api/dashboard/stats').status_code == 401

def test_sql_inspection_is_session_scoped(admin):
    admin.get('/students?search=trace-one-secret')
    first_trace = admin.get('/api/inspect-sql').get_json()
    assert 'trace-one-secret' in str(first_trace)
    other = admin.application.test_client()
    with other.session_transaction() as session:
        session.update(user_id=1,username='admin',role='admin')
    assert other.get('/api/inspect-sql').get_json()['queries'] == []

def test_password_hash_queries_never_logged():
    from repositories.db_pool import clear_last_queries, record_last_query, get_last_queries
    clear_last_queries()
    record_last_query('UPDATE app_user SET password_hash=%s',('secret-hash',))
    assert get_last_queries() == []

@pytest.mark.parametrize('page', [0,-1,-500,9999999])
def test_pagination_clamps_to_valid_pages(page):
    data = StudentRepository.get_all(page=page,per_page=15)
    assert 1 <= data['page'] <= data['pages']
    assert data['items']

def test_edit_data_and_full_name_search(admin):
    result = StudentRepository.get_all(search='Aarav Sharma')
    assert result['total'] == 1
    assert result['items'][0]['dob'] == '2005-04-12'
    assert result['items'][0]['address']
    response = admin.get('/api/search?q=Aarav%20Sharma').get_json()
    assert response['results'][0]['url'] == '/students/1'
    assert admin.get('/courses?search=CS202').status_code == 200
    assert b'Database Management Systems' in admin.get('/courses?search=CS202').data
    assert b'Engineering Thermodynamics' not in admin.get('/courses?search=CS202').data

def test_export_honors_filters_and_has_all_rows(admin):
    response = admin.get('/api/dashboard/export-students?dept_id=1&status=Active')
    rows = list(csv.DictReader(io.StringIO(response.data.decode())))
    expected = StudentRepository.get_all(dept_id=1,status='Active',per_page=None)
    assert len(rows) == expected['total']
    assert all(r['Department']=='CSE' and r['Status']=='Active' for r in rows)
    all_rows = list(csv.DictReader(io.StringIO(admin.get('/api/dashboard/export-students').data.decode())))
    assert len(all_rows) == db_pool.execute_query('SELECT COUNT(*) FROM student',fetch='val')

@pytest.mark.parametrize('value',['=1+1','+CMD','-12','@SUM(A1)','  =HYPERLINK("x")','\t=1+1'])
def test_csv_formula_cells_are_neutralized(value):
    from routes.dashboard import safe_csv
    assert safe_csv(value).startswith("'")

def test_chart_years_and_stats_are_live(admin):
    year = datetime.date.today().year
    data = admin.get(f'/api/dashboard/chart?year={year}').get_json()
    assert len(data['labels']) == len(data['admissions']) == len(data['enrollments']) == 12
    assert sum(data['admissions']) == db_pool.execute_query('SELECT COUNT(*) FROM student WHERE YEAR(admission_date)=%s',(year,),fetch='val')
    assert admin.get('/api/dashboard/chart?year=-5').status_code == 400
    stats = DashboardRepository.get_stats()
    assert stats['total_students'] == db_pool.execute_query('SELECT COUNT(*) FROM student',fetch='val')
    assert 0 <= stats['attendance_pct'] <= 100

@pytest.mark.parametrize('path', ['/api/enrollments/enroll','/api/attendance/mark','/api/results/save','/api/fees/pay','/api/fees/structure/save','/api/admissions/approve'])
def test_invalid_api_input_returns_400_not_500(admin,path):
    response = admin.post(path,json={})
    assert response.status_code == 400
    assert response.is_json

def test_exam_selector_cannot_mix_offerings(admin):
    exams = db_pool.execute_query('SELECT exam_id, offering_id FROM exam ORDER BY exam_id')
    first = exams[0]
    other = next(exam for exam in exams if exam['offering_id'] != first['offering_id'])
    page = admin.get(f"/results?offering_id={first['offering_id']}&exam_id={other['exam_id']}")
    assert page.status_code == 200
    assert f"exam_id: {other['exam_id']}".encode() not in page.data

def test_faculty_cannot_write_another_instructors_class():
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2,role='faculty',username='faculty',faculty_id=1)
    offering = db_pool.execute_query('SELECT offering_id FROM course_offering WHERE faculty_id != 1 LIMIT 1',fetch='val')
    assert client.post('/api/attendance/mark',json={'offering_id':offering,'class_date':'2026-01-01','records':[]}).status_code == 403
    assert client.get(f'/results?offering_id={offering}').status_code == 403

@pytest.mark.parametrize('marks',[float('nan'),float('inf'),-1])
def test_nonfinite_and_negative_marks_rejected(marks):
    with pytest.raises(ValueError):
        ResultRepository.save_result(1,1,marks)

def test_result_rejects_cross_course_enrollment():
    exam = db_pool.execute_query('SELECT exam_id, offering_id FROM exam LIMIT 1',fetch='one')
    enrollment = db_pool.execute_query("SELECT enrollment_id FROM enrollment WHERE offering_id != %s AND status='Enrolled' LIMIT 1",(exam['offering_id'],),fetch='val')
    with pytest.raises(ValueError,match='offering'):
        ResultRepository.save_result(exam['exam_id'],enrollment,10)

def test_attendance_cross_course_batch_rolls_back():
    first = db_pool.execute_query("SELECT enrollment_id,offering_id FROM enrollment WHERE status='Enrolled' LIMIT 1",fetch='one')
    second = db_pool.execute_query("SELECT enrollment_id FROM enrollment WHERE status='Enrolled' AND offering_id != %s LIMIT 1",(first['offering_id'],),fetch='val')
    day = '2026-01-03'
    records = [{'enrollment_id':first['enrollment_id'],'status':'Present'},{'enrollment_id':second,'status':'Present'}]
    with pytest.raises(ValueError):
        AttendanceRepository.save_batch(first['offering_id'],day,records)
    assert db_pool.execute_query('SELECT COUNT(*) FROM attendance WHERE enrollment_id=%s AND class_date=%s',(first['enrollment_id'],day),fetch='val') == 0

def test_attendance_rejects_future_date():
    future = (datetime.date.today()+datetime.timedelta(days=1)).isoformat()
    with pytest.raises(ValueError,match='future'):
        AttendanceRepository.save_batch(1,future,[{'enrollment_id':1,'status':'Present'}])

@pytest.mark.parametrize('amount',['NaN','Infinity','-1','0','1.001'])
def test_invalid_payment_values_rejected(amount):
    assert FeeRepository.record_payment(1,1,amount,'UPI','TEST-BAD')['status_code'] == 400

def test_duplicate_rejection_does_not_rewrite_review():
    email = f'test-{uuid.uuid4().hex}@example.com'
    application = AdmissionsRepository.create_application('Review Once',email,'9876543210',1)
    try:
        assert AdmissionsRepository.reject_admission(application)['status_code'] == 200
        assert AdmissionsRepository.reject_admission(application)['status_code'] == 409
        assert AdmissionsRepository.approve_admission(application)['status_code'] == 400
    finally:
        db_pool.execute_dml('DELETE FROM admission_application WHERE application_id=%s',(application,))

@pytest.mark.parametrize('percentage,grade',[(None,None),(95,'A+'),(80,'A'),(70,'B+'),(60,'B'),(50,'C'),(40,'P'),(39,'F')])
def test_grade_scale_is_consistent(percentage,grade):
    assert db_pool._fn_grade(percentage) == grade

def test_true_standard_deviation():
    value = db_pool.execute_query('SELECT STDDEV(x) FROM (SELECT 1 AS x UNION ALL SELECT 2 UNION ALL SELECT 3)',fetch='val')
    assert value == pytest.approx(math.sqrt(2/3))


def test_approval_requires_real_dob_and_generates_unique_password(admin):
    import bcrypt
    application_id = AdmissionsRepository.create_application('New Chapter', f'new-{uuid.uuid4().hex}@example.com', '9876543210', 1)
    student_id = None
    try:
        missing = admin.post('/api/admissions/approve',json={'application_id':application_id})
        assert missing.status_code == 400
        underage = admin.post('/api/admissions/approve',json={'application_id':application_id,'dob':'2020-01-01'})
        assert underage.status_code == 400
        response = admin.post('/api/admissions/approve',json={'application_id':application_id,'dob':'2004-07-18','address':'Test address'})
        assert response.status_code == 200
        data = response.get_json()
        student = db_pool.execute_query('SELECT * FROM student WHERE roll_no=%s',(data['roll_no'],),fetch='one')
        student_id = student['student_id']
        assert student['dob'] == '2004-07-18'
        assert student['address'] == 'Test address'
        user = db_pool.execute_query('SELECT password_hash FROM app_user WHERE username=%s',(data['username'],),fetch='one')
        assert data['temporary_password'] != 'student123'
        assert bcrypt.checkpw(data['temporary_password'].encode(),user['password_hash'].encode())
        assert not bcrypt.checkpw(b'student123',user['password_hash'].encode())
        assert admin.post('/api/admissions/approve',json={'application_id':application_id,'dob':'2004-07-18'}).status_code == 400
        assert admin.post('/api/admissions/reject',json={'application_id':application_id}).status_code == 409
    finally:
        if student_id:
            db_pool.execute_dml('DELETE FROM student WHERE student_id=%s',(student_id,))
        db_pool.execute_dml('DELETE FROM admission_application WHERE application_id=%s',(application_id,))


def test_reactivating_enrollment_cannot_overbook():
    offering = db_pool.execute_dml("INSERT INTO course_offering(course_id,faculty_id,academic_year,term,capacity,enrolled_count) VALUES(1,1,%s,'Fall',1,0)",(f'QA-{uuid.uuid4().hex[:6]}',))['lastrowid']
    students = db_pool.execute_query("SELECT student_id FROM student WHERE status='Active' LIMIT 2")
    try:
        first = db_pool.execute_dml("INSERT INTO enrollment(student_id,offering_id,enroll_date,status) VALUES(%s,%s,'2026-01-01','Enrolled')",(students[0]['student_id'],offering))['lastrowid']
        db_pool.execute_dml("UPDATE enrollment SET status='Dropped' WHERE enrollment_id=%s",(first,))
        db_pool.execute_dml("INSERT INTO enrollment(student_id,offering_id,enroll_date,status) VALUES(%s,%s,'2026-01-01','Enrolled')",(students[1]['student_id'],offering))
        with pytest.raises(Exception,match='capacity'):
            db_pool.execute_dml("UPDATE enrollment SET status='Enrolled' WHERE enrollment_id=%s",(first,))
        assert db_pool.execute_query('SELECT enrolled_count FROM course_offering WHERE offering_id=%s',(offering,),fetch='val') == 1
    finally:
        db_pool.execute_dml('DELETE FROM enrollment WHERE offering_id=%s',(offering,))
        db_pool.execute_dml('DELETE FROM course_offering WHERE offering_id=%s',(offering,))


def test_cgpa_weights_courses_once_by_credits():
    key = uuid.uuid4().hex[:8]
    student_id = StudentRepository.create('QA'+key.upper(),'Grade','Test',f'{key}@example.com','9876543210','2004-01-01','Other','Campus',1,'2026-01-01')
    courses, offerings, enrollments = [], [], []
    try:
        for i, (credits, marks) in enumerate([(1,[90]),(6,[50,50,50])]):
            course = db_pool.execute_dml('INSERT INTO course(course_code,title,credits,dept_id,semester_no) VALUES(%s,%s,%s,1,1)',(f'Q{key}{i}', 'CGPA regression', credits))['lastrowid']; courses.append(course)
            offering = db_pool.execute_dml("INSERT INTO course_offering(course_id,faculty_id,academic_year,term,capacity,enrolled_count) VALUES(%s,1,'2026-2027','Fall',5,0)",(course,))['lastrowid']; offerings.append(offering)
            enrollment = db_pool.execute_dml("INSERT INTO enrollment(student_id,offering_id,enroll_date,status) VALUES(%s,%s,'2026-01-01','Enrolled')",(student_id,offering))['lastrowid']; enrollments.append(enrollment)
            for j, mark in enumerate(marks):
                exam = db_pool.execute_dml('INSERT INTO exam(offering_id,exam_type,max_marks,exam_date) VALUES(%s,%s,100,%s)',(offering,['Internal','Midterm','Final'][j],'2026-02-01'))['lastrowid']
                ResultRepository.save_result(exam,enrollment,mark)
        assert db_pool.execute_query('SELECT fn_student_cgpa(%s)',(student_id,),fetch='val') == pytest.approx(6.57)
    finally:
        for offering in offerings:
            db_pool.execute_dml('DELETE FROM result WHERE exam_id IN (SELECT exam_id FROM exam WHERE offering_id=%s)',(offering,))
            db_pool.execute_dml('DELETE FROM exam WHERE offering_id=%s',(offering,))
            db_pool.execute_dml('DELETE FROM enrollment WHERE offering_id=%s',(offering,))
            db_pool.execute_dml('DELETE FROM course_offering WHERE offering_id=%s',(offering,))
        for course in courses:
            db_pool.execute_dml('DELETE FROM course WHERE course_id=%s',(course,))
        db_pool.execute_dml('DELETE FROM student WHERE student_id=%s',(student_id,))

@pytest.mark.parametrize('payload', [[],None,{'username':5,'password':'wrong'}, {'username':'test','password':{}}, {'first_name':True}])
def test_malformed_json_envelope_is_not_a_server_error(payload):
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    response = client.post('/api/auth/login',json=payload)
    assert response.status_code in (400,401)


def test_student_edit_saves_all_visible_fields(admin):
    key = uuid.uuid4().hex[:8]
    payload = {'roll_no':'QA'+key.upper(),'first_name':'Test','last_name':'Learner','email':f'{key}@example.com','phone':'9876543210','dob':'2004-01-01','gender':'Other','address':'Original address','dept_id':1,'admission_date':'2026-01-01','current_semester':1,'status':'Active'}
    created = admin.post('/api/students/create',json=payload)
    assert created.status_code == 200
    student_id = created.get_json()['student_id']
    try:
        updates = {**payload,'first_name':'Updated','last_name':"D’Souza",'dob':'2003-02-03','gender':'Female','address':'New campus address','dept_id':2,'admission_date':'2026-02-01','current_semester':2}
        response = admin.post(f'/api/students/update/{student_id}',json=updates)
        assert response.status_code == 200
        stored = StudentRepository.get_by_id(student_id)
        for field in ('first_name','last_name','dob','gender','address','dept_id','admission_date','current_semester'):
            assert stored[field] == updates[field]
        assert admin.post(f'/api/students/update/{student_id}',json={**updates,'dob':'2020-01-01'}).status_code == 400
        assert StudentRepository.get_by_id(student_id)['dob'] == '2003-02-03'
    finally:
        assert admin.post(f'/api/students/delete/{student_id}').status_code == 200
        assert StudentRepository.get_by_id(student_id) is None


def test_faculty_stats_exclude_financial_totals():
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2,username='faculty',role='faculty',faculty_id=1)
    stats = client.get('/api/dashboard/stats').get_json()
    assert 'total_collected' not in stats
    assert 'payment_count' not in stats
    assert b'Fee Ledger & Payment Summary' not in client.get('/students/1').data


@pytest.fixture
def payment_student():
    key = uuid.uuid4().hex[:8]
    student_id = StudentRepository.create('PAY'+key.upper(),'Payment','Test',f'{key}@example.com','9876543210','2004-01-01','Other','Campus',1,'2026-01-01',1)
    try:
        yield student_id
    finally:
        payments = FeeRepository.get_all_payments(student_id)
        for payment in payments:
            db_pool.execute_dml("DELETE FROM audit_log WHERE table_name='fee_payment' AND record_id=%s", (payment['payment_id'],))
        db_pool.execute_dml('DELETE FROM fee_payment WHERE student_id=%s', (student_id,))
        StudentRepository.delete(student_id)


def test_payment_positive_partial_full_duplicate_and_atomicity(admin, payment_student):
    from decimal import Decimal
    fee = Decimal(str(db_pool.execute_query('SELECT amount FROM fee_structure WHERE dept_id=1 AND semester_no=1',fetch='val')))
    receipt = 'QA-'+uuid.uuid4().hex
    payload = {'student_id':payment_student,'semester_no':1,'amount':'123.45','mode':'UPI','receipt_no':receipt}
    response = admin.post('/api/fees/pay',json=payload)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['receipt_no'] == receipt
    payment = FeeRepository.get_all_payments(payment_student)[0]
    assert Decimal(str(payment['amount'])) == Decimal('123.45')
    assert db_pool.execute_query("SELECT COUNT(*) FROM audit_log WHERE table_name='fee_payment' AND record_id=%s",(payment['payment_id'],),fetch='val') == 1
    assert admin.post('/api/fees/pay',json=payload).status_code == 409
    assert len(FeeRepository.get_all_payments(payment_student)) == 1
    partial = StudentRepository.get_fee_summary(payment_student)[0]
    assert partial['payment_status'] == 'Partial'
    assert Decimal(str(partial['balance_due'])).quantize(Decimal('.01')) == fee - Decimal('123.45')
    assert admin.post('/api/fees/pay',json={**payload,'receipt_no':'x'*51}).status_code == 400
    response = admin.post('/api/fees/pay',json={**payload,'amount':str(fee-Decimal('123.45')),'receipt_no':''})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['receipt_no'].startswith('REC-')
    assert StudentRepository.get_fee_summary(payment_student)[0]['payment_status'] == 'Fully Paid'
    assert admin.post('/api/fees/pay',json={**payload,'amount':'0.01','receipt_no':receipt+'x'}).status_code == 400
    assert len(FeeRepository.get_all_payments(payment_student)) == 2


def test_concurrent_payments_cannot_overpay(payment_student):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    fee = db_pool.execute_query('SELECT amount FROM fee_structure WHERE dept_id=1 AND semester_no=1',fetch='val')
    barrier = Barrier(2)
    def pay(_):
        barrier.wait(timeout=10)
        return FeeRepository.record_payment(payment_student,1,fee,'Card','RACE-'+uuid.uuid4().hex)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(pay,range(2)))
    assert sorted(r['status_code'] for r in results) == [200,400], results
    assert len(FeeRepository.get_all_payments(payment_student)) == 1
    assert db_pool.execute_query('SELECT SUM(amount) FROM fee_payment WHERE student_id=%s',(payment_student,),fetch='val') == fee


def test_fee_structure_cannot_be_lowered_below_payments(payment_student):
    original = db_pool.execute_query('SELECT amount FROM fee_structure WHERE dept_id=1 AND semester_no=1',fetch='val')
    assert FeeRepository.record_payment(payment_student,1,original,'Cash','FEE-'+uuid.uuid4().hex)['status_code'] == 200
    with pytest.raises(ValueError,match='lower'):
        FeeRepository.set_fee_structure(1,1,'1.00')
    assert db_pool.execute_query('SELECT amount FROM fee_structure WHERE dept_id=1 AND semester_no=1',fetch='val') == original
    assert FeeRepository.set_fee_structure(1,1,original)


def test_currency_rounding_marks_decimal_installments_fully_paid(payment_student):
    from decimal import Decimal
    dept = db_pool.execute_dml('INSERT INTO department (dept_code,dept_name,established_year) VALUES (%s,%s,2020)',('Q'+uuid.uuid4().hex[:7],'Currency test'))['lastrowid']
    try:
        db_pool.execute_dml('UPDATE student SET dept_id=%s WHERE student_id=%s',(dept,payment_student))
        FeeRepository.set_fee_structure(dept,1,'0.80')
        for amount in ('0.10','0.70'):
            response = FeeRepository.record_payment(payment_student,1,amount,'Cash','CENTS-'+uuid.uuid4().hex)
            assert response['status_code'] == 200, response
        profile = StudentRepository.get_fee_summary(payment_student)[0]
        ledger = db_pool.execute_query('SELECT * FROM v_fee_status WHERE student_id=%s',(payment_student,),fetch='one')
        for summary in (profile, ledger):
            assert summary['payment_status'] == 'Fully Paid'
            assert summary['balance_due'] == 0
            assert summary['is_defaulter'] == 0
            assert Decimal(str(summary['total_paid'])) == Decimal('0.80')
        assert FeeRepository.set_fee_structure(dept,1,'0.80')
    finally:
        db_pool.execute_dml("DELETE FROM audit_log WHERE table_name='fee_payment' AND record_id IN (SELECT payment_id FROM fee_payment WHERE student_id=%s)",(payment_student,))
        db_pool.execute_dml('DELETE FROM fee_payment WHERE student_id=%s',(payment_student,))
        db_pool.execute_dml('UPDATE student SET dept_id=1 WHERE student_id=%s',(payment_student,))
        db_pool.execute_dml('DELETE FROM department WHERE dept_id=%s',(dept,))


def test_profile_cannot_relabel_or_hide_recorded_payments(admin, payment_student):
    db_pool.execute_dml('UPDATE student SET current_semester=2 WHERE student_id=%s',(payment_student,))
    assert FeeRepository.record_payment(payment_student,2,'1.00','Cash','PROFILE-'+uuid.uuid4().hex)['status_code'] == 200
    assert admin.post(f'/api/students/update/{payment_student}',json={'dept_id':2}).status_code == 400
    assert admin.post(f'/api/students/update/{payment_student}',json={'current_semester':1}).status_code == 400
    # The database guard also protects direct SQL and closes the check/update race.
    with pytest.raises(Exception,match='payments'):
        db_pool.execute_dml('UPDATE student SET dept_id=2 WHERE student_id=%s',(payment_student,))
    assert StudentRepository.get_by_id(payment_student)['dept_id'] == 1
    assert StudentRepository.get_by_id(payment_student)['current_semester'] == 2


def test_embedded_cookie_is_partitioned_secure_and_still_requires_csrf():
    client = create_app({'TESTING':True,'CSRF_ENABLED':True,'SESSION_COOKIE_SECURE':True,'SESSION_COOKIE_SAMESITE':'None','SESSION_COOKIE_PARTITIONED':True}).test_client()
    response = client.get('/login')
    cookie = response.headers['Set-Cookie']
    for attribute in ('Secure','HttpOnly','SameSite=None','Partitioned'):
        assert attribute in cookie
    assert client.post('/api/auth/login',json={'username':'admin','password':'admin123'}).status_code == 400
