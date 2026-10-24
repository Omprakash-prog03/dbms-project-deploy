from flask import Blueprint, request, jsonify, session, render_template
from routes.auth import login_required, role_required
from repositories.admissions import AdmissionsRepository
from repositories.faculty import FacultyRepository

admissions_bp = Blueprint('admissions', __name__)

@admissions_bp.route('/admissions')
@login_required
@role_required('admin', 'faculty')
def admissions_view():
    status = request.args.get('status', 'Pending')
    if status not in ('All', 'Pending', 'Approved', 'Rejected'):
        status = 'Pending'
    search = request.args.get('search', '').strip()[:100]
    return render_template('admissions/index.html', applications=AdmissionsRepository.get_all(status, search), status=status, search=search, departments=FacultyRepository.get_departments())

@admissions_bp.route('/api/admissions/pending')
@login_required
@role_required('admin', 'faculty')
def get_pending():
    return jsonify(AdmissionsRepository.get_pending())

@admissions_bp.route('/api/admissions/approve', methods=['POST'])
@login_required
@role_required('admin', 'faculty')
def approve():
    data = request.get_json(silent=True) or request.form
    app_id = int(data.get('application_id'))
    result = AdmissionsRepository.approve_admission(
        app_id, reviewer_id=session.get('faculty_id'), date_of_birth=data.get('dob'),
        address=data.get('address', ''), password=data.get('password') or None,
    )
    return jsonify(success=result['status_code']==200, message=result['message'], roll_no=result.get('roll_no'),
                   username=result.get('username'), temporary_password=result.get('temporary_password'),
                   password_generated=result.get('password_generated')), result['status_code']

@admissions_bp.route('/api/admissions/reject', methods=['POST'])
@login_required
@role_required('admin', 'faculty')
def reject():
    data = request.get_json(silent=True) or request.form
    result = AdmissionsRepository.reject_admission(int(data.get('application_id')), reviewer_id=session.get('faculty_id'))
    return jsonify(success=result['status_code']==200, message=result['message']), result['status_code']


@admissions_bp.route('/api/admissions/create', methods=['POST'])
@login_required
@role_required('admin', 'faculty')
def create_application():
    data = request.get_json(silent=True) or request.form
    try:
        application_id = AdmissionsRepository.create_application(
            data.get('applicant_name', ''), data.get('email', ''),
            data.get('phone', ''), data.get('dept_id'),
        )
        return jsonify(success=True, application_id=application_id, message='Application added for review.')
    except (ValueError, TypeError) as error:
        return jsonify(success=False, message=str(error)), 400
