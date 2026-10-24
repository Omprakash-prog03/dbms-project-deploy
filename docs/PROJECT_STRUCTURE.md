# Project structure by work area

A complete inventory of the repository, grouped by the kind of work each file does:
**Python backend**, **database**, **UI**, **tests**, **scripts**, **deployment**, **docs**.

Measured from `git ls-files` on the current `main` — **127 tracked files, 22,593 lines**.

---

## At a glance

| Work area | Files | Lines | Folder(s) |
| --- | ---: | ---: | --- |
| Python backend | 30 | 4,473 | root (4 files), `routes/`, `repositories/`, `db/seed.py` |
| Database (SQL) | 13 | 1,770 | `db/`, `db/queries/` |
| UI — HTML templates | 20 | 2,845 | `templates/` |
| UI — CSS | 3 | 2,938 | `static/css/` |
| UI — JavaScript | 8 | 953 | `static/js/` |
| UI — images | 7 | 1,894 | `static/images/` |
| UI — fonts | 3 | 629 | `static/fonts/` |
| Tests | 15 | 2,062 | `tests/` |
| Scripts / operations | 11 | 528 | `scripts/` |
| Deployment / config | 11 | 486 | root, `.github/workflows/` |
| Documentation | 6 | 4,015 | root, `docs/` |
| **Total** | **127** | **22,593** | |

**UI as one block:** 41 files / 9,259 lines (the largest single work area by line count).

---

## 1. Python backend — 30 files, 4,473 lines

### Entry points and configuration (4)

| File | Lines | Purpose |
| --- | ---: | --- |
| `app.py` | 182 | Flask application factory: blueprints, CSRF, security headers, error handlers, production guards |
| `config.py` | 40 | Environment-driven settings, loaded once from `.env` |
| `extensions.py` | 12 | Shared Flask-Limiter instance (login throttling) |
| `wsgi.py` | 11 | Production WSGI entry point for PythonAnywhere |

### HTTP routes — the "controllers" (9 files, 983 lines)

| File | Lines | Purpose |
| --- | ---: | --- |
| `routes/auth.py` | 160 | Login, logout, password reset, role guards |
| `routes/operations.py` | 186 | Attendance, enrolments, results |
| `routes/academics.py` | 127 | Departments, faculty, courses, offerings |
| `routes/students.py` | 122 | Student CRUD and profiles |
| `routes/dashboard.py` | 117 | Overview stats, charts, search, CSV export |
| `routes/reports.py` | 98 | Reports page and PDF/CSV downloads |
| `routes/fees.py` | 66 | Fee structures and payments |
| `routes/admissions.py` | 59 | Admission applications |
| `routes/insights.py` | 48 | Live SQL inspector panel |

### Data access — the "repositories" (16 files, 2,709 lines)

| File | Lines | Purpose |
| --- | ---: | --- |
| `repositories/db_pool.py` | 641 | MySQL + embedded SQLite engine, schema bootstrap, query log |
| `repositories/students.py` | 278 | Student queries |
| `repositories/insights.py` | 225 | Showcase query catalogue for the inspector |
| `repositories/admissions.py` | 216 | Application intake and review |
| `repositories/pdf.py` | 212 | Dependency-free A4 PDF builder |
| `repositories/fees.py` | 193 | Fee ledger and balances |
| `repositories/reports.py` | 166 | Campus reports shared by UI and downloads |
| `repositories/faculty.py` | 117 | Faculty records |
| `repositories/courses.py` | 120 | Courses and offerings |
| `repositories/attendance.py` | 103 | Attendance registers |
| `repositories/results.py` | 99 | Exam results |
| `repositories/enrollments.py` | 96 | Student ↔ offering enrolments |
| `repositories/dashboard.py` | 93 | Aggregate dashboard metrics |
| `repositories/validation.py` | 55 | Shared input validation helpers |
| `repositories/departments.py` | 52 | Departments and heads |
| `repositories/accounts.py` | 43 | Portal credentials, bcrypt hashing |

### Seeding (1)

| File | Lines | Purpose |
| --- | ---: | --- |
| `db/seed.py` | 536 | Synthetic demo data; refuses to run in production |

---

## 2. Database — 13 files, 1,770 lines

