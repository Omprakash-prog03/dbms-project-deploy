import uuid
from flask import Blueprint, render_template, request, jsonify, flash
from routes.auth import login_required, role_required
from repositories.fees import FeeRepository
from repositories.students import StudentRepository
from repositories.faculty import FacultyRepository
from repositories.validation import money

fee_bp = Blueprint("fees", __name__)

@fee_bp.route("/fees")
@login_required
@role_required("admin")
def fees_view():
    tab = request.args.get("tab", "payments")
    payments = FeeRepository.get_all_payments()
    defaulters = FeeRepository.get_defaulters()
    unpaid = FeeRepository.get_unpaid_students()
    structures = FeeRepository.get_fee_structures()
    missing_structures = FeeRepository.get_missing_fee_structures()
    students = StudentRepository.get_all(per_page=None)["items"]
    departments = FacultyRepository.get_departments()

    return render_template(
        "fees/index.html",
        tab=tab,
        payments=payments,
        defaulters=defaulters,
        unpaid=unpaid,
        structures=structures,
        missing_structures=missing_structures,
        students=students,
        departments=departments
    )

@fee_bp.route("/api/fees/pay", methods=["POST"])
@login_required
@role_required("admin")
def record_payment_api():
    data = request.get_json(silent=True) or request.form
    student_id = int(data.get("student_id"))
    semester_no = int(data.get("semester_no"))
    amount = money(data.get("amount"))
    mode = data.get("mode", "UPI")
    receipt_no = data.get("receipt_no", "").strip() or f"REC-{uuid.uuid4().hex[:16].upper()}"

    res = FeeRepository.record_payment(student_id, semester_no, amount, mode, receipt_no)
    if res["status_code"] == 200:
        return jsonify({"success": True, "message": res["message"], "receipt_no": receipt_no})
    else:
        return jsonify({"success": False, "message": res["message"]}), res["status_code"]

@fee_bp.route("/api/fees/structure/save", methods=["POST"])
@login_required
@role_required("admin")
def save_fee_structure_api():
    data = request.get_json(silent=True) or request.form
    dept_id = int(data.get("dept_id"))
    semester_no = int(data.get("semester_no"))
    amount = money(data.get("amount"))

    try:
        FeeRepository.set_fee_structure(dept_id, semester_no, amount)
        return jsonify({"success": True, "message": f"Tuition fee structure for Semester {semester_no} configured to Rs {amount:,.2f}."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
