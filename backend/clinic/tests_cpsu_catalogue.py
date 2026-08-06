"""End-to-end tests for the CPSU Appliance & Accessories catalogue and the
Product Specifications register. Run: python manage.py test clinic.tests_cpsu_catalogue
"""
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from . import models


class CpsuCatalogueTests(TestCase):
    def test_cpsu_landing_shows_new_buttons(self):
        html = self.client.get(reverse("clinic:cpsu")).content.decode()
        self.assertIn("Appliance &amp; Accessories", html)
        self.assertIn("Product Specifications", html)
        self.assertIn(reverse("clinic:cpsu_appliances"), html)
        self.assertIn(reverse("clinic:cpsu_specifications"), html)

    def test_add_search_and_delete_appliance(self):
        url = reverse("clinic:cpsu_appliances")
        self.assertEqual(self.client.get(url).status_code, 200)

        r = self.client.post(url, {
            "item_type": "accessory", "name": "Barrier ring",
            "brand": "Salts", "product_code": "XR100",
            "category": "accessory / seal", "size": "48 mm",
            "on_contract": "1",
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        item = models.ApplianceCatalogueItem.objects.get(name="Barrier ring")
        self.assertEqual(item.item_type, "accessory")
        self.assertTrue(item.on_contract)
        self.assertEqual(item.created_by_username, "stoma")

        # Appears in the list, and search by brand finds it.
        self.assertIn("Barrier ring", self.client.get(url).content.decode())
        self.assertIn("Barrier ring", self.client.get(url, {"q": "Salts"}).content.decode())
        # Filtering by the other type hides it.
        self.assertNotIn("Barrier ring",
                         self.client.get(url, {"type": "appliance"}).content.decode())

        # Name is required.
        self.client.post(url, {"name": ""})
        self.assertEqual(models.ApplianceCatalogueItem.objects.count(), 1)

        # Delete.
        self.client.post(reverse("clinic:cpsu_appliance_delete", args=[item.id]))
        self.assertEqual(models.ApplianceCatalogueItem.objects.count(), 0)

    def test_add_search_and_delete_specification(self):
        url = reverse("clinic:cpsu_specifications")
        self.assertEqual(self.client.get(url).status_code, 200)

        title = "ZZ-Pouch-Reference-Item"  # distinctive: no form placeholder collision
        self.client.post(url, {
            "title": title, "product_group": "colostomy appliances",
            "reference": "SPEC-COL-01",
            "specification": "CE-marked; integral filter; latex-free.",
            "mandatory": "1",
        }, follow=True)
        spec = models.ProductSpecification.objects.get(title=title)
        self.assertTrue(spec.mandatory)
        self.assertEqual(spec.reference, "SPEC-COL-01")

        self.assertIn(title, self.client.get(url).content.decode())
        self.assertIn(title, self.client.get(url, {"q": "filter"}).content.decode())
        self.assertNotIn(title, self.client.get(url, {"q": "nomatch-xyz"}).content.decode())

        self.client.post(reverse("clinic:cpsu_specification_delete", args=[spec.id]))
        self.assertEqual(models.ProductSpecification.objects.count(), 0)

    def test_pages_survive_missing_tables(self):
        """A dropped table must not abort the request (the _safe_query guard)."""
        with connection.cursor() as c:
            c.execute("DROP TABLE appliance_catalogue")
            c.execute("DROP TABLE product_specifications")
        for name in ("clinic:cpsu_appliances", "clinic:cpsu_specifications", "clinic:cpsu"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 200, name)
        self.assertIn("temporarily unavailable",
                      self.client.get(reverse("clinic:cpsu_appliances")).content.decode())
