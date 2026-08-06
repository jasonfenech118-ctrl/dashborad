"""Email every reminder that is due today to its recipient.

Intended to be run once a day by a scheduler (e.g. a PythonAnywhere
scheduled task):

    cd ~/dashborad/backend && python manage.py send_due_reminders

Only reminders that are active, due today, have a recipient email, and have
not already been sent today are emailed. Safe to run more than once a day —
it won't send a reminder twice.
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from clinic import models
from clinic.views import _send_reminder_email


class Command(BaseCommand):
    help = "Email reminders that are due today to their recipients."

    def handle(self, *args, **options):
        today = datetime.date.today()
        due = [
            r for r in models.Reminder.objects.filter(active=True)
            if r.is_due_on(today) and r.recipient_email
            and (r.last_sent_at is None or timezone.localtime(r.last_sent_at).date() != today)
        ]
        if not due:
            self.stdout.write("No reminders due to send today.")
            return
        sent = 0
        for r in due:
            try:
                _send_reminder_email(r)
                r.last_sent_at = timezone.now()
                r.save(update_fields=["last_sent_at"])
                sent += 1
                self.stdout.write(self.style.SUCCESS(f"Sent “{r.title}” to {r.recipient_email}"))
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"Failed “{r.title}”: {exc}"))
        self.stdout.write(f"Done — {sent}/{len(due)} reminder(s) sent.")
