import pytest
from app import create_app
from repositories.db_pool import db_pool
from repositories.fees import FeeRepository

@pytest.fixture
def admin_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
        yield client

@pytest.fixture
def faculty_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "faculty"
            sess["role"] = "faculty"
            sess["faculty_id"] = 1
        yield client

def test_admin_create_faculty(admin_client):
    email = "newprof99@sims.edu"
    # Clean up before
    db_pool.execute_dml("DELETE FROM app_user WHERE username = 'newprof99'")
    db_pool.execute_dml("DELETE FROM faculty WHERE email = %s", (email,))

    payload = {
        "first_name": "Alan",
        "last_name": "Turing",
        "email": email,
        "phone": "9998887771",
        "dept_id": 1,
        "designation": "Professor",
        "salary": 140000,
        "hire_date": "2026-02-01",
        "initial_password": "turingpass123",
        "status": "Active"
    }
    res = admin_client.post("/api/faculty/create", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "faculty_id" in data

    # Verify app_user was provisioned
    user = db_pool.execute_query("SELECT * FROM app_user WHERE username = 'newprof99'", fetch="one")
    assert user is not None
    assert user["role"] == "faculty"

def test_admin_create_course(admin_client):
    code = "CS999"
    db_pool.execute_dml("DELETE FROM course WHERE course_code = %s", (code,))

    payload = {
        "course_code": code,
        "title": "Quantum Relational Databases",
        "credits": 4,
        "dept_id": 1,
        "semester_no": 7
    }
    res = admin_client.post("/api/courses/create", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Verify course exists
    c = db_pool.execute_query("SELECT * FROM course WHERE course_code = %s", (code,), fetch="one")
    assert c is not None
    assert c["title"] == "Quantum Relational Databases"

def test_faculty_create_student(faculty_client):
    roll = "99FACSTU01"
    db_pool.execute_dml("DELETE FROM student WHERE roll_no = %s", (roll,))

    payload = {
        "roll_no": roll,
        "first_name": "Grace",
        "last_name": "Hopper",
        "email": "ghopper99@sims.edu",
        "phone": "9988776655",
        "dob": "2004-12-09",
        "gender": "Female",
        "address": "Campus North",
        "dept_id": 1,
        "admission_date": "2025-08-01",
        "current_semester": 1,
        "status": "Active"
    }
    res = faculty_client.post("/api/students/create", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    stu = db_pool.execute_query("SELECT * FROM student WHERE roll_no = %s", (roll,), fetch="one")
    assert stu is not None
    assert stu["first_name"] == "Grace"

def test_admin_reset_student_password(admin_client):
    # Reset password for student_id = 1
    res = admin_client.post("/api/users/reset-password", json={
        "user_type": "student",
        "target_id": 1,
        "new_password": "newpassStudent123!"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Verify login with new password
    login_res = admin_client.post("/api/auth/login", json={
        "username": "student",
        "password": "newpassStudent123!"
    })
    assert login_res.status_code == 200
    assert login_res.get_json()["success"] is True

def test_admin_reset_faculty_password(admin_client):
    # Reset password for faculty_id = 1
    res = admin_client.post("/api/users/reset-password", json={
        "user_type": "faculty",
        "target_id": 1,
        "new_password": "newpassFaculty123!"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Verify login with new password
    login_res = admin_client.post("/api/auth/login", json={
        "username": "faculty",
        "password": "newpassFaculty123!"
    })
    assert login_res.status_code == 200
    assert login_res.get_json()["success"] is True

def test_admin_set_fee_structure(admin_client):
    payload = {
        "dept_id": 1,
        "semester_no": 8,
        "amount": 72500
    }
    res = admin_client.post("/api/fees/structure/save", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Verify fee structure updated
    fs = db_pool.execute_query("SELECT amount FROM fee_structure WHERE dept_id = 1 AND semester_no = 8", fetch="one")
    assert fs is not None
    assert float(fs["amount"]) == 72500.0

def test_missing_fee_structures_query():
    missing = FeeRepository.get_missing_fee_structures()
    assert isinstance(missing, list)

def test_unpaid_students_query():
    unpaid = FeeRepository.get_unpaid_students()
    assert isinstance(unpaid, list)
