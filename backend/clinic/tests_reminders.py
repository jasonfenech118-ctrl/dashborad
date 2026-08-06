"""Tests for the Reminders feature. Run:
    python manage.py test clinic.tests_reminders
"""
import datetime

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from . import models, views


class ReminderModelTests(TestCase):
    def test_is_due_and_schedule_display(self):
        R = models.Reminder
        sat = R(frequency=R.WEEKLY, weekday=5, at_time=datetime.time(8, 0), active=True)
        self.assertTrue(sat.is_due_on(datetime.date(2026, 8, 8)))    # a Saturday
        self.assertFalse(sat.is_due_on(datetime.date(2026, 8, 7)))   # Friday
        self.assertEqual(sat.schedule_display, "Every Saturday at 08:00")

        daily = R(frequency=R.DAILY, active=True)
        self.assertTrue(daily.is_due_on(datetime.date(2026, 1, 1)))

        once = R(frequency=R.ONCE, on_date=datetime.date(2026, 8, 10), active=True)
        self.assertTrue(once.is_due_on(datetime.date(2026, 8, 10)))
        self.assertFalse(once.is_due_on(datetime.date(2026, 8, 11)))

        paused = R(frequency=R.DAILY, active=False)
        self.assertFalse(paused.is_due_on(datetime.date(2026, 1, 1)))


class ReminderPageTests(TestCase):
    def test_seeded_mml_reminder_present(self):
        # migration 0011 seeds the weekly MML reminder
        self.assertTrue(models.Reminder.objects.filter(
            title="Weekly MML order (Part 1 & 2)", weekday=5).exists())

    def test_nav_has_reminders_link(self):
        html = self.client.get(reverse("clinic:ordering_forms")).content.decode()
        self.assertIn(reverse("clinic:reminders"), html)

    def test_page_renders_with_form(self):
        html = self.client.get(reverse("clinic:reminders")).content.decode()
        self.assertIn("Add a reminder", html)
        self.assertIn("Weekly MML order", html)   # the seeded one is listed

    def test_create_reminder(self):
        url = reverse("clinic:reminders")
        self.client.post(url, {
            "title": "Monthly stock count", "frequency": "monthly",
            "day_of_month": "1", "at_time": "09:30",
            "recipient_email": "ward@gov.mt", "message": "Count the shelves",
        }, follow=True)
        r = models.Reminder.objects.get(title="Monthly stock count")
        self.assertEqual(r.frequency, "monthly")
        self.assertEqual(r.day_of_month, 1)
        self.assertEqual(r.recipient_email, "ward@gov.mt")
        self.assertEqual(r.at_time, datetime.time(9, 30))
        self.assertEqual(r.schedule_display, "Day 1 of each month at 09:30")

    def test_toggle_repeat_and_delete(self):
        r = models.Reminder.objects.create(title="X", frequency="daily", active=True)
        self.client.post(reverse("clinic:reminder_toggle", args=[r.id]))
        r.refresh_from_db()
        self.assertFalse(r.active)
        self.client.post(reverse("clinic:reminder_toggle", args=[r.id]))
        r.refresh_from_db()
        self.assertTrue(r.active)
        self.client.post(reverse("clinic:reminder_delete", args=[r.id]))
        self.assertFalse(models.Reminder.objects.filter(id=r.id).exists())

    def test_due_reminder_shows_on_dashboard(self):
        models.Reminder.objects.create(title="Daily huddle", frequency="daily", active=True)
        html = self.client.get(reverse("clinic:dashboard")).content.decode()
        self.assertIn("Reminders due today", html)
        self.assertIn("Daily huddle", html)

    def test_send_reminder_email(self):
        r = models.Reminder.objects.create(
            title="Order supplies", frequency="weekly", weekday=5,
            recipient_email="disposablessupplies.mdh@gov.mt",
            message="Send the MML orders.")
        views._send_reminder_email(r)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["disposablessupplies.mdh@gov.mt"])
        self.assertIn("Order supplies", mail.outbox[0].subject)
        self.assertIn("Send the MML orders.", mail.outbox[0].alternatives[0][0])

    def test_send_command_runs(self):
        from django.core.management import call_command
        from io import StringIO
        # A daily reminder with a recipient is due today.
        models.Reminder.objects.create(title="CMD", frequency="daily",
                                       recipient_email="x@gov.mt", active=True)
        out = StringIO()
        call_command("send_due_reminders", stdout=out)
        # At least one email went out and last_sent_at was stamped.
        self.assertTrue(models.Reminder.objects.get(title="CMD").last_sent_at)
        self.assertTrue(len(mail.outbox) >= 1)
