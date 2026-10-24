"""Department setup for a fresh, unseeded installation."""
import re
from datetime import date
from repositories.db_pool import db_pool


class DepartmentRepository:
    @staticmethod
    def fields(dept_code, dept_name, established_year):
        code = str(dept_code or '').strip().upper()
        name = str(dept_name or '').strip()
        if not re.fullmatch(r'[A-Z][A-Z0-9_-]{0,9}', code):
            raise ValueError('Use a department code of 1–10 letters, digits, dashes, or underscores, starting with a letter.')
        if not name or len(name) > 100:
            raise ValueError('Enter a department name of at most 100 characters.')
        if not re.fullmatch(r'\d{4}', str(established_year)) or not 1900 <= int(established_year) <= date.today().year:
            raise ValueError('Enter an established year between 1900 and the current year.')
        return code, name, int(established_year)

    @staticmethod
    def save(dept_code, dept_name, established_year, dept_id=None, hod_faculty_id=None):
        code, name, year = DepartmentRepository.fields(dept_code, dept_name, established_year)
        hod_id = int(hod_faculty_id) if hod_faculty_id not in (None, '') else None
        with db_pool.get_connection() as conn:
            cursor = conn.cursor()
            def execute(sql, params):
                cursor.execute(sql if db_pool.is_mysql else sql.replace('%s', '?'), params)
            try:
                cursor.execute('START TRANSACTION' if db_pool.is_mysql else 'BEGIN IMMEDIATE')
                if dept_id is not None:
                    execute('SELECT dept_id FROM department WHERE dept_id=%s', (dept_id,))
                    if not cursor.fetchone():
                        raise ValueError('Department not found.')
                execute('SELECT dept_id FROM department WHERE (LOWER(dept_code)=LOWER(%s) OR LOWER(dept_name)=LOWER(%s)) AND dept_id!=%s', (code, name, dept_id or 0))
                if cursor.fetchone():
                    raise ValueError('A department with that code or name already exists.')
                if hod_id:
                    execute("SELECT faculty_id FROM faculty WHERE faculty_id=%s AND dept_id=%s AND status='Active'", (hod_id, dept_id or 0))
                    if not cursor.fetchone():
                        raise ValueError('The head must be an active faculty member of this department.')
                if dept_id is None:
                    execute('INSERT INTO department (dept_code,dept_name,established_year) VALUES (%s,%s,%s)', (code, name, year))
                    dept_id = cursor.lastrowid
                else:
                    execute('UPDATE department SET dept_code=%s,dept_name=%s,established_year=%s,hod_faculty_id=%s WHERE dept_id=%s', (code, name, year, hod_id, dept_id))
                conn.commit()
                return dept_id
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
