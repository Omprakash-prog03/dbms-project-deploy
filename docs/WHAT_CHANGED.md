# What changed — original zip vs. the current repository

This document answers one question: **how much of this project came from `dbms project.zip`, and what is new?**

Everything below was measured against the archive, not recalled from memory.

|                      | Original zip                                                                   | Current repository                        |
| -------------------- | ------------------------------------------------------------------------------ | ----------------------------------------- |
| Files                | 82 (incl. `.env`, `.pytest_cache/`, an old `backups/*.db`, `sims_embedded.db`) | 131 tracked files (+4 in this change)     |
| Python source        | ~4,700 lines                                                                   | ~7,300 lines                              |
| Templates / CSS / JS | ~2,600 lines                                                                   | ~7,450 lines                              |
| Automated tests      | 43 test functions                                                              | 156 Python test functions + browser suite |
| Routes / endpoints   | 37 route decorators                                                            | 58 route decorators (59 URL rules)        |
| Portal name          | SIMS                                                                           | NIST University Portal Management         |

**Verdict: this is an evolution of the original codebase, not a rewrite.** The schema, the repositories, the route modules, the Jinja page structure and the SQL showcase files are the same code continued forward. Roughly **60 files were modified in place** and **60 files are new** (listed at the end). Two genuinely new subsystems were added: a PDF/CSV reporting layer and a deployment/verification toolchain.

---

## 1. Kept as-is (unchanged from the zip)

- `db/schema.sql`, `db/indexes.sql`, `db/queries/*.sql` (7 files), `db/roles.sql` — the relational design: 15 tables, constraints, indexes and showcase queries.
- `repositories/enrollments.py`, `repositories/insights.py`, `tests/test_queries.py` (minor edits only).
- `docs/er_diagram.md`, `docs/normalization.md`, `docs/DESIGN_DOCUMENT.md` — the academic documentation.
- The overall architecture: Flask blueprints → repository classes → `db_pool` (MySQL or embedded SQLite), one template per screen.

## 2. Modified heavily (same file, substantially rewritten)

| File                                                                                  | What changed                                                                                                                                                 |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `static/css/shell.css` (837 → 2,402)                                                  | Whole visual system: dark shell, pastel mesh cards, glass artwork, responsive/mobile rules, dialogs, tables, focus states.                                   |
| `static/js/app.js` (53 → 391)                                                         | Toasts, modals, confirmation dialogs with validated fields, global search palette, notifications, keyboard shortcuts, **global CSRF-aware `fetch` wrapper**. |
| `app.py` (63 → 182)                                                                   | CSRF enforcement, JSON/type validation, per-session SQL traces, error handlers, production config guard, rate limiting, health check, security headers.      |
| `templates/base.html`, `dashboard.html`, `login.html`, `students/*.html`              | Rebuilt against the reference design; login shrunk 148 → 10 lines by moving inline styles into `static/css/login.css`.                                       |
| `repositories/students.py`, `fees.py`, `admissions.py`, `attendance.py`, `faculty.py` | Logic fixes listed in section 3.                                                                                                                             |
| `db/triggers.sql`, `db/procedures.sql`, `db/embedded_guards.sql`                      | Additional guards, atomic routines, grade/CGPA parity.                                                                                                       |
| `db/seed.py`                                                                          | Deterministic demo data; now refuses to run in production.                                                                                                   |

## 3. Logic bugs found in the zip and fixed

These were verified by reading the original source, not assumed:

1. **Authentication bypass (critical).** If bcrypt raised on a malformed hash, the original fell back to
   `is_valid = (password == user["password_hash"]) or (password in ("admin123", "faculty123", "student123"))`
   — so a corrupted hash could be logged into with a public demo password. Replaced with fail-closed verification, plus inactive-student/inactive-faculty checks.
2. **No CSRF protection at all.** Added token checks for every POST/PUT/PATCH/DELETE, session and token rotation on login, and POST-only logout (the original also accepted `GET /logout`).
3. **Any student could open any other student's profile** — `profile_view` had no ownership check, and the page included the fee ledger. Now students see only their own record.
4. **No instructor ownership on class operations.** Attendance `save_batch` only rejected `Dropped` enrolments; a faculty member could post attendance for any offering. Attendance, results and enrolment now verify the offering belongs to the signed-in faculty member.
5. **Attendance accepted bad input** — future dates, duplicate enrolment IDs, forged IDs from another class, invalid statuses. Now rejected transactionally.
6. **Editing a student silently dropped fields** — `update()` wrote only name/email/phone/address/semester/status, so date of birth, gender, department and admission date were never saved. Now all fields persist, with rules preventing department changes that would rewrite past fee balances.
7. **Roll numbers could collide.** Admission approval used `COUNT(*) + 1`, which repeats after any deletion. Now allocates the maximum existing suffix under a transaction lock.
8. **CSV export silently truncated at 2,000 rows**, ignored sort order, and allowed spreadsheet formula injection from text fields. Now exports every matching row, honours filters, and neutralises `= + - @` prefixes.
9. **Pagination could show an empty page** past the last page (no clamp) and search matched fewer fields. Both fixed; sort columns remain allow-listed.
10. **Money handling was float-based.** Underpaid/overpaid states could appear from binary rounding (`0.10 + 0.70` against `0.80`), and payment methods/dates were lightly validated. Now decimal-validated, cent-rounded, overpayment/duplicate-receipt/future-semester rejected, and MySQL payments lock rows.
11. **Admissions invented data.** Approval could not proceed without a real date of birth (15+), generates a unique password, and terminal states cannot be re-approved.
12. **Faculty account creation was two separate writes** — a failure could leave a faculty member with no login. Now atomic, with an administrator-chosen password.
13. **Page scripts posted without the CSRF token** (`fetch` called directly in 12 places, e.g. attendance and results), so those saves failed with “session expired”. Fixed globally in `app.js`; faculty roll-call now saves (verified in a browser: 200, 35 students recorded).
14. **The demo faculty account owned no course offerings**, so its attendance page was empty. The seed now assigns the first two offerings to it, and the page explains the situation when no class exists.

