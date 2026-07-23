# MDH Stoma Care Clinic — Django backend

A Python/Django rewrite of the clinic system. Phase 1 gives you a working
**admin panel and REST API over your existing Supabase database** — no data
migration, both the old app and Django share one Postgres database.

## Why `managed = False`

Every model in `clinic/models.py` maps onto a table that already exists in
Supabase (`managed = False`, `db_table = "..."`). Django therefore **reads and
writes your live data directly** and never tries to create or drop those
tables. Only Django's own auth/session tables are created (see below).

When the rewrite is complete and you no longer use Supabase's client, flip
`managed = True` to let Django own the schema.

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# edit .env — set DJANGO_SECRET_KEY and the Supabase Postgres credentials
# (Supabase dashboard -> Project Settings -> Database -> Connection info)
```

### Run against Supabase (real data)

Set `PGHOST` etc. in `.env`, then:

```bash
python manage.py migrate          # creates ONLY Django auth/session tables
python manage.py createsuperuser  # your admin login
python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ and you can browse and edit every patient,
appointment, episode, follow-up review and encounter.

### Run locally without Supabase (quick look)

Leave `PGHOST` blank in `.env` — Django falls back to a local `db.sqlite3`.
The clinic tables won't exist there (they live in Supabase), but the project,
admin login and dashboard all boot so you can develop the UI.

## Layout

```
backend/
  config/          project settings, urls, wsgi
  clinic/
    models.py      12 models mapped to the existing Supabase tables
    admin.py       admin panel: list views, search, filters, inlines
    api_urls.py    DRF router (viewsets added as endpoints come online)
    urls.py        site URLs
    views.py       landing dashboard
  templates/
  requirements.txt
  .env.example
```

## Roadmap (full rewrite)

1. **Admin + API over existing DB** ✅ (this phase)
2. REST endpoints (DRF viewsets/serializers) for patients, appointments, encounters
3. Server-side forms & validation for the clinical pathways (elective, emergency,
   stoma sitting session, daily reviews, follow-up seen review)
4. Port the front-end screens to Django templates (or point the existing
   `index.html` at the Django API instead of Supabase)
5. Move business rules (episode step transitions, follow-up scheduling) into the
   server so they can't be bypassed
6. Reports / PDF exports
7. Flip `managed = True` and retire the Supabase client
