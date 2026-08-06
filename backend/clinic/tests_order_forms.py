"""End-to-end tests for the two pre-printed ward ordering forms
(M.M.M.U. top-up and cleaning consumables). Run:
    python manage.py test clinic.tests_order_forms
"""
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from . import models, order_forms, views


class OrderFormTests(TestCase):
    def test_ordering_page_lists_both_new_forms(self):
        html = self.client.get(reverse("clinic:ordering_forms")).content.decode()
        self.assertIn("M.M.M.U. Top-Up List", html)
        self.assertIn("Cleaning Consumables Order", html)
        self.assertIn(reverse("clinic:order_form", args=["mmml-topup"]), html)
        self.assertIn(reverse("clinic:order_form", args=["cleaning"]), html)

    def test_library_has_both_form_buttons(self):
        html = self.client.get(reverse("clinic:library")).content.decode()
        self.assertIn(reverse("clinic:order_form", args=["mmml-topup"]), html)
        self.assertIn(reverse("clinic:order_form", args=["cleaning"]), html)

    def test_topup_form_renders_faithfully(self):
        html = self.client.get(reverse("clinic:order_form", args=["mmml-topup"])).content.decode()
        self.assertIn("M.M.M.U. - IRO TOP-UP SYSTEM LIST, DISPOSABLES", html)
        self.assertIn("disposablessupplies.mdh@gov.mt", html)
        self.assertIn("ALCOHOL WIPES", html)          # a preset item
        self.assertIn("For Office Use Only", html)     # office-use footer
        self.assertIn("Required", html)                # fillable column header

    def test_cleaning_form_renders_faithfully(self):
        html = self.client.get(reverse("clinic:order_form", args=["cleaning"])).content.decode()
        self.assertIn("CLEANING CONSUMABLES ORDER LIST", html)
        self.assertIn("ALUMINIUM FOIL", html)
        self.assertIn("OFFICER I/C", html)
        self.assertIn("Quota", html)

    def test_unknown_slug_404(self):
        self.assertEqual(self.client.get("/ordering/form/nope/").status_code, 404)

    def test_submit_saves_document_and_files_in_library(self):
        url = reverse("clinic:order_form", args=["mmml-topup"])
        r = self.client.post(url, {
            "ext_no": "25454431/2", "note": "Tuesday Team 1",
            "requested_by": "Jason Fenech", "form_date": "2026-08-06",
            # two preset rows (code/description/topup round-trip) + quantities
            "code": ["P2019", "EQ02050", ""],
            "description": ["ALCOHOL WIPES", "BASIC DRESSING PACK STERILE", ""],
            "topup": ["2", "18", ""],
            "required": ["3", "10", ""],
            "supplied": ["", "", ""],
        }, follow=True)
        self.assertEqual(r.status_code, 200)

        doc = models.OrderingDocument.objects.get(form_type="MMML Top-Up (Disposables)")
        self.assertTrue(doc.reference.startswith("MMML-TOPUP-"))
        self.assertEqual(doc.section_ward, "Stoma Care Clinic")
        self.assertEqual(doc.cost_centre, "STO-01")
        self.assertEqual(doc.ext_no, "25454431/2")
        self.assertEqual(doc.delivery_period, "Tuesday Team 1")   # the note
        self.assertEqual(doc.requested_by_name, "Jason Fenech")
        self.assertEqual(doc.recipient_email, "disposablessupplies.mdh@gov.mt")
        # empty third row dropped; the two preset rows kept with their values
        self.assertEqual(len(doc.items), 2)
        self.assertEqual(doc.items[0], {
            "code": "P2019", "description": "ALCOHOL WIPES", "topup": "2",
            "required": "3", "supplied": "",
        })

        # Filed in the Library (email isn't configured under test → requisition)
        lib = models.LibraryDocument.objects.filter(reference=doc.reference)
        self.assertEqual(lib.count(), 1)
        self.assertEqual(lib.first().source, models.LibraryDocument.SOURCE_REQUISITION)

        # The detail page renders with the top-up columns
        detail = self.client.get(reverse("clinic:ordering_document_detail", args=[doc.id]))
        self.assertEqual(detail.status_code, 200)
        body = detail.content.decode()
        self.assertIn("Top Up Quantity", body)
        self.assertIn("ALCOHOL WIPES", body)

    def test_submit_requires_at_least_one_item(self):
        url = reverse("clinic:order_form", args=["cleaning"])
        r = self.client.post(url, {"code": [""], "description": [""]})
        self.assertEqual(r.status_code, 200)   # re-rendered, not redirected
        self.assertEqual(models.OrderingDocument.objects.count(), 0)

    def test_email_renders_and_sends_to_disposables(self):
        """The generic email carries the form's own columns and goes to the
        Disposables & Supplies mailbox."""
        fdef = order_forms.get_form_def("cleaning")
        doc = models.OrderingDocument(
            reference="CLEAN-STO01-20260806-001", form_type=fdef["form_type"],
            section_ward=fdef["section_ward"], cost_centre=fdef["cost_centre"],
            ext_no="4431/2", delivery_period="TEAM 1 - TUESDAY",
            items=[{"code": "10FOIL-005", "description": "ALUMINIUM FOIL",
                    "unit": "PACK", "quota": "5", "demand": "5", "supply": ""}],
            requested_by_name="Jason Fenech", recipient_email=fdef["recipient"],
        )
        views._send_order_form_email(doc, fdef)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["disposablessupplies.mdh@gov.mt"])
        self.assertIn("Cleaning Consumables Order List", msg.subject)
        html = msg.alternatives[0][0]
        self.assertIn("ALUMINIUM FOIL", html)
        self.assertIn("Quota", html)          # column label
        self.assertIn("TEAM 1 - TUESDAY", html)   # the remarks note
