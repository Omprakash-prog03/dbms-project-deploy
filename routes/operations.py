import datetime
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, abort
from routes.auth import login_required, role_required
from repositories.enrollments import EnrollmentRepository
from repositories.attendance import AttendanceRepository
from repositories.results import ResultRepository
from repositories.courses import CourseRepository
from repositories.students import StudentRepository

operations_bp = Blueprint("operations", __name__)

def available_offerings():
    offerings = CourseRepository.get_offerings()
    if session.get("role") == "faculty":
        offerings = [o for o in offerings if o["faculty_id"] == session.get("faculty_id")]
    return offerings


def check_offering(offering_id):
    offering = CourseRepository.get_offering_by_id(offering_id)
    if not offering:
        abort(404, description="Course offering not found.")
    if session.get("role") == "faculty" and offering["faculty_id"] != session.get("faculty_id"):
        abort(403, description="You can only manage your own course offerings.")
    return offering


# ============================================================================
# ENROLLMENTS
# ============================================================================
@operations_bp.route("/enrollments")
@login_required
@role_required("admin", "faculty")
def enrollments_view():
    offering_id = request.args.get("offering_id", None, type=int)
    student_id = request.args.get("student_id", None, type=int)
    if offering_id:
        check_offering(offering_id)
    enrollments = EnrollmentRepository.get_all(offering_id=offering_id, student_id=student_id)
    if session.get("role") == "faculty":
        allowed = {o["offering_id"] for o in available_offerings()}
        enrollments = [e for e in enrollments if e["offering_id"] in allowed]
    offerings = available_offerings()
    students = StudentRepository.get_all(per_page=None)["items"]

    return render_template(
        "operations/enrollments.html",
        enrollments=enrollments,
        offerings=offerings,
        students=students,
        offering_id=offering_id,
        student_id=student_id
    )

@operations_bp.route("/api/enrollments/enroll", methods=["POST"])
@login_required
@role_required("admin", "faculty")
def enroll_student_api():
    data = request.get_json(silent=True) or request.form
    student_id = int(data.get("student_id"))
    offering_id = int(data.get("offering_id"))

    check_offering(offering_id)
    res = EnrollmentRepository.enroll_student(student_id, offering_id)
    if res["status_code"] == 200:
        return jsonify({"success": True, "message": res["message"]})
    else:
        return jsonify({"success": False, "message": res["message"]}), res["status_code"]

# ============================================================================
# ATTENDANCE
# ============================================================================
@operations_bp.route("/attendance")
@login_required
@role_required("admin", "faculty")
def attendance_view():
    offerings = available_offerings()
    default_off_id = offerings[0]["offering_id"] if offerings else 0
    offering_id = request.args.get("offering_id", default_off_id, type=int)
    class_date = request.args.get("class_date", datetime.date.today().isoformat())

    try:
        class_date = datetime.date.fromisoformat(class_date).isoformat()
    except ValueError:
        abort(400, description="Choose a valid class date.")
    current_offering = check_offering(offering_id) if offering_id else None
    roster = AttendanceRepository.get_class_roster(offering_id, class_date)
    summary = AttendanceRepository.get_summary_by_offering(offering_id)

    return render_template(
        "operations/attendance.html",
        offerings=offerings,
        current_offering=current_offering,
        offering_id=offering_id,
        class_date=class_date,
        roster=roster,
        summary=summary
    )

@operations_bp.route("/api/attendance/mark", methods=["POST"])
@login_required
@role_required("admin", "faculty")
def mark_attendance_api():
    data = request.get_json(silent=True) or {}
    offering_id = int(data.get("offering_id"))
    class_date = data.get("class_date")
    records = data.get("records", [])

    check_offering(offering_id)
    try:
        res = AttendanceRepository.save_batch(offering_id, class_date, records)
        return jsonify({"success": True, "message": f"Successfully recorded attendance for {res['count']} students."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

# ============================================================================
# RESULTS & GRADEBOOK
# ============================================================================
@operations_bp.route("/results")
@login_required
@role_required("admin", "faculty")
def results_view():
    offerings = available_offerings()
    default_off_id = offerings[0]["offering_id"] if offerings else 0
    offering_id = request.args.get("offering_id", default_off_id, type=int)

    current_offering = check_offering(offering_id) if offering_id else None
    exams = ResultRepository.get_exams_by_offering(offering_id)
    default_exam_id = exams[0]["exam_id"] if exams else None
    exam_id = request.args.get("exam_id", default_exam_id, type=int)
    if exam_id not in {exam["exam_id"] for exam in exams}:
        exam_id = default_exam_id

    gradebook = []
    current_exam = None
    if exam_id:
        gradebook = ResultRepository.get_gradebook_for_exam(exam_id)
        current_exam = ResultRepository.get_exam_by_id(exam_id)

    current_offering = CourseRepository.get_offering_by_id(offering_id)

    return render_template(
        "operations/results.html",
        offerings=offerings,
        current_offering=current_offering,
        offering_id=offering_id,
        exams=exams,
        exam_id=exam_id,
        current_exam=current_exam,
        gradebook=gradebook
    )

@operations_bp.route("/api/results/save", methods=["POST"])
@login_required
@role_required("admin", "faculty")
def save_result_api():
    data = request.get_json(silent=True) or request.form
    exam_id = int(data.get("exam_id"))
    enrollment_id = int(data.get("enrollment_id"))
    marks_obtained = float(data.get("marks_obtained"))

    exam = ResultRepository.get_exam_by_id(exam_id)
    if not exam:
        abort(404, description="Exam not found.")
    check_offering(exam["offering_id"])
    try:
        res_id = ResultRepository.save_result(exam_id, enrollment_id, marks_obtained)
        return jsonify({"success": True, "message": "Mark saved successfully.", "result_id": res_id})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@operations_bp.route('/api/exams/create', methods=['POST'])
@login_required
@role_required('admin', 'faculty')
def create_exam_api():
    data = request.get_json(silent=True) or request.form
    offering_id = int(data.get('offering_id'))
    check_offering(offering_id)
    try:
        exam_id = ResultRepository.create_exam(offering_id, data.get('exam_type'), data.get('max_marks'), data.get('exam_date'))
        return jsonify(success=True, exam_id=exam_id, message='Examination created successfully.')
    except (ValueError, TypeError) as error:
        return jsonify(success=False, message=str(error)), 400
    except Exception:
        return jsonify(success=False, message='The examination could not be created. Check for a duplicate exam type.'), 400
