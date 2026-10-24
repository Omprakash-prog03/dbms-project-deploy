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