### Schema and database objects (7 files, 1,198 lines)

| File | Lines | Purpose |
| --- | ---: | --- |
| `db/schema.sql` | 270 | 15 tables, 3NF/BCNF, PK/FK/UNIQUE/CHECK |
| `db/procedures.sql` | 361 | Stored procedures and functions |
| `db/triggers.sql` | 232 | Audit and integrity triggers |
| `db/views.sql` | 156 | Reporting views |
| `db/embedded_guards.sql` | 109 | Constraint emulation for the SQLite fallback |
| `db/roles.sql` | 40 | Database roles and grants |
| `db/indexes.sql` | 30 | Composite and covering indexes |

### Showcase queries (6 files, 572 lines)

| File | Lines | Query group |
| --- | ---: | --- |
| `db/queries/windows_ctes.sql` | 153 | D — Window functions & CTEs |
| `db/queries/subqueries.sql` | 121 | C — Subqueries |
| `db/queries/joins.sql` | 118 | A — Relational joins |
| `db/queries/aggregates.sql` | 86 | B — Aggregations & grouping |
| `db/queries/dml.sql` | 57 | F — Data modification |
| `db/queries/sets.sql` | 37 | E — Set operations |

---

## 3. UI — 41 files, 9,259 lines

### HTML templates (20 files, 2,845 lines)

| File | Lines | Purpose |
| --- | ---: | --- |
| `templates/base.html` | 81 | Shared page shell and navigation |
| `templates/dashboard.html` | 69 | Overview page |
| `templates/error.html` | 2 | Error page |
| `templates/login.html` | 10 | Sign-in page |
| `templates/components/icons.html` | 32 | Inline SVG icon set |
| `templates/components/password_modal.html` | 83 | Password reset dialog |
| `templates/components/sql_modal.html` | 22 | "Show SQL" inspector dialog |
| `templates/academics/courses.html` | 181 | Courses |
| `templates/academics/departments.html` | 39 | Departments |
| `templates/academics/faculty.html` | 224 | Faculty |
| `templates/academics/offerings.html` | 196 | Course offerings |
| `templates/admissions/index.html` | 28 | Admission applications |
| `templates/fees/index.html` | 507 | Fee structures and payments |
| `templates/insights/lab.html` | 390 | SQL inspector lab |
| `templates/operations/attendance.html` | 215 | Attendance |
| `templates/operations/enrollments.html` | 173 | Enrolments |
| `templates/operations/results.html` | 175 | Results |
| `templates/reports/index.html` | 66 | Reports and downloads |
| `templates/students/list.html` | 40 | Student list |
| `templates/students/profile.html` | 312 | Student profile |

### CSS (3 files, 2,938 lines)

| File | Lines | Purpose |
| --- | ---: | --- |
| `static/css/shell.css` | 2,402 | Application shell, cards, tables, dialogs, responsive rules |
| `static/css/login.css` | 472 | Sign-in screen |
| `static/css/tokens.css` | 64 | Colour, spacing and type tokens |

### JavaScript (8 files, 953 lines)

| File | Lines | Purpose |
| --- | ---: | --- |
| `static/js/app.js` | 391 | Shared shell behaviour, search, notifications |
| `static/js/dashboard.js` | 139 | Dashboard chart and stats |
| `static/js/admissions.js` | 105 | Admissions workflow |
| `static/js/students.js` | 104 | Student dialogs and validation |
| `static/js/departments.js` | 68 | Department management |
| `static/js/sql_inspector.js` | 58 | SQL inspector modal |
| `static/js/login.js` | 53 | Sign-in behaviour |
| `static/js/exams.js` | 35 | Exam creation |

### Images (7 files, 1,894 lines of binary)

`static/images/` — `bloom.png`, `flower.png`, `helix.png`, `knot.png`, `orbit.png`, `ribbon.png` (locally rendered glass artwork), plus `favicon.svg`.

### Fonts (3 files, 629 lines of binary)

`static/fonts/` — `inter-latin.woff2`, `inter-latin-ext.woff2`, `INTER-LICENSE.txt`. Hosted locally, so no CDN dependency.

---

## 4. Tests — 15 files, 2,062 lines

