# MDH Stoma Care Clinic — Django backend

A Python/Django clinic system: an **admin panel, REST API, and patient screens**
backed by a database that **Django owns**. Django manages the schema, so
`migrate` creates every table — it runs on the free PythonAnywhere plan with
PythonAnywhere's bundled MySQL, and on local sqlite out of the box.

## Django owns the schema (`managed = True`)

Every model in `clinic/models.py` is Django-managed (`managed = True`) with an
explicit, readable `db_table`. `manage.py migrate` creates and maintains all 12
clinic tables plus Django's own auth/session tables — the models are the single
source of truth.

## Database backends

The backend is chosen automatically from `.env` (see `.env.example`):

- **MySQL** — set `MYSQL_HOST`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
  (this is the PythonAnywhere path; uses the pure-Python PyMySQL driver).
- **Postgres** — set `PGHOST` etc. instead (e.g. an external Supabase/Postgres;
  needs the PythonAnywhere Hacker plan for outbound access).
- **sqlite** — set neither; Django uses a local `db.sqlite3` file.

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set DJANGO_SECRET_KEY and the MySQL vars (or leave blank for sqlite)
```

Then build the schema and create an admin login:

```bash
python manage.py migrate           # creates ALL tables (Django auth + clinic)
python manage.py check_db          # lists the 12 clinic tables and their row counts
python manage.py createsuperuser   # your admin login
python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ to add and edit patients, appointments,
episodes, follow-up reviews and encounters. The dashboard and patient screens
are at http://127.0.0.1:8000/.

To deploy on PythonAnywhere, follow **`DEPLOY.md`**.

## Layout

```
backend/
  config/          project settings, urls, wsgi (+ PyMySQL shim in __init__)
  clinic/
    models.py      12 Django-managed models (the schema)
    migrations/    0001_initial builds every clinic table
    admin.py       admin panel: list views, search, filters, inlines
    api.py         DRF viewsets
    api_urls.py    DRF router
    urls.py        site URLs
    views.py       dashboard + patient list/detail
    management/commands/check_db.py   DB connection + row-count tester
  templates/
  requirements.txt
  .env.example
  DEPLOY.md
```

## Roadmap

1. **Django-managed schema + admin + API + patient screens** ✅ (done)
2. Server-side forms for the clinical pathways (elective, emergency, stoma
   sitting session, daily reviews, follow-up seen review)
3. Port the tile dashboard / ward workspace screens to Django templates
4. Move business rules (episode step transitions, follow-up scheduling) into the
   server so they can't be bypassed
5. Reports / PDF exports
