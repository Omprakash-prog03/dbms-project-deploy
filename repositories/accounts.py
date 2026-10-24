"""Portal account helpers: manual passwords and one account per person."""
import re
import bcrypt
from repositories.db_pool import db_pool


def sql(statement):
    return statement if db_pool.is_mysql else statement.replace('%s', '?')


def validate_password(password, label='Password'):
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError(f'{label} must be at least 8 characters long.')
    if len(password.encode('utf-8')) > 72:
        raise ValueError(f'{label} must be at most 72 UTF-8 bytes (bcrypt limit).')
    return password


def hash_password(password):
    return bcrypt.hashpw(validate_password(password).encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def unique_username(preferred, cursor):
    """Return a free username, suffixing the preferred base if it is taken."""
    base = re.sub(r'[^a-z0-9._-]+', '.', str(preferred).strip().lower()).strip('.') or 'user'
    base = base[:45]
    candidate, counter = base, 1
    while True:
        cursor.execute(sql('SELECT user_id FROM app_user WHERE LOWER(username)=LOWER(%s)'), (candidate,))
        if not cursor.fetchone():
            return candidate
        counter += 1
        candidate = f'{base}{counter}'


def create_account(cursor, username, password, role, student_id=None, faculty_id=None):
    password_hash = hash_password(password)
    final_name = unique_username(username, cursor)
    cursor.execute(
        sql("INSERT INTO app_user (username, password_hash, role, student_id, faculty_id) VALUES (%s, %s, %s, %s, %s)"),
        (final_name, password_hash, role, student_id, faculty_id),
    )
    return final_name
