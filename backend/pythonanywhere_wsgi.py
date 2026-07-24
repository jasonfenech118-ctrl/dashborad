# =============================================================
# PythonAnywhere WSGI configuration
# -------------------------------------------------------------
# Do NOT run this file directly. On PythonAnywhere:
#   Web tab  ->  "WSGI configuration file"  ->  open the editor
#   ->  delete its contents  ->  paste THIS file's contents
#   ->  change YOURUSERNAME below  ->  Save  ->  Reload.
# =============================================================

import os
import sys

# --- 1. Point this at the backend/ folder inside your cloned repo ---------
#     Adjust the path to match where you cloned it. Common layouts:
#       /home/YOURUSERNAME/dashborad/backend
project_path = "/home/YOURUSERNAME/dashborad/backend"
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# --- 2. Load environment variables from backend/.env ----------------------
#     (settings.py also calls load_dotenv, this is a belt-and-braces load)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_path, ".env"))
except Exception:
    pass

# --- 3. Tell Django which settings module to use --------------------------
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

# --- 4. Hand off to Django ------------------------------------------------
from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
