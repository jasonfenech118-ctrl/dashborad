#!/usr/bin/env bash
# One-shot setup for the MDH Stoma Care Clinic Django backend.
# Run from the backend/ directory:  ./setup.sh
set -e

cd "$(dirname "$0")"

echo "==> Creating virtual environment (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
  # Generate a real secret key and drop it in.
  SECRET=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
  # Portable in-place edit (works on Linux and macOS).
  python3 - "$SECRET" <<'PY'
import sys, pathlib
secret = sys.argv[1]
p = pathlib.Path(".env")
lines = []
for line in p.read_text().splitlines():
    if line.startswith("DJANGO_SECRET_KEY="):
        line = f"DJANGO_SECRET_KEY={secret}"
    lines.append(line)
p.write_text("\n".join(lines) + "\n")
PY
  echo "    A random DJANGO_SECRET_KEY was generated for you."
  echo "    >>> Now edit .env and fill in your Supabase Postgres credentials (PGHOST, PGPASSWORD, ...)."
else
  echo "==> .env already exists, leaving it untouched"
fi

echo "==> Applying Django auth/session migrations (clinic tables are left to Supabase)"
python3 manage.py migrate

echo ""
echo "Setup complete. Next steps:"
echo "  1. Edit backend/.env with your Supabase database password (if not done yet)."
echo "  2. source .venv/bin/activate"
echo "  3. python3 manage.py check_db        # test the Supabase connection"
echo "  4. python3 manage.py createsuperuser # create your admin login"
echo "  5. python3 manage.py runserver       # then open http://127.0.0.1:8000/"
