# Deploying to PythonAnywhere (Django-managed MySQL)

This puts the Django backend live on **PythonAnywhere**, using PythonAnywhere's
own **MySQL** database. Django owns the schema — `migrate` creates every table
for you — so this works on the **free** PythonAnywhere plan (no external
database, no paid plan needed).

> Prefer to use an external Postgres (e.g. Supabase) instead? See
> "Alternative: Postgres" at the bottom.

---

## 1. On PythonAnywhere: clone and install

Open a **Bash console** (Consoles → Bash):

```bash
git clone https://github.com/jasonfenech118-ctrl/dashborad.git
cd dashborad/backend

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Create a MySQL database

PythonAnywhere **Databases** tab:

1. If you haven't already, **set a MySQL password** (top of the page) and note it.
2. Under "Create a database", the default database is named
   **`YOURUSERNAME$default`** — you can use that, or create a new one, e.g.
   `YOURUSERNAME$clinic`.

Your connection details will be:
- Host: `YOURUSERNAME.mysql.pythonanywhere-services.com`
- User: `YOURUSERNAME`
- Database: `YOURUSERNAME$default` (or the name you created)
- Password: the MySQL password you just set

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

MYSQL_HOST=YOURUSERNAME.mysql.pythonanywhere-services.com
MYSQL_PORT=3306
MYSQL_DATABASE=YOURUSERNAME$default
MYSQL_USER=YOURUSERNAME
MYSQL_PASSWORD=<your MySQL password>
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Save in nano with **Ctrl+O**, **Enter**, then **Ctrl+X**.

---

## 4. Create the schema, verify, create admin

```bash
python manage.py migrate           # creates ALL tables (Django auth + clinic)
python manage.py check_db          # should list all 12 clinic tables at 0 rows
python manage.py createsuperuser   # your admin login
python manage.py collectstatic --noinput
```

`check_db` showing all 12 tables at `0 rows` is exactly right — the schema is
built and empty, ready for you to start entering patients.

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

Visit **https://YOURUSERNAME.pythonanywhere.com/admin/** — log in with the
superuser and start adding data. The dashboard and patient screens are at `/`.

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

- **500 error / DisallowedHost** → `DJANGO_ALLOWED_HOSTS` must match your
  PythonAnywhere domain exactly; reload after editing `.env`.
- **Static files missing (unstyled admin)** → run `collectstatic` and confirm
  the `/static/` mapping path.
- **`check_db` shows missing tables** → run `python manage.py migrate`.
- **Access denied for MySQL** → re-check `MYSQL_PASSWORD` and that
  `MYSQL_DATABASE` matches a database you created on the Databases tab (names
  include the `YOURUSERNAME$` prefix).
- **CSRF errors on login** → set
  `DJANGO_CSRF_TRUSTED_ORIGINS=https://YOURUSERNAME.pythonanywhere.com`.

---

## Alternative: Postgres (e.g. Supabase)

To use an external Postgres instead of PythonAnywhere MySQL, leave the `MYSQL_*`
vars blank and set `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`,
`PGSSLMODE` in `.env` instead. Note this requires the PythonAnywhere **Hacker**
plan (~$5/mo) for outbound access to an external database host; the free plan
blocks it. Everything else (migrate, createsuperuser, Web tab) is identical.
