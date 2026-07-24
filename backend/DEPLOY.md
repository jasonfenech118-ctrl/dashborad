# Deploying to PythonAnywhere

This guide puts the Django backend live on **PythonAnywhere**, connected to your
existing **Supabase** Postgres database.

---

## 0. Which PythonAnywhere plan?

Your data lives in Supabase (an external Postgres host reached over the internet).

| Plan | Outbound access | Works with Supabase? |
|------|-----------------|----------------------|
| **Free ($0)** | Whitelisted HTTP/HTTPS sites only. Raw database connections to external hosts are blocked. | ❌ No — Django will fail to connect. |
| **Hacker (~$5/mo)** | Unrestricted outbound. | ✅ Yes — recommended. |

**Use the Hacker plan** (or higher) so Django can reach Supabase. The free plan
only works if you abandon Supabase and use PythonAnywhere's bundled database,
which would mean migrating your data — not recommended.

---

## 1. Get your Supabase connection details

Supabase dashboard → **Project Settings → Database → Connection info**.

Prefer the **Connection Pooler** (Session mode) values for a web app:
- Host: `aws-0-<region>.pooler.supabase.com` (or your project's pooler host)
- Port: `6543`
- Database: `postgres`
- User: `postgres.<your-project-ref>`
- Password: your database password

(The direct connection on port `5432` also works on the Hacker plan; the pooler
just handles many short web requests better.)

---

## 2. On PythonAnywhere: clone and install

Open a **Bash console** on PythonAnywhere:

```bash
git clone https://github.com/jasonfenech118-ctrl/dashborad.git
cd dashborad/backend

# Create a virtualenv (match the Python version you'll select in the Web tab)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Create the `.env` file

```bash
cp .env.example .env
nano .env      # or use the PythonAnywhere Files editor
```

Fill in:

```
DJANGO_SECRET_KEY=<a long random string>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=YOURUSERNAME.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://YOURUSERNAME.pythonanywhere.com

PGHOST=aws-0-<region>.pooler.supabase.com
PGPORT=6543
PGDATABASE=postgres
PGUSER=postgres.<your-project-ref>
PGPASSWORD=<your database password>
PGSSLMODE=require
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 4. Verify the connection, migrate, create admin

```bash
python manage.py check_db          # should list row counts for all 12 tables
python manage.py migrate           # creates only Django auth/session tables
python manage.py createsuperuser   # your admin login
python manage.py collectstatic --noinput
```

If `check_db` reports a connection error, re-check the Supabase host/password
and that you're on the Hacker plan.

---

## 5. Configure the Web app

PythonAnywhere **Web** tab → **Add a new web app**:

1. Choose **Manual configuration** (not the Django auto-setup) → **Python 3.11**.
2. **Virtualenv** section → set the path:
   `/home/YOURUSERNAME/dashborad/backend/.venv`
3. **Code** section → **WSGI configuration file** → open the editor, delete the
   contents, and paste the contents of `backend/pythonanywhere_wsgi.py`.
   Change `YOURUSERNAME` in that file to your actual username.
4. **Static files** → add a mapping:
   - URL: `/static/`
   - Directory: `/home/YOURUSERNAME/dashborad/backend/staticfiles`
5. Click the big green **Reload** button.

Visit **https://YOURUSERNAME.pythonanywhere.com/admin/** — you should be able to
log in and see all your live clinic data.

---

## 6. Updating after code changes

```bash
cd ~/dashborad
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt          # if requirements changed
python manage.py migrate                 # if migrations changed
python manage.py collectstatic --noinput # if static changed
```
Then hit **Reload** on the Web tab.

---

## Troubleshooting

- **500 error / DisallowedHost** → check `DJANGO_ALLOWED_HOSTS` in `.env` matches
  your PythonAnywhere domain exactly, and reload.
- **Static files missing (unstyled admin)** → run `collectstatic` and confirm the
  `/static/` mapping path is correct.
- **Database connection timeout** → you're likely on the free plan, or the
  Supabase host/port/password is wrong. Confirm with `python manage.py check_db`.
- **CSRF errors on login** → set `DJANGO_CSRF_TRUSTED_ORIGINS=https://YOURUSERNAME.pythonanywhere.com`.
