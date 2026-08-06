"""Tests for the monthly roster. Run:  python manage.py test clinic.tests_roster"""
import datetime

from django.test import TestCase
from django.urls import reverse

from . import models


class RosterTests(TestCase):
    def test_seeded_staff_and_grid_render(self):
        # migration 0013 seeds the core + overtime staff
        self.assertTrue(models.RosterStaff.objects.filter(full_name="Jason Fenech").exists())
        html = self.client.get(reverse("clinic:roster")).content.decode()
        self.assertIn("Monthly Roster", html)
        self.assertIn("Jacqueline Sammut", html)
        self.assertIn("Tracey Galea", html)
        self.assertIn("Core Staff", html)
        self.assertIn("Overtime Staff", html)
        # legend code present
        self.assertIn("Annual Leave", html)

    def test_nav_link_present(self):
        html = self.client.get(reverse("clinic:library")).content.decode()
        self.assertIn(reverse("clinic:roster"), html)

    def test_add_and_remove_staff(self):
        self.client.post(reverse("clinic:roster_staff_add"), {
            "full_name": "New Nurse", "role": "Staff Nurse",
            "category": "core", "year": "2026", "month": "8"}, follow=True)
        s = models.RosterStaff.objects.get(full_name="New Nurse")
        self.assertEqual(s.category, "core")
        self.assertEqual(s.role, "Staff Nurse")

        self.client.post(reverse("clinic:roster_staff_delete", args=[s.id]),
                         {"year": "2026", "month": "8"})
        self.assertFalse(models.RosterStaff.objects.filter(id=s.id).exists())

    def test_add_requires_name(self):
        before = models.RosterStaff.objects.count()
        self.client.post(reverse("clinic:roster_staff_add"), {"full_name": ""})
        self.assertEqual(models.RosterStaff.objects.count(), before)

    def test_set_update_and_clear_shift(self):
        st = models.RosterStaff.objects.first()
        url = reverse("clinic:roster_shift_set")
        d = "2026-08-10"

        r = self.client.post(url, {"staff_id": str(st.id), "date": d, "code": "L"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["code"], "L")
        sh = models.RosterShift.objects.get(staff=st, date=datetime.date(2026, 8, 10))
        self.assertEqual(sh.code, "L")

        # update the same cell (one row per staff+day)
        self.client.post(url, {"staff_id": str(st.id), "date": d, "code": "OT"})
        self.assertEqual(models.RosterShift.objects.filter(staff=st, date=sh.date).count(), 1)
        self.assertEqual(models.RosterShift.objects.get(staff=st, date=sh.date).code, "OT")

        # clear it
        self.client.post(url, {"staff_id": str(st.id), "date": d, "code": ""})
        self.assertFalse(models.RosterShift.objects.filter(staff=st, date=sh.date).exists())

    def test_bad_code_rejected(self):
        st = models.RosterStaff.objects.first()
        r = self.client.post(reverse("clinic:roster_shift_set"),
                             {"staff_id": str(st.id), "date": "2026-08-11", "code": "ZZZ"})
        self.assertEqual(r.status_code, 400)

    def test_shift_shows_in_grid(self):
        st = models.RosterStaff.objects.filter(category="core").first()
        models.RosterShift.objects.create(staff=st, date=datetime.date(2026, 8, 15), code="M")
        html = self.client.get(reverse("clinic:roster"), {"year": 2026, "month": 8}).content.decode()
        self.assertIn(">M<", html)   # the code rendered in a cell