| File | Lines | Covers |
| --- | ---: | --- |
| `tests/test_workspace.py` | 415 | End-to-end page and workflow behaviour |
| `tests/ui.mjs` | 367 | Browser suite (Playwright) |
| `tests/test_reports.py` | 251 | Report generation, PDF and CSV output |
| `tests/test_production.py` | 194 | Production configuration guards |
| `tests/test_new_sections.py` | 168 | Departments, exams, admissions |
| `tests/test_triggers.py` | 117 | Trigger enforcement |
| `tests/test_routes.py` | 101 | Route access control |
| `tests/test_procedures.py` | 90 | Stored procedures and rollbacks |
| `tests/production_smoke.py` | 74 | Post-deployment smoke checks |
| `tests/test_backup_restore.py` | 66 | Backup and restore round trip |
| `tests/test_concurrency.py` | 63 | Row locking under concurrent writes |
| `tests/test_schema.py` | 61 | Tables, keys and constraints |
| `tests/test_security.py` | 47 | CSRF, hashing, injection resistance |
| `tests/conftest.py` | 24 | Disposable seeded test database |
| `tests/test_queries.py` | 24 | Showcase query correctness |

`conftest.py` points `SQLITE_PATH` at a temporary directory, so tests never touch real data.

---

## 5. Scripts / operations — 11 files, 528 lines

| File | Lines | Purpose |
| --- | ---: | --- |
| `scripts/render-art.mjs` | 92 | Regenerates the glass artwork PNGs |
| `scripts/init_production.py` | 83 | Creates a private production install |
| `scripts/restore.py` | 70 | Restores a MySQL dump |
| `scripts/backup.py` | 51 | Dumps the database |
| `scripts/check_production.py` | 41 | Verifies a published site |
| `scripts/setup_pythonanywhere.sh` | 40 | Server-side setup |
| `scripts/create_admin.py` | 26 | Adds an administrator |
| `scripts/reset_password.py` | 89 | Resets a portal password |
| `scripts/browser.mjs` | 24 | Launches the browser suite |
| `scripts/backup.sh` | 6 | Shell wrapper for backup |
| `scripts/restore.sh` | 6 | Shell wrapper for restore |

---

## 6. Deployment / config — 11 files, 486 lines

| File | Lines | Purpose |
| --- | ---: | --- |
| `package-lock.json` | 304 | Pinned Node dev dependencies |
| `.env.example` | 26 | Documented configuration template |
| `.gitignore` | 32 | Excluded files |
| `package.json` | 28 | Node scripts for browser tests |
| `docker-compose.yml` | 43 | MySQL 8 + app services |
| `Dockerfile` | 10 | Container image |
| `.github/workflows/test.yml` | 18 | CI: pytest on Python 3.11 and 3.12 |
| `.dockerignore` | 14 | Build exclusions |
| `requirements.txt` | 6 | All dependencies (includes runtime) |
| `requirements-runtime.txt` | 5 | Minimal runtime for the free host |
| `CNAME` | 0 | Custom domain record |

---

## 7. Documentation — 6 files, 4,015 lines

| File | Lines | Purpose |
| --- | ---: | --- |
| `docs/DESIGN_DOCUMENT.md` | 2,910 | Full design report |
| `docs/er_diagram.md` | 304 | Entity-relationship diagram |
| `docs/normalization.md` | 253 | Normalisation walkthrough |
| `docs/DEPLOY_PYTHONANYWHERE.md` | 241 | Free-host deployment guide |
| `README.md` | 207 | Project overview and quick start |
| `docs/WHAT_CHANGED.md` | 100 | Original zip vs. current repository |

---

## How the layers connect

```
Browser
   │
   ▼
templates/ + static/          ← UI: HTML, CSS, JS, images, fonts
   │  fetch / form post
   ▼
routes/                       ← Backend: URL rules, roles, CSRF checks
   │  calls
   ▼
repositories/                 ← Backend: parameterised SQL, no ORM
   │  executes
   ▼
db/*.sql                      ← Database: schema, triggers, views, procedures
```

The **SQL inspector** in the UI surfaces the exact statement from `repositories/` that a page just executed — that is the link between the three layers and the centrepiece of the project.
