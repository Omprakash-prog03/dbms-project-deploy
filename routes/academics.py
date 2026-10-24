from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from routes.auth import login_required, role_required
from repositories.faculty import FacultyRepository
from repositories.courses import CourseRepository
from repositories.departments import DepartmentRepository

academics_bp = Blueprint("academics", __name__)

@academics_bp.route("/faculty")
@login_required
@role_required("admin", "faculty")
def faculty_view():
    dept_id = request.args.get("dept_id", None, type=int)
    faculty_list = FacultyRepository.get_all(dept_id=dept_id)
    departments = FacultyRepository.get_departments()
    return render_template("academics/faculty.html", faculty_list=faculty_list, departments=departments, dept_id=dept_id)

@academics_bp.route("/departments")
@login_required
def departments_view():
    departments = FacultyRepository.get_departments()
    return render_template("academics/departments.html", departments=departments, faculty=FacultyRepository.get_all())

@academics_bp.route("/courses")
@login_required
def courses_view():
    dept_id = request.args.get("dept_id", None, type=int)
    semester_no = request.args.get("semester_no", None, type=int)
    search = request.args.get("search", "").strip()[:100]
    courses = CourseRepository.get_all(dept_id=dept_id, semester_no=semester_no, search=search)
    departments = FacultyRepository.get_departments()
    return render_template("academics/courses.html", courses=courses, departments=departments, dept_id=dept_id, semester_no=semester_no, search=search)

@academics_bp.route("/offerings")
@login_required
@role_required("admin", "faculty")
def offerings_view():
    years = CourseRepository.get_academic_years()
    academic_year = request.args.get("academic_year", years[0] if years else "")
    term = request.args.get("term", None)
    offerings = CourseRepository.get_offerings(academic_year=academic_year, term=term)
    courses = CourseRepository.get_all()
    faculty_list = FacultyRepository.get_all()

    return render_template(
        "academics/offerings.html",
        offerings=offerings,
        courses=courses,
        faculty_list=faculty_list,
        academic_year=academic_year,
        years=years,
        term=term
    )

@academics_bp.route("/api/courses/create", methods=["POST"])
@login_required
@role_required("admin")
def create_course_api():
    data = request.get_json(silent=True) or request.form
    try:
        new_id = CourseRepository.create(
            course_code=data["course_code"].strip().upper(),
            title=data["title"].strip(),
            credits=int(data["credits"]),
            dept_id=int(data["dept_id"]),
            semester_no=int(data["semester_no"])
        )
        return jsonify({"success": True, "course_id": new_id, "message": f"Course '{data['course_code'].strip().upper()}' added successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@academics_bp.route("/api/faculty/create", methods=["POST"])
@login_required
@role_required("admin")
def create_faculty_api():
    data = request.get_json(silent=True) or request.form
    try:
        new_id = FacultyRepository.create(
            first_name=data["first_name"].strip(),
            last_name=data["last_name"].strip(),
            email=data["email"].strip().lower(),
            phone=data["phone"].strip(),
            dept_id=int(data["dept_id"]),
            designation=data.get("designation", "Assistant Professor"),
            hire_date=data.get("hire_date", "2026-01-01").strip(),
            salary=float(data["salary"]),
            status=data.get("status", "Active"),
            initial_password=data.get("initial_password", "")
        )
        return jsonify({"success": True, "faculty_id": new_id, "message": f"Faculty member '{data['first_name']} {data['last_name']}' appointed successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@academics_bp.route("/api/offerings/create", methods=["POST"])
@login_required
@role_required("admin")
def create_offering():
    data = request.get_json(silent=True) or request.form
    try:
        new_id = CourseRepository.create_offering(
            course_id=int(data["course_id"]),
            faculty_id=int(data["faculty_id"]),
            academic_year=data["academic_year"].strip(),
            term=data["term"].strip(),
            capacity=int(data["capacity"])
        )
        return jsonify({"success": True, "offering_id": new_id, "message": "Offering opened successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@academics_bp.route('/api/departments/create', methods=['POST'])
@academics_bp.route('/api/departments/update/<int:dept_id>', methods=['POST'])
@login_required
@role_required('admin')
def save_department_api(dept_id=None):
    data = request.get_json(silent=True) or request.form
    try:
        saved_id = DepartmentRepository.save(
            data.get('dept_code'), data.get('dept_name'), data.get('established_year'),
            dept_id=dept_id, hod_faculty_id=data.get('hod_faculty_id'),
        )
        return jsonify(success=True, dept_id=saved_id, message='Department saved successfully.')
    except (ValueError, TypeError) as error:
        return jsonify(success=False, message=str(error)), 400
    except Exception:
        return jsonify(success=False, message='Department could not be saved. Check that its code and name are unique.'), 400
