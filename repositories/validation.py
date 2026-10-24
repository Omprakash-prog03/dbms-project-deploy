"""Shared input rules, independent of browser validation and database engine."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation


def student_fields(data, existing=None):
    source = {**(existing or {}), **dict(data)}
    result = {}
    for name, limit in [('first_name', 80), ('last_name', 80), ('email', 150), ('phone', 20)]:
        value = str(source.get(name) or '').strip()
        if not value or len(value) > limit:
            raise ValueError(f'Please enter a valid {name.replace("_", " ")} (up to {limit} characters).')
        result[name] = value
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result['email']):
        raise ValueError('Please enter a valid email address.')
    if not re.fullmatch(r'[+\d ()-]{7,20}', result['phone']):
        raise ValueError('Please enter a valid phone number.')
    result['email'] = result['email'].lower()
    for field in ('dob', 'admission_date'):
        try:
            result[field] = date.fromisoformat(str(source.get(field, ''))).isoformat()
        except ValueError:
            raise ValueError(f'Please enter a valid {field.replace("_", " ")} (YYYY-MM-DD).')
    birth = date.fromisoformat(result['dob'])
    admission = date.fromisoformat(result['admission_date'])
    age = admission.year - birth.year - ((admission.month, admission.day) < (birth.month, birth.day))
    if age < 15 or birth > date.today():
        raise ValueError('Students must be at least 15 years old on their admission date.')
    result['dept_id'] = int(source['dept_id'])
    result['current_semester'] = int(source.get('current_semester', 1))
    if result['dept_id'] <= 0 or not 1 <= result['current_semester'] <= 8:
        raise ValueError('Choose a department and a semester between 1 and 8.')
    result['gender'] = source.get('gender', 'Other')
    result['status'] = source.get('status', 'Active')
    if result['gender'] not in ('Male', 'Female', 'Other') or result['status'] not in ('Active','Graduated','Suspended','Dropped'):
        raise ValueError('Choose a valid gender and student status.')
    result['address'] = str(source.get('address') or '').strip()[:500]
    if not existing:
        result['roll_no'] = str(source.get('roll_no', '')).strip().upper()
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_/-]{1,29}', result['roll_no']):
            raise ValueError('Use 2–30 letters, digits, dashes, or slashes for the roll number.')
    return result


def money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Enter a valid payment amount.')
    if not amount.is_finite() or amount <= 0 or amount > Decimal('99999999.99'):
        raise ValueError('Amount must be a finite positive value below 100 million.')
    if amount.as_tuple().exponent < -2:
        raise ValueError('Use at most two decimal places for currency.')
    return amount.quantize(Decimal('0.01'))
