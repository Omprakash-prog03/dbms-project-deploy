# NIST University Portal Management

A Flask student information system with a calm, dark interface inspired by the supplied reference: pastel mesh-gradient cards, locally rendered glass sculptures, rounded controls, and a responsive campus workspace.

The application source lives at the repository root. The original `dbms project.zip` archive is no longer required and is not part of this project.

## Private deployment — free hosting

The selected deployment target is **PythonAnywhere Beginner**, using persistent SQLite and a fresh private administrator account. Follow the **[free-host deployment guide](docs/DEPLOY_PYTHONANYWHERE.md)**, which starts with the exact copy-paste commands and Web-tab values. It includes a setup script, owner-only configuration, production WSGI entry point, HTTPS/CSRF requirements, login throttling, and post-publication checks.

**No public production site is provisioned by this repository alone.** Publishing requires the owner's PythonAnywhere sign-in and Web-tab setup. The Arena preview is temporary and uses demonstration data; it is not the private production database.

The free tier has one worker, 512 MiB of private storage, restricted resources, and monthly web-app renewal. It is intended here for a small installation, not guaranteed high-traffic uptime. No paid hosting is provisioned. [1](https://www.pythonanywhere.com/pricing/) [12](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/)

The production initializer creates **no shared demo logins and no student records**. The seed script refuses to run in production mode. The administrator starts with Departments, then Faculty/Courses/Offerings, Admissions or Students, and fees. Internal legacy database identifiers remain unchanged to preserve existing data compatibility; displayed branding and exports use NIST University.

## Run a local development/demo instance

Requires **Python 3.11+**. Node is only needed for browser tests or rebuilding artwork, not to run the app.

```bash
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
python db/seed.py                    # optional synthetic university/demo data
python app.py
```

Open **http://localhost:5000**. The server binds to `0.0.0.0` for container/proxied previews. All browser requests use relative, same-origin URLs; no remote fonts or CDN scripts are required.

Set `DEMO_MODE=true` in `.env` to show one-click demo account buttons on the sign-in page. This only displays shortcuts; normal password verification is still required. Run the seed script first.

| Demo role     | Username  | Password     |
| ------------- | --------- | ------------ |
| Administrator | `admin`   | `admin123`   |
| Faculty       | `faculty` | `faculty123` |
| Student       | `student` | `student123` |

**These accounts are for demonstrations only.** Do not seed a production database. Running the seed script again leaves existing seeded records and passwords unchanged. The provided data is synthetic, dated primarily to the 2025–2026 academic session; sparse months in the activity chart are actual zeroes, not missing UI data.

For a fresh private installation, use `python scripts/init_production.py` in a new checkout, without first copying `.env.example` or running the seed script. It prompts securely for a private administrator password and generates the production configuration. Use the Departments screen to create your own academic structure. `scripts/create_admin.py` remains available to add another administrator interactively.

## What's changed

### Interface and workflows

- Unified dark theme across authentication, overview, student profiles, academics, operations, fees, and database insights.
- Six gradient overview cards with glass artwork; **For you / Academics / People / Operations** filters.
- Live database metrics, year-selectable SVG activity chart, admissions queue, and recent students. No hardcoded dashboard counts.
- Search students, full names, roll numbers, courses, and workspace pages with **Ctrl/Cmd + K**.
- Admissions creation and review with status/search filters, confirmation, age validation, and one-time generated account credentials.
- Department creation/editing and head-of-department assignment; examination creation with ownership and marks validation. New installations no longer depend on sample records.
- Working student create/edit/delete dialogs; populated dates and address fields; useful validation errors; real filtered CSV exports.
- Responsive mobile navigation, scrollable tables, keyboard-focusable controls, accessible dialogs, focus return, Escape dismissal, reduced-motion support, and status notifications.
- Locally hosted Inter fonts (including the rupee symbol), icons, and six reproducible glass sculptures. No Chart.js/CDN dependency.

### Reports and PDF exports

- **Reports & PDF** (staff section) shows overall campus figures from live records: students by department, statuses, grade mix, and — for administrators — the fee position and a row count for every database table.
- **Download campus PDF** produces a paginated summary; each student profile has **Download report PDF** with enrolment, exam results, attendance, and (for administrators and that student) the fee ledger.
- **Raw data** (administrator only) prints any physical table the way a database client does: the `SELECT` statement above a monospaced fixed-width grid with a dashed header rule and row numbers, 10/20/50/100 rows per page, plus CSV and landscape PDF downloads of the entire table (capped at 200 rows in the PDF). Read-only, and `password_hash`/`photo_url` are never selected.
- **SQL console** (`/raw-data/query`, administrator only) is a real prompt over the live database: type `SELECT`, `INSERT`, `UPDATE` or `DELETE`, run it with **Run statement** or **Ctrl/⌘ + Enter**, and read the result in the same fixed-width grid the raw viewer uses, with timing and a session history. Data changes are committed immediately. `DROP`, `ALTER`, `CREATE`, `TRUNCATE` and transaction control are refused, a `UPDATE`/`DELETE` without a `WHERE` clause needs an explicit tick, `password_hash` is masked in results and cannot be written, and the schema sidebar lists every table and column so statements can be written without guessing.
- Administrators can export any table to CSV; the `password_hash` and photo columns are never included, and formula-prefixed text is neutralised.
- PDFs are generated server-side without a native library, so the free host's 512 MiB quota is unaffected. Text is Latin-1: non-Latin characters appear as `?` in PDFs (the web UI and CSV retain full Unicode).

### Two doors: the campus sign-in and the supreme dashboard

There are **two sign-in pages**, and they are not interchangeable.

**`/login` — staff, students and faculty.** The password is enough for students and
faculty. Every administrator — except the ones named in `OTP_EXEMPT_ADMINS` — must
also type a **one-time code** that the supreme administrator issues, every single
time they sign in. The access-code box is always on the page, labelled
"administrators only", and it explains the rule before anyone fails; while an
administrator waits, the page polls `/api/auth/access-status` every five seconds and
turns green the moment the code is issued.

**`/supreme` — the supreme administrator alone.** A separate page with its own
username and password (`om-2026` by default, created by
`scripts/setup_admins.py`). The supreme account is refused on `/login` and sent
here, and this page refuses every other account. Everything below lives behind it.

#### Who the accounts are

| Account | Where they sign in | Code needed? |
| --- | --- | --- |
| `om-2026` (supreme) | `/supreme` | — (their own password) |
| `omprakash` | `/login` | no, exempt by `OTP_EXEMPT_ADMINS` |
| `swaruppradhan`, `avashbadatya`, `aryandash` | `/login` | yes, a fresh code every sign-in |

`scripts/setup_admins.py` creates exactly these accounts:

```bash
python scripts/setup_admins.py                 # dry run: show what would happen
python scripts/setup_admins.py --apply         # create or update the accounts
python scripts/setup_admins.py --apply --keep-passwords
```

Passwords are stored as bcrypt hashes and never printed back. Running it twice is
safe and idempotent: it re-applies the passwords above to existing accounts (so a
pre-existing `omprakash` ends up on `Adminom123`), `--keep-passwords` opts out, and a
stale `OWNER_USERNAME` in `.env` is corrected to the supreme account.

#### The supreme dashboard (`/owner`)

- **Live roster**: every administrator with signed in / signed out / blocked, last
  activity and sign-in count. **Sign out** ends one administrator's session on their
  next click; **Sign out everyone else** ends all of them and never the supreme
  session itself. **Remove admin** deletes the account, so they cannot return.
- **Access codes**: every waiting request, one code each (six digits, 15 minutes,
  single use, five wrong tries and it is revoked), plus **Close request**.
- **Administrator sign-in switch**: closing it refuses every other administrator even
  with a valid code, and signs the signed-in ones out.
- **Per-account block**: refuses one administrator's logins while leaving the rest.
- **Master key (optional step-up)**: set one and every action on the page asks for it
  again; leave it unset and the supreme password alone unlocks the page. The key is
  stored as a bcrypt hash, shown once, and `scripts/owner_key.py` can recover it.
- **Owner activity**: every lock, code, block, reset and removal, newest first.

### Who can do what

| Capability                                      | Administrator | Faculty                                                              | Student             |
| ----------------------------------------------- | ------------- | -------------------------------------------------------------------- | ------------------- |
| Campus overview, reports, CSV/PDF exports       | Yes (all)     | Own classes, no finance                                              | Own profile and PDF |
| Departments, courses, offerings, faculty        | Yes           | View                                                                 | View                |
| Students: add/edit/delete                       | Yes           | Add, and edit **their own** students' records only through enrolment | No                  |
| Attendance roll-call                            | Yes           | **Yes, for their own offerings**                                     | No                  |
| Exams, marks/results                            | Yes           | Yes, for their own offerings                                         | Read own results    |
| Fees and payments                               | Yes           | No                                                                   | Own fee summary     |
| Password resets, database tables, SQL inspector | Yes           | No                                                                   | No                  |

A faculty account only sees classes where they are the instructor. If the Attendance page says "No class assigned yet", an administrator needs to create a course offering with that faculty member as the instructor.

### Passwords chosen by staff

- Staff set student portal passwords when creating a student (optional) or while approving an admission application. No password is generated unless the field is left blank at approval, in which case a one-time password is shown once.
- Faculty accounts are created with a password the administrator types in the Faculty dialog.
- Any administrator can reset a student/faculty password from the row action, or reset the administrator's own via `scripts/reset_password.py` on the server console.
- Students sign in with their roll number and the password staff set. They can only see their own profile, results, attendance, fees, and report PDF.

### Correctness and access control

- Removed the login fallback that could accept demo passwords when a stored hash was invalid.
- Added CSRF protection for mutations, session/token rotation on login, HTTP-only/SameSite cookies, and POST-only logout.
- Students can see only their own profile, transcript, attendance, and fee summary. They cannot access the campus directory, staff APIs, admissions, CSV exports, or SQL inspector.
- Faculty can maintain students and review admissions, and can manage enrollments/attendance/results **only for their own offerings**. Fees, passwords, and database insights are administrator-only.
- SQL traces are bounded and session-scoped; password-hash operations are omitted. The inspector is diagnostic, not durable audit storage, and uses one server worker's memory.
- Student pagination is clamped to valid pages. Sorting is allowlisted. Editing now preserves and saves dates, gender, department, and address instead of dropping fields. Database guards prevent profile changes from relabeling or hiding existing fee payments.
- CSV exports preserve search/department/status/sort filters, export all matching records, and neutralize formula-prefixed text cells.
- Attendance batches reject forged cross-course enrollment IDs, duplicate IDs, inactive enrollments, invalid statuses, and future dates; a failed batch rolls back.
- Gradebook selection cannot retain an exam from a different offering. Result writes reject cross-course/inactive enrollments, negative and non-finite marks, and marks above the maximum; saves use atomic upserts.
- Payment amounts use decimal validation and cent precision; invalid methods, overpayments, and future-semester payments are rejected. MySQL payments lock the student and fee rows before checking balances. Successful installments, duplicate receipts, concurrent payments, and full-payment balances have regression tests; financial totals are rounded to cent precision.
- Admissions use serialized roll-number allocation rather than row counts. Approvals require a real birth date (age 15+), create a unique random password, and cannot be re-approved/rejected. No date of birth or address is fabricated. A student record is **not** a course enrollment.
- Faculty + login creation is atomic, with an explicitly chosen initial password.
- Enrollment update triggers enforce capacity on reactivation and maintain both offering counts when an enrollment moves. Academic records block reassignment.
- Grade scales match across SQLite/MySQL: A+, A, B+, B, C, P, F at 90/80/70/60/50/40 percent. Ungraded results remain ungraded.
- CGPA is credit-weighted across graded, non-dropped enrollments, combining recorded exam scores within each offering before assigning grade points. Repeated offerings each contribute independently; institution-specific retake rules are not implemented.
- SQLite standard deviation uses a real population aggregate. Empty SQL results retain column metadata.

## Tests

```bash
python -m pytest -q
```

The test suite seeds a **temporary SQLite database** and never changes the running app's data. It covers the original query/schema/procedure tests plus access control, CSRF, hash failure, SQL trace isolation, CSV safety, pagination, grades, attendance, financial validation, admissions, capacity rules, and SQLite backup/restore. A Python 3.11/3.12 CI workflow is included. Additional tests initialize a separate, empty production database and exercise private login, department/faculty/course/offering creation, admissions approval, enrollment, attendance, examination/result entry, payments, and student-only access.

For browser checks, start a seeded demo server separately, then:

```bash
npm ci
npm run test:ui
# Optional, for another local test server:
TEST_BASE_URL=http://localhost:5001 npm run test:ui
# Also verify cross-site iframe sign-in when EMBEDDED_PREVIEW=true on the server:
TEST_EMBEDDED=true npm run test:ui
```

Browser checks cover all 16 main routes at desktop/mobile widths, three role logins, keyboard navigation, tabs, live search, chart years, SQL inspection, edit dialogs, filtered exports, runtime errors, and WCAG A/AA checks on login, the overview, student directory, and student/admission dialogs, including desktop/mobile layouts. Screenshots are written to ignored `.artifacts/`.

**Test scope:** the automated database suite and preview run on SQLite. The MySQL adapters, routines, and Docker configuration are supplied but were not integration-tested against a live MySQL server in this environment.

## Database and deployment

- `DB_ENGINE=sqlite`: explicit local SQLite database at `SQLITE_PATH`.
- `DB_ENGINE=mysql`: explicit MySQL 8 connection; an unavailable database fails closed instead of silently falling back to unrelated data.
- `DB_ENGINE=auto`: legacy MySQL-first fallback, useful only for local demos.
- Runtime databases, `.env`, backups, caches, screenshots, and dependencies are Git-ignored.
- SQLite applies the non-destructive integrity migration in `db/embedded_guards.sql` using `PRAGMA user_version` on startup. Back up existing databases first; legacy data is not silently rewritten.
- MySQL: initialize a **new** database with the supplied SQL files in Docker's listed order. For an **existing** installation, back it up and review/apply `db/triggers.sql` and `db/procedures.sql`; do **not** reapply `db/schema.sql`, which recreates tables. The `sp_approve_admission` signature now takes date of birth and a fresh bcrypt hash before its OUT parameters. The web route uses the equivalent Python transaction on both engines.

Production startup:

```bash
# Initialize a private deployment first; do not seed it with demo data.
# Generate it locally: python -c "import secrets; print(secrets.token_hex(32))"
gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 wsgi:application
```

Use HTTPS and `COOKIE_SECURE=true`, disable `DEMO_MODE`, choose a least-privilege database user, keep a persistent database volume, configure backups, and review authorization for your institution before using real student data. Production mode includes a ten-attempts-per-minute, per-client-IP login limit for the selected single-worker host. Limits reset on worker restart; use a shared rate-limit store if scaling to multiple workers. For an HTTPS embedded preview such as Arena, set `EMBEDDED_PREVIEW=true`: this uses Secure, SameSite=None, partitioned session cookies so sign-in works inside the preview iframe without disabling CSRF. Leave it false for ordinary HTTP development. Changing `SECRET_KEY` invalidates existing sessions. Without an explicitly configured key, the local development fallback is random per process.

### Reset a forgotten password

From the server console, with the virtual environment active:

```bash
python scripts/reset_password.py
```

The password is typed twice at a hidden prompt and never passed as an argument. The account's role and other users are untouched. Deployments created with `scripts/init_production.py` start with only the administrator you chose — the demo logins below exist only in the seeded local database.

### Back up / restore

With the virtual environment active, `python scripts/backup.py` creates a timestamped snapshot of the **configured** database under ignored `backups/`. SQLite uses its online backup API; MySQL requires the `mysqldump` client and never puts the database password in command-line arguments.

Stop the web server and take a current backup before restoring:

```bash
python scripts/restore.py backups/your_snapshot.db --confirm
# For an explicitly configured MySQL target and an installed mysql client:
# python scripts/restore.py backups/your_snapshot.sql --confirm
```

Restoring replaces database contents. Without `--confirm`, the utility makes no changes. SQLite validates the selected backup and saves a pre-restore snapshot if the destination exists. The shell scripts delegate to these Python utilities; they no longer contain default credentials or hardcoded database targets.

### Optional Docker + MySQL

Set `SECRET_KEY`, `DB_PASSWORD`, and `MYSQL_ROOT_PASSWORD` locally in `.env`. Then:

```bash
docker compose up --build -d
# Choose ONE of these paths:
docker compose exec web python db/seed.py              # synthetic demo only
# or
docker compose exec web python scripts/create_admin.py # empty, non-demo install
```

The MySQL data volume persists across restarts. The database is not exposed on a public host port. The image includes Gunicorn and runs as a non-root user.

**GitHub Pages cannot run Flask or a database.** The existing `CNAME` file does not deploy this application. Use a Python/container host and point your domain to that service. No external production deployment has been performed by these changes.

A file-by-file comparison with the original `dbms project.zip` — what was kept, what was rewritten, and every logic bug fixed — is in **[docs/WHAT_CHANGED.md](docs/WHAT_CHANGED.md)**.

## Project layout

```text
app.py / config.py       Application setup, CSRF, filters and environment
routes/                  Role-protected HTML and JSON endpoints
repositories/            Parameterized SQL and transactional business logic
db/                      Schema, routines, guards, showcase queries and demo seed
templates/               Jinja pages and accessible shared components
static/css/              Dark design tokens, responsive shell and login
static/js/               Search, dialogs, SVG charts and workflow controllers
static/images/           Small, locally rendered glass sculptures
static/fonts/            Inter variable fonts and license
scripts/                 Private setup, deployment checks, artwork and backup utilities
wsgi.py                  Production WSGI entry point for the selected free host
requirements-runtime.txt Minimal SQLite runtime (no demo/test/build dependencies)
tests/                   Isolated pytest suite and browser regression checks
```

Rebuild the decorative artwork with `npm run art`. The committed PNGs are ready to use; no WebGL is required in visitors' browsers. Historical design/viva notes in `docs/` describe the original project; this README is the current runbook.
