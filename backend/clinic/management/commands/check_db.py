"""
Verify the database connection and that the expected clinic tables are
reachable. Run after filling in .env:  python manage.py check_db
"""

from django.core.management.base import BaseCommand
from django.db import connection

from clinic import models

TABLES = [
    ("patients", models.Patient),
    ("appointments", models.Appointment),
    ("episodes", models.Episode),
    ("episode_steps", models.EpisodeStep),
    ("followup_seen_episodes", models.FollowupSeenEpisode),
    ("encounters", models.Encounter),
    ("staff", models.Staff),
    ("bank_staff", models.BankStaff),
    ("roster", models.Roster),
    ("leave_records", models.LeaveRecord),
    ("bank_staff_assignments", models.BankStaffAssignment),
    ("public_holidays", models.PublicHoliday),
]


class Command(BaseCommand):
    help = "Test the DB connection and report row counts for each clinic table."

    def handle(self, *args, **options):
        engine = connection.settings_dict.get("ENGINE", "")
        name = connection.settings_dict.get("NAME", "")
        host = connection.settings_dict.get("HOST", "")

        self.stdout.write(f"Engine : {engine}")
        self.stdout.write(f"Host   : {host or '(local)'}")
        self.stdout.write(f"Name   : {name}")
        self.stdout.write("")

        if "sqlite" in engine:
            self.stdout.write(self.style.WARNING(
                "Using the local sqlite fallback — no MYSQL_HOST or PGHOST is set in "
                ".env. This is fine for local testing; set the MySQL vars to point at "
                "your PythonAnywhere database."
            ))

        try:
            connection.ensure_connection()
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"Could not connect: {exc}"))
            return

        self.stdout.write(self.style.SUCCESS("Connection OK. Table row counts:"))
        ok = 0
        missing = 0
        for table, model in TABLES:
            try:
                count = model.objects.count()
                self.stdout.write(f"  {table:<24} {count:>7} rows")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                missing += 1
                self.stdout.write(self.style.ERROR(f"  {table:<24} ERROR: {exc}"))

        self.stdout.write("")
        if ok == len(TABLES):
            self.stdout.write(self.style.SUCCESS(f"All {ok} tables present. You're ready to run the server."))
        else:
            self.stdout.write(self.style.WARNING(
                f"{ok}/{len(TABLES)} tables present. Missing tables usually just mean the "
                "schema hasn't been created yet — run:  python manage.py migrate"
            ))
