import os
import sys
import random
import datetime
import bcrypt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from repositories.db_pool import db_pool
from config import Config

def run_seed():
    if Config.APP_ENV == 'production':
        raise RuntimeError('Demo seeding is disabled in production. Use the private setup screens instead.')
    from faker import Faker
    if db_pool.execute_query("SELECT COUNT(*) FROM app_user WHERE username = 'admin'", fetch="val"):
        print("Database already seeded. Existing records and credentials left unchanged.")
        return
    print("=" * 70)
    print("HOGWARDS DEVELOPMENT DATA (Faker Seed: 42)")
    print("=" * 70)

    fake = Faker('en_IN')
    Faker.seed(42)
    random.seed(42)

    # 1. Departments
    print("[1/10] Seeding 6 Academic Departments...")
    departments_data = [
        ("CSE", "Computer Science & Engineering", 1995),
        ("ECE", "Electronics & Communication Engineering", 1998),
        ("MECH", "Mechanical Engineering", 1990),
        ("CIVIL", "Civil Engineering", 1988),
        ("EEE", "Electrical & Electronics Engineering", 1992),
        ("IT", "Information Technology", 2002)
    ]

    dept_ids = []
    for code, name, year in departments_data:
        # Check existing
        existing = db_pool.execute_query("SELECT dept_id FROM department WHERE dept_code = %s", (code,), fetch="one")
        if existing:
            dept_ids.append(existing["dept_id"])
        else:
            res = db_pool.execute_dml(
                "INSERT INTO department (dept_code, dept_name, established_year) VALUES (%s, %s, %s)",
                (code, name, year)
            )
            dept_ids.append(res["lastrowid"])

    # 2. Faculty
    print("[2/10] Seeding 25 Faculty Members & HoD assignments...")
    designations = ["Professor", "Associate Professor", "Assistant Professor", "Lecturer"]
    faculty_ids = []

    # Pre-defined distinguished faculty
    core_faculty = [
        ("Edgar", "Codd", "edgar.codd@sims.edu", "9876540001", dept_ids[0], "Professor", 150000.00),
        ("Alan", "Turing", "alan.turing@sims.edu", "9876540002", dept_ids[0], "Professor", 160000.00),
        ("Claude", "Shannon", "claude.shannon@sims.edu", "9876540003", dept_ids[1], "Professor", 155000.00),
        ("James", "Watt", "james.watt@sims.edu", "9876540004", dept_ids[2], "Professor", 145000.00),
        ("Thomas", "Telford", "thomas.telford@sims.edu", "9876540005", dept_ids[3], "Professor", 140000.00),
        ("Nikola", "Tesla", "nikola.tesla@sims.edu", "9876540006", dept_ids[4], "Professor", 158000.00),
        ("Tim", "Berners-Lee", "tim.bl@sims.edu", "9876540007", dept_ids[5], "Professor", 152000.00)
    ]

    for first, last, email, phone, did, desig, sal in core_faculty:
        existing = db_pool.execute_query("SELECT faculty_id FROM faculty WHERE email = %s", (email,), fetch="one")
        if existing:
            faculty_ids.append(existing["faculty_id"])
        else:
            res = db_pool.execute_dml(
                "INSERT INTO faculty (first_name, last_name, email, phone, dept_id, designation, hire_date, salary, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, '2015-08-01', %s, 'Active')",
                (first, last, email, phone, did, desig, sal)
            )
            faculty_ids.append(res["lastrowid"])

    # Generate additional faculty to reach 25
    while len(faculty_ids) < 25:
        f_name = fake.first_name()
        l_name = fake.last_name()
        email = f"{f_name.lower()}.{l_name.lower()}{random.randint(10,99)}@sims.edu"
        phone = f"98{random.randint(10000000, 99999999)}"
        did = random.choice(dept_ids)
        desig = random.choice(designations)
        sal = round(random.uniform(65000, 130000), 2)
        hire_d = fake.date_between(start_date="-8y", end_date="-1y").isoformat()

        try:
            res = db_pool.execute_dml(
                "INSERT INTO faculty (first_name, last_name, email, phone, dept_id, designation, hire_date, salary, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Active')",
                (f_name, l_name, email, phone, did, desig, hire_d, sal)
            )
            faculty_ids.append(res["lastrowid"])
        except Exception:
            pass

    # Assign HoDs to each department
    for i, did in enumerate(dept_ids):
        # Pick first faculty in that department
        f_row = db_pool.execute_query("SELECT faculty_id FROM faculty WHERE dept_id = %s LIMIT 1", (did,), fetch="one")
        if f_row:
            db_pool.execute_dml("UPDATE department SET hod_faculty_id = %s WHERE dept_id = %s", (f_row["faculty_id"], did))

    # 3. Catalog Courses
    print("[3/10] Seeding 40 Academic Catalog Courses across 8 semesters...")
    courses_spec = [
        # CSE
        ("CS101", "Introduction to Computing", 4, dept_ids[0], 1),
        ("CS102", "Data Structures & Algorithms", 4, dept_ids[0], 2),
        ("CS201", "Discrete Mathematics", 3, dept_ids[0], 3),
        ("CS202", "Database Management Systems", 4, dept_ids[0], 4),
        ("CS301", "Operating Systems", 4, dept_ids[0], 5),
        ("CS302", "Computer Networks", 3, dept_ids[0], 6),
        ("CS401", "Compiler Design", 4, dept_ids[0], 7),
        ("CS402", "Distributed Systems & Cloud", 4, dept_ids[0], 8),
        # ECE
        ("EC101", "Basic Electrical Engineering", 3, dept_ids[1], 1),
        ("EC102", "Semiconductor Devices", 4, dept_ids[1], 2),
        ("EC201", "Digital Logic Design", 4, dept_ids[1], 3),
        ("EC202", "Signals & Linear Systems", 4, dept_ids[1], 4),
        ("EC301", "Microprocessors & Microcontrollers", 4, dept_ids[1], 5),
        ("EC302", "Electromagnetic Wave Propagation", 3, dept_ids[1], 6),
        ("EC401", "VLSI System Design", 4, dept_ids[1], 7),
        ("EC402", "Wireless Communications", 4, dept_ids[1], 8),
        # MECH
        ("ME101", "Engineering Graphics & CAD", 3, dept_ids[2], 1),
        ("ME102", "Engineering Thermodynamics", 4, dept_ids[2], 2),
        ("ME201", "Fluid Mechanics & Hydraulics", 4, dept_ids[2], 3),
        ("ME202", "Strength of Materials", 4, dept_ids[2], 4),
        ("ME301", "Kinematics & Dynamics of Machines", 4, dept_ids[2], 5),
        ("ME302", "Heat & Mass Transfer", 4, dept_ids[2], 6),
        ("ME401", "Manufacturing Technology", 4, dept_ids[2], 7),
        ("ME402", "Automotive Engineering", 3, dept_ids[2], 8),
        # CIVIL
        ("CE101", "Building Materials & Construction", 3, dept_ids[3], 1),
        ("CE102", "Surveying & Geomatics", 4, dept_ids[3], 2),
        ("CE201", "Structural Analysis I", 4, dept_ids[3], 3),
        ("CE202", "Geotechnical Engineering", 4, dept_ids[3], 4),
        ("CE301", "Concrete Technology", 3, dept_ids[3], 5),
        ("CE302", "Transportation Engineering", 4, dept_ids[3], 6),
        ("CE401", "Environmental Engineering", 4, dept_ids[3], 7),
        ("CE402", "Earthquake Resistant Structures", 4, dept_ids[3], 8),
        # EEE
        ("EE101", "Circuit Theory & Analysis", 4, dept_ids[4], 1),
        ("EE201", "Electrical Machines I", 4, dept_ids[4], 3),
        ("EE202", "Power Electronics & Drives", 4, dept_ids[4], 4),
        ("EE301", "Control Systems Engineering", 4, dept_ids[4], 5),
        # IT
        ("IT101", "Object-Oriented Programming in Java", 4, dept_ids[5], 2),
        ("IT201", "Web Architectures & Full-Stack Development", 4, dept_ids[5], 4),
        ("IT301", "Information & Cyber Security", 4, dept_ids[5], 6),
        ("IT401", "Machine Learning & Neural Networks", 4, dept_ids[5], 7)
    ]

    course_ids = []
    for code, title, credits, did, sem in courses_spec:
        existing = db_pool.execute_query("SELECT course_id FROM course WHERE course_code = %s", (code,), fetch="one")
        if existing:
            course_ids.append(existing["course_id"])
        else:
            res = db_pool.execute_dml(
                "INSERT INTO course (course_code, title, credits, dept_id, semester_no) VALUES (%s, %s, %s, %s, %s)",
                (code, title, credits, did, sem)
            )
            course_ids.append(res["lastrowid"])

    # 4. Course Offerings
    print("[4/10] Seeding 60 Course Offerings across Terms...")
    terms = ["Fall", "Spring"]
    years = ["2024-2025", "2025-2026", "2026-2027"]
    offering_ids = []

    for c_id in course_ids:
        # Schedule each course in 2025-2026 Fall or Spring
        c_info = db_pool.execute_query("SELECT dept_id, semester_no FROM course WHERE course_id = %s", (c_id,), fetch="one")
        term = "Fall" if (c_info["semester_no"] % 2 == 1) else "Spring"

        # Pick faculty from that department
        f_pool = db_pool.execute_query("SELECT faculty_id FROM faculty WHERE dept_id = %s", (c_info["dept_id"],), fetch="all")
        fac_id = random.choice(f_pool)["faculty_id"] if f_pool else faculty_ids[0]

        capacity = random.choice([50, 60, 60, 75])

        existing = db_pool.execute_query(
            "SELECT offering_id FROM course_offering WHERE course_id = %s AND academic_year = '2025-2026' AND term = %s",
            (c_id, term), fetch="one"
        )
        if existing:
            offering_ids.append(existing["offering_id"])
        else:
            res = db_pool.execute_dml(
                "INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count) "
                "VALUES (%s, %s, '2025-2026', %s, %s, 0)",
                (c_id, fac_id, term, capacity)
            )
            offering_ids.append(res["lastrowid"])

    # Additional offerings in 2024-2025 for showcase Q23 (EXCEPT demonstration)
    for c_id in course_ids[:20]:
        c_info = db_pool.execute_query("SELECT dept_id, semester_no FROM course WHERE course_id = %s", (c_id,), fetch="one")
        term = "Fall" if (c_info["semester_no"] % 2 == 1) else "Spring"
        f_pool = db_pool.execute_query("SELECT faculty_id FROM faculty WHERE dept_id = %s", (c_info["dept_id"],), fetch="all")
        fac_id = random.choice(f_pool)["faculty_id"] if f_pool else faculty_ids[0]

        try:
            res = db_pool.execute_dml(
                "INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count) "
                "VALUES (%s, %s, '2024-2025', %s, 60, 0)",
                (c_id, fac_id, term)
            )
            offering_ids.append(res["lastrowid"])
        except Exception:
            pass

    # 5. Fee Structures
    print("[5/10] Seeding Fee Structures for all 6 departments (8 semesters each)...")
    base_fees = {
        dept_ids[0]: 55000.0, # CSE
        dept_ids[1]: 50000.0, # ECE
        dept_ids[2]: 48000.0, # MECH
        dept_ids[3]: 45000.0, # CIVIL
        dept_ids[4]: 47000.0, # EEE
        dept_ids[5]: 52000.0  # IT
    }
    for did in dept_ids:
        b_amt = base_fees.get(did, 50000.0)
        for sem in range(1, 9):
            sem_amt = b_amt + (sem * 1000.0) # progressive tuition
            try:
                db_pool.execute_dml(
                    "INSERT INTO fee_structure (dept_id, semester_no, amount) VALUES (%s, %s, %s)",
                    (did, sem, sem_amt)
                )
            except Exception:
                pass

    # 6. Students (320+ Students)
    print("[6/10] Seeding 320+ Students & Emergency Contact Guardians...")
    current_count = db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val") or 0
    students_to_create = max(0, 320 - current_count)
    student_ids = []

    # Ensure demo student exists: 26CSE001 (Aarav Sharma)
    demo_stu = db_pool.execute_query("SELECT student_id FROM student WHERE roll_no = '26CSE001'", fetch="one")
    if not demo_stu:
        res = db_pool.execute_dml(
            """INSERT INTO student (
                roll_no, first_name, last_name, email, phone, dob, gender,
                address, dept_id, admission_date, current_semester, status
            ) VALUES ('26CSE001', 'Aarav', 'Sharma', 'aarav.sharma@sims.edu', '9876500001',
                     '2005-04-12', 'Male', 'Flat 402, Green Park Avenue, New Delhi',
                     %s, '2026-06-10', 4, 'Active')""",
            (dept_ids[0],)
        )
        demo_id = res["lastrowid"]
        student_ids.append(demo_id)
        # Add guardian
        db_pool.execute_dml(
            "INSERT INTO guardian (student_id, name, relation, phone) VALUES (%s, 'Suresh Sharma', 'Father', '9876500002')",
            (demo_id,)
        )
        db_pool.execute_dml(
            "INSERT INTO guardian (student_id, name, relation, phone) VALUES (%s, 'Meena Sharma', 'Mother', '9876500003')",
            (demo_id,)
        )
    else:
        student_ids.append(demo_stu["student_id"])

    students_to_create = max(0, 320 - db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val"))
    # Batch generate students
    for i in range(1, students_to_create + 1):
        did = random.choice(dept_ids)
        d_code = db_pool.execute_query("SELECT dept_code FROM department WHERE dept_id = %s", (did,), fetch="one")["dept_code"]

        sem = random.choices([1, 2, 3, 4, 5, 6, 7, 8], weights=[20, 20, 15, 15, 10, 10, 5, 5])[0]
        adm_year = 2026 - ((sem - 1) // 2)
        year_str = str(adm_year)[2:]
        roll_no = f"{year_str}{d_code}{random.randint(100, 999)}"

        # Guard against duplicate roll_no
        exists = db_pool.execute_query("SELECT student_id FROM student WHERE roll_no = %s", (roll_no,), fetch="one")
        if exists:
            roll_no = f"{year_str}{d_code}{random.randint(1000, 9999)}"

        gender = random.choice(["Male", "Female", "Other"])
        f_name = fake.first_name_male() if gender == "Male" else (fake.first_name_female() if gender == "Female" else fake.first_name())
        l_name = fake.last_name()
        email = f"{f_name.lower()}.{l_name.lower()}{random.randint(1,999)}@sims.edu"
        phone = f"9{random.randint(100000000, 999999999)}"

        # Age >= 15 years constraint
        dob = datetime.date(adm_year - random.randint(18, 23), random.randint(1, 12), random.randint(1, 28)).isoformat()
        adm_date = f"{adm_year}-06-{random.randint(10, 28):02d}"

        # Status distribution (mostly Active, some Suspended/Graduated/Dropped for viva rules)
        if sem == 8:
            status = random.choices(["Active", "Graduated"], weights=[70, 30])[0]
        else:
            status = random.choices(["Active", "Suspended", "Dropped"], weights=[92, 5, 3])[0]

        addr = f"{fake.building_number()}, {fake.street_name()}, {fake.city()}"

        try:
            res = db_pool.execute_dml(
                """INSERT INTO student (
                    roll_no, first_name, last_name, email, phone, dob, gender,
                    address, dept_id, admission_date, current_semester, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (roll_no, f_name, l_name, email, phone, dob, gender, addr, did, adm_date, sem, status)
            )
            s_id = res["lastrowid"]
            student_ids.append(s_id)

            # Add guardian
            g_rel = random.choice(["Father", "Mother", "Guardian"])
            g_name = f"{fake.first_name()} {l_name}"
            db_pool.execute_dml(
                "INSERT INTO guardian (student_id, name, relation, phone) VALUES (%s, %s, %s, %s)",
                (s_id, g_name, g_rel, f"98{random.randint(10000000, 99999999)}")
            )
        except Exception:
            pass

    # Ensure all student IDs in db are captured
    all_s = db_pool.execute_query("SELECT student_id, dept_id, current_semester, status FROM student", fetch="all")
    student_map = {s["student_id"]: s for s in all_s}

    # 7. Enrollments (1600+ Course Enrollments)
    print("[7/10] Seeding 1600+ Enrollments across Active Offerings...")
    current_enr = db_pool.execute_query("SELECT COUNT(*) FROM enrollment", fetch="val") or 0

    # Active 2025-2026 offerings
    active_offerings = db_pool.execute_query(
        "SELECT offering_id, course_id, capacity, enrolled_count FROM course_offering WHERE academic_year = '2025-2026'",
        fetch="all"
    )

    if current_enr < 1500 and active_offerings:
        for s_id, s_info in student_map.items():
            if s_info["status"] != "Active":
                continue
            # Pick 4 to 5 offerings matching the student's department or open electives
            num_courses = random.randint(4, 5)
            candidate_offerings = random.sample(active_offerings, min(num_courses, len(active_offerings)))

            for off in candidate_offerings:
                off_id = off["offering_id"]
                # Check duplicate
                dup = db_pool.execute_query("SELECT enrollment_id FROM enrollment WHERE student_id = %s AND offering_id = %s", (s_id, off_id), fetch="one")
                if not dup:
                    try:
                        db_pool.execute_dml(
                            "INSERT INTO enrollment (student_id, offering_id, enroll_date, status) VALUES (%s, %s, '2025-08-15', 'Enrolled')",
                            (s_id, off_id)
                        )
                    except Exception:
                        pass

    # 8. Exams & Results
    print("[8/10] Seeding Exams (Internal, Midterm, Final) & Results...")
    exam_specs = [
        ("Internal", 30.0, "2025-09-25"),
        ("Midterm", 50.0, "2025-10-20"),
        ("Final", 100.0, "2025-12-15")
    ]

    all_offerings = db_pool.execute_query("SELECT offering_id FROM course_offering", fetch="all")
    for off in all_offerings:
        off_id = off["offering_id"]
        for etype, max_m, edate in exam_specs:
            ex_row = db_pool.execute_query(
                "SELECT exam_id FROM exam WHERE offering_id = %s AND exam_type = %s",
                (off_id, etype), fetch="one"
            )
            if not ex_row:
                try:
                    res = db_pool.execute_dml(
                        "INSERT INTO exam (offering_id, exam_type, max_marks, exam_date) VALUES (%s, %s, %s, %s)",
                        (off_id, etype, max_m, edate)
                    )
                    ex_id = res["lastrowid"]
                except Exception:
                    continue
            else:
                ex_id = ex_row["exam_id"]

            # Grade enrolled students for this exam
            enrs = db_pool.execute_query("SELECT enrollment_id FROM enrollment WHERE offering_id = %s AND status = 'Enrolled' LIMIT 40", (off_id,), fetch="all")
            for e in enrs:
                enr_id = e["enrollment_id"]
                r_exists = db_pool.execute_query("SELECT result_id FROM result WHERE exam_id = %s AND enrollment_id = %s", (ex_id, enr_id), fetch="one")
                if not r_exists:
                    # Score distribution (40% to 98% of max)
                    pct = random.triangular(45.0, 98.0, 75.0)
                    marks = round((pct / 100.0) * max_m, 1)
                    try:
                        db_pool.execute_dml(
                            "INSERT INTO result (exam_id, enrollment_id, marks_obtained) VALUES (%s, %s, %s)",
                            (ex_id, enr_id, marks)
                        )
                    except Exception:
                        pass

    # 9. Attendance (30 Days per Offering)
    print("[9/10] Seeding Daily Classroom Attendance Roll-Calls...")
    cur_att = db_pool.execute_query("SELECT COUNT(*) FROM attendance", fetch="val") or 0
    if cur_att < 3000:
        sample_offerings = all_offerings[:15]
        for off in sample_offerings:
            off_id = off["offering_id"]
            enr_list = db_pool.execute_query("SELECT enrollment_id FROM enrollment WHERE offering_id = %s AND status = 'Enrolled'", (off_id,), fetch="all")
            if not enr_list:
                continue

            # Generate 20 dates
            start_date = datetime.date(2025, 9, 1)
            for d_offset in range(25):
                c_date = (start_date + datetime.timedelta(days=d_offset)).isoformat()
                for enr in enr_list:
                    status = random.choices(["Present", "Late", "Absent"], weights=[85, 10, 5])[0]
                    try:
                        db_pool.execute_dml(
                            "INSERT INTO attendance (enrollment_id, class_date, status) VALUES (%s, %s, %s)",
                            (enr["enrollment_id"], c_date, status)
                        )
                    except Exception:
                        pass

    # 10. Fee Payments & Pending Admissions & Demo Users
    print("[10/10] Seeding Fee Payments, Pending Admissions & 3 System Users...")

    # Payments
    for s_id, s_info in student_map.items():
        if s_info["status"] != "Active":
            continue
        sem = s_info["current_semester"]
        did = s_info["dept_id"]
        fee_struct = db_pool.execute_query("SELECT amount FROM fee_structure WHERE dept_id = %s AND semester_no = %s", (did, sem), fetch="one")
        if not fee_struct:
            continue
        total_due = fee_struct["amount"]

        # 80% paid in full, 10% partial, 10% defaulter (0 paid)
        p_type = random.choices(["full", "partial", "defaulter"], weights=[80, 10, 10])[0]
        if p_type == "full":
            paid_amt = total_due
        elif p_type == "partial":
            paid_amt = round(total_due * 0.40, 2)
        else:
            paid_amt = 0.0

        if paid_amt > 0:
            rec_no = f"REC-2026-{s_id:04d}-{sem}"
            mode = random.choice(["UPI", "Net Banking", "Card", "Demand Draft"])
            existing_pay = db_pool.execute_query("SELECT payment_id FROM fee_payment WHERE receipt_no = %s", (rec_no,), fetch="one")
            if not existing_pay:
                try:
                    db_pool.execute_dml(
                        "INSERT INTO fee_payment (student_id, semester_no, amount, paid_on, mode, receipt_no) VALUES (%s, %s, %s, '2026-07-15', %s, %s)",
                        (s_id, sem, paid_amt, mode, rec_no)
                    )
                except Exception:
                    pass

    # Pending Admissions (20 Applications)
    for k in range(1, 22):
        app_name = f"{fake.first_name()} {fake.last_name()}"
        app_email = f"applicant{k}_{random.randint(100,999)}@gmail.com"
        app_phone = f"91{random.randint(10000000, 99999999)}"
        app_did = random.choice(dept_ids)
        app_date = fake.date_between(start_date="-30d", end_date="today").isoformat()

        dup = db_pool.execute_query("SELECT application_id FROM admission_application WHERE email = %s", (app_email,), fetch="one")
        if not dup:
            try:
                db_pool.execute_dml(
                    "INSERT INTO admission_application (applicant_name, email, phone, dept_id, applied_on, status) VALUES (%s, %s, %s, %s, %s, 'Pending')",
                    (app_name, app_email, app_phone, app_did, app_date)
                )
            except Exception:
                pass

    # 3 Demo Users
    # Admin: admin / admin123
    admin_pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
    existing_admin = db_pool.execute_query("SELECT user_id FROM app_user WHERE username = 'admin'", fetch="one")
    if not existing_admin:
        db_pool.execute_dml(
            "INSERT INTO app_user (username, password_hash, role) VALUES ('admin', %s, 'admin')",
            (admin_pw,)
        )

    # Faculty: faculty / faculty123 (linked to faculty_id 1)
    fac_pw = bcrypt.hashpw(b"faculty123", bcrypt.gensalt()).decode("utf-8")
    existing_fac = db_pool.execute_query("SELECT user_id FROM app_user WHERE username = 'faculty'", fetch="one")
    if not existing_fac and faculty_ids:
        db_pool.execute_dml(
            "INSERT INTO app_user (username, password_hash, role, faculty_id) VALUES ('faculty', %s, 'faculty', %s)",
            (fac_pw, faculty_ids[0])
        )

    # Student: student / student123 (linked to student_id 1)
    stu_pw = bcrypt.hashpw(b"student123", bcrypt.gensalt()).decode("utf-8")
    existing_stu = db_pool.execute_query("SELECT user_id FROM app_user WHERE username = 'student'", fetch="one")
    if not existing_stu and student_ids:
        db_pool.execute_dml(
            "INSERT INTO app_user (username, password_hash, role, student_id) VALUES ('student', %s, 'student', %s)",
            (stu_pw, student_ids[0])
        )

    # Output live counts
    print("-" * 70)
    print("SEEDING COMPLETE. LIVE DATABASE TOTALS:")
    print(f"  • Departments:    {db_pool.execute_query('SELECT COUNT(*) FROM department', fetch='val')}")
    print(f"  • Faculty:        {db_pool.execute_query('SELECT COUNT(*) FROM faculty', fetch='val')}")
    print(f"  • Students:       {db_pool.execute_query('SELECT COUNT(*) FROM student', fetch='val')}")
    print(f"  • Courses:        {db_pool.execute_query('SELECT COUNT(*) FROM course', fetch='val')}")
    print(f"  • Offerings:      {db_pool.execute_query('SELECT COUNT(*) FROM course_offering', fetch='val')}")
    print(f"  • Enrollments:    {db_pool.execute_query('SELECT COUNT(*) FROM enrollment', fetch='val')}")
    print(f"  • Attendance:     {db_pool.execute_query('SELECT COUNT(*) FROM attendance', fetch='val')}")
    print(f"  • Exams:          {db_pool.execute_query('SELECT COUNT(*) FROM exam', fetch='val')}")
    print(f"  • Results:        {db_pool.execute_query('SELECT COUNT(*) FROM result', fetch='val')}")
    print(f"  • Payments:       {db_pool.execute_query('SELECT COUNT(*) FROM fee_payment', fetch='val')}")
    print(f"  • Applications:   {db_pool.execute_query('SELECT COUNT(*) FROM admission_application', fetch='val')}")
    print(f"  • App Users:      {db_pool.execute_query('SELECT COUNT(*) FROM app_user', fetch='val')}")
    print("=" * 70)

if __name__ == "__main__":
    run_seed()