## 4. New subsystems (not in the zip at all)

- **PDF reporting** (`repositories/pdf.py`): a dependency-free PDF writer producing paginated A4 reports, so the free host needs no native library or extra package.
- **Reports page** (`/reports`): live campus figures, students by department/status, grade mix, administrator fee snapshot, row counts for every database table, per-table CSV export.
- **Supreme control** (`/owner`, owner only; `/admin-access` redirects): one private page holding a live administrator roster (signed in / signed out / blocked, last activity, sign-in count), per-account sign-out, the global lock, an administrator sign-in switch, one-time six-digit access codes, blocks, password resets, removals and the owner's own activity trail. A bcrypt-hashed master key guards every action and is re-checked on destructive forms; `owner_key.py` is the console fallback.
- **Live session registry** (`admin_session`): each administrator sign-in carries a token version, so one account can be ejected without touching the others, while the lock is still an `epoch` counter that survives restarts.
- **The sign-in page explains the rule before anyone fails**: the access-code box is always visible with an "administrators only" note, the page polls `/api/auth/access-status` every five seconds while an administrator waits, and closed sign-in / no master key / blocked account are stated on the page rather than failing silently. Students and faculty are never shown administrator messages.
- **Raw data viewer** (`/raw-data`, administrator only): every physical table rendered the way a database client prints a result — the `SELECT` statement above a monospaced fixed-width grid with a dashed header rule, row numbers, pagination, and column metadata — plus CSV and landscape PDF downloads of the whole table. `password_hash` and `photo_url` are never selected.
- **SQL console** (`/raw-data/query`, administrator only): a genuine SQL prompt over the live database — read and write statements, raw fixed-width output with timing, per-session history, schema reference and one-click examples. Schema changes are refused and credential columns are masked.
- **Student report card PDF** (`/students/<id>/report.pdf`): enrolment, marks, attendance, and the fee ledger for administrators and the student themselves.
- **Departments management** — the zip had a read-only departments page; creation/editing with head-of-department assignment is new.
- **Admission application entry, examination creation, student password choice, faculty password choice** — the empty-install gaps.
- **Deployment toolchain**: `wsgi.py`, `scripts/init_production.py`, `scripts/check_production.py`, `scripts/reset_password.py`, `scripts/setup_pythonanywhere.sh`, `scripts/browser.mjs`, `requirements-runtime.txt`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/test.yml`.
- **Verification**: 156 Python tests (up from 43) including concurrency, backup/restore, production bootstrap and CSRF regressions, plus a Playwright suite covering 17 routes, three roles, accessibility and PDFs.
- **Assets**: six generated glass sculptures, local Inter fonts, favicon — no runtime CDN.

## 5. Removed from the zip

- `.env` (contained local secrets), `.pytest_cache/`, `backups/sims_embedded_20261020_115611.db` and the root database file — all runtime/secret artifacts, now Git-ignored. No code was deleted.

## 6. New files, complete list

```
.dockerignore                     .github/workflows/test.yml        .gitignore
Dockerfile                        docs/DEPLOY_PYTHONANYWHERE.md     extensions.py
package.json                      package-lock.json                 requirements-runtime.txt
wsgi.py
repositories/accounts.py          repositories/departments.py       repositories/pdf.py
repositories/reports.py           repositories/validation.py
routes/reports.py                 scripts/check_production.py       scripts/create_admin.py
scripts/init_production.py        scripts/reset_password.py         scripts/restore.py
scripts/setup_pythonanywhere.sh   scripts/browser.mjs               scripts/render-art.mjs
static/css/login.css              static/fonts/* (3)                static/images/* (7)
static/js/admissions.js           static/js/departments.js          static/js/exams.js
static/js/login.js                static/js/students.js
templates/admissions/index.html   templates/components/icons.html   templates/error.html
templates/reports/index.html      templates/rawdata/index.html      repositories/rawdata.py
routes/rawdata.py                 tests/test_rawdata.py            repositories/sqlconsole.py
tests/test_sqlconsole.py          templates/rawdata/query.html     static/js/sqlconsole.js
tests/production_smoke.py         tests/test_backup_restore.py      tests/test_production.py
tests/test_reports.py             tests/test_workspace.py           tests/ui.mjs
```

## 7. Things still not done

- The MySQL adapters, stored procedures and Docker configuration are supplied but **have not been run against a live MySQL server** in this environment; SQLite is what the tests and the deployed site use.
- PDFs use Latin-1 text, so Devanagari/Odia names appear as `?` inside a PDF (the web UI and CSV keep full Unicode).
- The deployed free-tier site has one worker, 512 MiB of storage and needs monthly renewal; login throttling is per-process memory.
