# Publish NIST University Portal Management — free, private installation

**Target:** PythonAnywhere Beginner ($0), Flask/WSGI, persistent SQLite, one private administrator, no demo accounts or records.

**Publishing status:** the configuration and setup commands are verified on a clean clone, but this repository cannot sign in to, or publish to, your PythonAnywhere account. Only the account owner can run the console commands and Web-tab steps below. Do not share hosting passwords, API keys, or administrator passwords in chat.

## Free-tier limitations — read before deployment

The current free plan provides one web application on your PythonAnywhere subdomain, one worker, 512 MiB of private file storage, two consoles, and a 100 CPU-second allowance. Free applications have a **one-month expiry**; renew the app before the date displayed in the Web tab. New free accounts do not include MySQL or scheduled tasks. Use the supplied SQLite configuration, not Docker/MySQL. [1](https://www.pythonanywhere.com/pricing/) [12](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/)

This is a small, low-traffic deployment, **not an always-on enterprise hosting guarantee**. Monitor capacity and free-account renewal, download backups manually, and obtain your institution's approval before uploading real student information to a third-party host. No paid service is provisioned by the scripts.

## Fast path (copy-paste)

Everything below has been rehearsed on a clean clone of the pushed branch, including a private sign-in, production headers, empty-dashboard onboarding, and static assets. Gunicorn is **not** used on PythonAnywhere; the host serves `wsgi:application`.

**A. In your PythonAnywhere Bash console**

```bash
git clone --depth 1 --single-branch --branch arena/e027de8b-dbms-project-deploy \
  https://github.com/Omprakash-prog03/dbms-project-deploy.git \
  ~/hogwards-student-management-system
cd ~/hogwards-student-management-system
bash scripts/setup_pythonanywhere.sh
```

Choose an administrator username and a unique 12+ character password **in the console**. Expected last lines:

```text
PASS: private administrator, no shared demo passwords, database ready, ...
NEXT: Web → Add a new web app → Manual configuration.
```

**B. In the Web tab**

| Setting           | Value                                                                           |
| ----------------- | ------------------------------------------------------------------------------- |
| Add a new web app | **Manual configuration**, same Python version the script printed (3.11–3.13)    |
| Virtualenv        | `/home/YOURUSERNAME/hogwards-student-management-system/.venv`                   |
| Source code       | `/home/YOURUSERNAME/hogwards-student-management-system`                         |
| Working directory | `/home/YOURUSERNAME/hogwards-student-management-system`                         |
| Static files      | URL `/static/` → `/home/YOURUSERNAME/hogwards-student-management-system/static` |
| Force HTTPS       | **Enabled**                                                                     |

**C. Replace the WSGI configuration file** with exactly this, then click **Reload**:

```python
import sys
from pathlib import Path

path = str(Path.home() / "hogwards-student-management-system")
if path not in sys.path:
    sys.path.insert(0, path)

from wsgi import application
```

**D. Open `https://YOURUSERNAME.pythonanywhere.com/healthz`.** It must return:

```json
{ "application": "NIST University Portal Management", "status": "ok" }
```

Then open `/login` (no demo buttons), sign in, and add your first department. Do **not** run `db/seed.py`; it refuses to run in production mode and the private installation must stay free of sample records.

## 1. Create/sign in to a free account

Use the **Beginner / free** account at https://www.pythonanywhere.com/registration/register/beginner/ . Do not select an upgrade. Your eventual address is the subdomain PythonAnywhere assigns to your account; no custom domain is required. [1](https://www.pythonanywhere.com/pricing/)

## 2. Install the current application in a Bash console

Open **Consoles → Bash** in your own PythonAnywhere account:

```bash
git clone --depth 1 --single-branch --branch arena/e027de8b-dbms-project-deploy \
  https://github.com/Omprakash-prog03/dbms-project-deploy.git \
  ~/hogwards-student-management-system
cd ~/hogwards-student-management-system
bash scripts/setup_pythonanywhere.sh
```

The script detects Python 3.11–3.13, creates a virtual environment, and installs **only `requirements-runtime.txt`**. Node, browser tests, Faker, MySQL, and local sample databases are not needed on the host.

Choose your administrator username and a unique password of at least 12 characters when prompted **inside the hosting console**. Password entry is hidden. Keep it in your password manager.

The initializer:

- Creates `instance/hogwards.db` with an empty school dataset and one administrator.
- Generates a persistent random signing key in private, Git-ignored `.env`.
- Sets production mode, HTTPS cookies, CSRF, login rate limiting, and no demo shortcuts.
- Gives the database and configuration owner-only file permissions.
- Refuses to overwrite existing configuration/data. Rerunning the shell script preserves an existing installation and checks it instead.

**Do not run `db/seed.py` or copy a local `.db` into production. Do not copy `.env.example` before initialization.** The shared `admin/admin123`, `faculty/faculty123`, and `student/student123` demo credentials do not exist in this installation.

## 3. Publish through the Web tab

The setup script prints the exact paths and Python version for your account. Follow PythonAnywhere's [manual Flask/virtualenv configuration](https://help.pythonanywhere.com/pages/Flask/):

1. **Web → Add a new web app → Manual configuration.** Choose the same Python version printed by the setup script.
2. Set **Virtualenv** to the printed `.venv` path.
3. Set **Source code** and **Working directory** to the printed project directory.
4. Add the static mapping `/static/` to the project's `static` directory. **Never expose the project root, `.env`, `instance`, or `backups` as static directories.**
5. Replace the Web tab's WSGI file with the three lines printed by setup. They add your actual project path and import `application` from `wsgi.py`.
6. Enable **Force HTTPS**, then click **Reload**.

Do not start Gunicorn or `python app.py` in a background console on this host. PythonAnywhere serves the application through its WSGI worker.

## 4. Verify the actual published site

Use the HTTPS URL shown by PythonAnywhere, not an Arena preview URL.

- Open `/healthz`: it should return `"status": "ok"` and the NIST University application name, with no personal records.
- Open `/login`: there should be **no demo buttons**.
- Sign in with the private credentials you chose in step 2.
- Open the dashboard: all school counts should initially be zero.
- Add your first department, faculty member, course, and offering.
- Record an application in **Admissions → New application**, then approve it with the actual date of birth. Save/share the generated student credentials privately.
- Enroll the student in an offering; mark attendance; create an examination and save results.
- Configure a fee structure before recording a payment.
- Check the student account can open its own profile but not the campus directory or finance administration.
- Sign out, reload, and confirm that staff screens require authentication.

The repository tests exercise the fresh-install workflow against a disposable local database. They are not a substitute for these live-host checks. The hosting URL cannot be claimed as deployed until the Web-tab configuration and HTTPS verification succeed.

## If the published site does not load

| Symptom                                              | Check                                                                                                                                                                   |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 502 / 504, or “Something went wrong”                 | Web tab → **Error log**. Usually the WSGI path above is wrong, the virtualenv is not selected, or `.env` is missing because setup was not run in the project directory. |
| `RuntimeError: Initialize the private installation…` | `scripts/setup_pythonanywhere.sh` never completed (or `.env` was deleted). Re-run it in a Bash console; it preserves existing data.                                     |
| Login page loads but CSS/artwork is missing          | The `/static/` mapping must point at the project's **`static`** folder, ending in `/static`, not the project root.                                                      |
| Sign-in returns “Your session expired”               | CSRF cookie missing. Confirm Force HTTPS is on, the site is opened over `https://`, and `COOKIE_SECURE="true"` remains in `.env`.                                       |
| Everything redirects to `/login` after signing in    | Cookies are blocked or the browser is on `http://`. Use the HTTPS URL.                                                                                                  |
| `Disk quota exceeded`                                | Free accounts have 512 MiB. Remove unused old backups after downloading them; keep `instance/hogwards.db`.                                                              |
| Site suddenly stops                                  | Free web apps expire monthly. Renew in the Web tab before the listed date.                                                                                              |

Change the administrator password, or add staff accounts, only through the application. Do not edit `app_user` rows by hand.

## Signing in (and what to do if the password is lost)

The production site has exactly the accounts you created — there are **no** `admin`/`faculty`/`student` demo logins on it.

- **Administrator username:** the one you typed during setup (for example `omprakash`).
- **Password:** the 12+ character password typed into the hidden prompt during setup. It is never stored in plaintext, printed, or sent anywhere, so it cannot be recovered — only reset.

To reset it, in a Bash console:

```bash
cd ~/hogwards-student-management-system
git pull --ff-only origin arena/e027de8b-dbms-project-deploy
.venv/bin/python scripts/reset_password.py
```

Type the username (`omprakash`), then the new password twice. Sign in at `https://YOURUSERNAME.pythonanywhere.com/login`. Other users' passwords are unchanged, and the account's role is preserved.

The demo shortcuts on the local/development preview (`admin` / `admin123`, etc.) belong to a **separate local database** and do not work on the deployed site.

## Updating an existing published site

Switch the checkout to the branch you want to run, keeping `.env` and
`instance/hogwards.db` untouched (both are ignored by git, so they survive the
switch):

```bash
cd ~/hogwards-student-management-system
git fetch --depth 1 origin arena/40e568c8-dbms-project-deploy   # or: main
git checkout -B deployed FETCH_HEAD
.venv/bin/python -m pip install --no-cache-dir -r requirements-runtime.txt
.venv/bin/python scripts/check_production.py
```

Then click **Reload** in the Web tab. Your administrator account, password, and
all records stay as they were; the new tables (`owner_guard`,
`admin_access_request`, `admin_session`) are created automatically on the first
request after the reload.

### What is new since the first deployment

- The portal reads **NIST University Portal Management**.
- **Reports & PDF**, **Raw data** and the **SQL console** (`/raw-data/query`).
- **Supreme control** (owner only, `/owner`): live administrator roster, single
  and global sign-out, the administrator sign-in switch, per-account blocks,
  one-time access codes, password resets, removals, and the owner activity trail.
- The sign-in page always shows the access-code box and explains, before anyone
  fails, that other administrators need a code from the owner.

### Set an exact password in one command

To set a specific password without any hidden prompts (for example to match a password you already use elsewhere):

```bash
cd ~/hogwards-student-management-system
.venv/bin/python scripts/reset_password.py --username omprakash --password 'YourNewPassword'
```

The script prints the database path, a weak-password warning when the value is under 12 characters, and `Verified against the database: OK`. Short passwords (8+ characters) are accepted, but a command-line password stays in the shell session history — change it from the hidden prompt afterwards if other people can see that console.

### Set a known administrator password

Passwords are typed at a hidden prompt (never on the command line or in chat):

```bash
cd ~/hogwards-student-management-system
.venv/bin/python scripts/reset_password.py --create-admin
```

Enter the username and type the new password twice. `--create-admin` creates the account if the username does not exist yet; without it, an unknown username is rejected and nothing changes.

If a hidden prompt keeps producing “Invalid username or password”, skip typing altogether:

```bash
.venv/bin/python scripts/reset_password.py --random --create-admin
```

The script prints the database path it is writing to and a one-time password, then verifies it against the stored hash (`Verified against the database: OK`). The database path must be `…/hogwards-student-management-system/instance/hogwards.db`; a different path means the console and the web app are looking at different data.

To test credentials without changing anything:

```bash
.venv/bin/python scripts/reset_password.py --check
```

It reports `MATCH - these credentials work` or `NO MATCH - the stored password is different`, and prints no hashes.

### Staff-chosen passwords for students and faculty

- **Faculty:** the add-faculty dialog has a required _Initial password_ field — the administrator types it.
- **Students:** the add-student dialog has an optional _Portal password_ field. Leave it empty to create the record without portal access, or set one later with the row's reset action.
- **Admissions:** the approval dialog offers an optional password. Leave it blank and the portal generates a one-time password, shown once.
- **Students** sign in with their roll number and that password, and only ever see their own profile, results, attendance, fees, and PDF report.

### Reports

**Reports & PDF** (Campus Operations menu) shows live overall figures, a fee snapshot for administrators, and row counts for every database table. **Download campus PDF** produces the overall report; **Download report PDF** on a student profile produces that student's report card. Administrators can also export any table as CSV (password hashes and photos are excluded).

## Maintenance without deleting records

In the same Bash console:

```bash
cd ~/hogwards-student-management-system
.venv/bin/python scripts/backup.py
# Download the resulting private backup using the Files tab before upgrading.
git pull --ff-only origin arena/e027de8b-dbms-project-deploy
.venv/bin/python -m pip install --no-cache-dir -r requirements-runtime.txt
.venv/bin/python scripts/check_production.py
```

Then **Web → Reload**. `.env` and `instance/hogwards.db` remain in place across updates. Never run `git clean -fdx`, delete the project directory, or reseed a production database.

Download and retain private backups regularly; free accounts do not provide the scheduled-task feature needed for an automatic backup job. Restore only after stopping the web app and following `scripts/restore.py --help`. Keep backups out of Git and remove old hosted copies only after checking the downloaded backups to stay within the disk quota. [12](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/)

`TRUSTED_PROXY_HOPS=1` is for a hosted reverse-proxy environment. Use `0` if running directly without a trusted proxy. Login throttling uses process-local memory and resets on worker restart; use shared rate-limit storage if scaling to multiple workers.

The original internal database identifier `sims_db`, old CSS class names, and the historical ZIP are retained for compatibility. They are not the portal's displayed name and are not used to seed this private installation.


## The supreme administrator and the administrator codes

`instance/hogwards.db` gains three small tables automatically (`owner_guard`,
`admin_access_request`, `admin_session`); there is no migration to run.

**Two doors.** Everyone on campus signs in at `/login`. The supreme administrator
signs in at **`/supreme`** with their own username and password — that page refuses
every other account, and `/login` sends the supreme account here if they try it.

### 1. Create the accounts (once)

In a Bash console:

```bash
cd ~/hogwards-student-management-system
source .venv/bin/activate
python scripts/setup_admins.py            # dry run — shows what would be created
python scripts/setup_admins.py --apply    # writes the accounts
```

That creates:

| Account | Password | Where | Code needed? |
| --- | --- | --- | --- |
| `om-2026` | `Superadmin123` | `/supreme` | — |
| `omprakash` | `Adminom123` | `/login` | no |
| `swaruppradhan` | `Adminpradhan123` | `/login` | yes |
| `avashbadatya` | `Adminavash123` | `/login` | yes |
| `aryandash` | `Adminaryan123` | `/login` | yes |

Passwords are hashed with bcrypt; nothing is printed back. Re-running the script is
safe and idempotent — it also puts the passwords above back on accounts that already
exist, so an existing `omprakash` keeps working with `Adminom123`. Add
`--keep-passwords` if you would rather leave existing passwords alone. Change any of
these later with `python scripts/reset_password.py --username NAME`.

### 2. `.env`

```
OWNER_USERNAME=om-2026
OTP_EXEMPT_ADMINS=omprakash
```

`OWNER_USERNAME` is the supreme account (the setup script corrects a stale value for
you). `OTP_EXEMPT_ADMINS` lists administrators who sign in with a password only —
everyone else listed as an admin must also type a code.

### 3. Reload and use it

Click **Reload** in the Web tab, then:

1. Open **`/supreme`** and sign in as `om-2026`.
2. When another administrator signs in with their password, their request appears
   under **Access codes** on the dashboard. Press **Issue code** and read them the
   six digits — it works once, for 15 minutes.
3. **Sign out** ends that administrator's session immediately; **Remove admin**
   deletes the account; **Close administrator sign-in** refuses all of them at once.

The **master key** is optional. Set one and every action on the dashboard asks for it
again; until you do, the supreme password alone is enough. Recover or replace it from
a console with `python scripts/owner_key.py --generate`.

Note: students and faculty are unaffected by any of this — they sign in with their
password only, at `/login`.
