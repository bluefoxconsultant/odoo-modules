from odoo.tests import TransactionCase, tagged


@tagged("bf_universal_search", "universal_search")
class TestUniversalSearch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Search = cls.env["bf.universal.search"]
        cls.Config = cls.env["bf.universal.search.config"]
        cls.Model = cls.env["ir.model"]

        # Clean slate for deterministic results
        cls.Config.search([]).write({"active": False})

        cls.partner_model = cls.Model._get("res.partner")
        cls.config = cls.Config.create({
            "name": "Contacts",
            "model_id": cls.partner_model.id,
            "search_fields": "name,email",
            "category": "search_contacts",
            "icon": "fa fa-users",
            "limit": 5,
        })
        # Rename an existing partner instead of creating one: in -i mode,
        # bf_universal_search loads before the account module, so res.partner's
        # Python definition lacks account's autopost_bills field and create()
        # fails while write() on existing rows is unaffected.
        cls.partner = cls.env.ref("base.partner_admin")
        cls.partner.write({
            "name": "ZZZ Universal Search Target",
            "email": "usearch@example.com",
        })

    # --- Config model ---

    def test_config_related_model_name(self):
        self.assertEqual(self.config.model_name, "res.partner")

    def test_config_defaults(self):
        c = self.Config.create({
            "name": "Test",
            "model_id": self.partner_model.id,
            "search_fields": "name",
            "category": "t",
        })
        self.assertEqual(c.icon, "fa fa-search")
        self.assertEqual(c.sequence, 100)
        self.assertEqual(c.limit, 5)
        self.assertTrue(c.active)

    # --- search_all ---

    def test_search_all_too_short_query_returns_empty(self):
        self.assertEqual(self.Search.search_all("z"), [])
        self.assertEqual(self.Search.search_all(""), [])

    def test_search_all_finds_matching_partner(self):
        groups = self.Search.search_all("ZZZ Universal")
        # Should have at least the contacts group with our seeded partner
        matching_groups = [g for g in groups if g["model"] == "res.partner"]
        self.assertTrue(matching_groups)
        result_ids = [r["id"] for r in matching_groups[0]["results"]]
        self.assertIn(self.partner.id, result_ids)

    def test_search_all_respects_model_filters(self):
        groups = self.Search.search_all(
            "ZZZ Universal", model_filters=["res.users"]
        )
        # res.partner config should be filtered out
        self.assertEqual(
            [g for g in groups if g["model"] == "res.partner"], []
        )

    def test_search_all_skips_inactive_configs(self):
        self.config.active = False
        groups = self.Search.search_all("ZZZ Universal")
        self.assertEqual(
            [g for g in groups if g["model"] == "res.partner"], []
        )

    def test_search_all_returns_expected_shape(self):
        groups = self.Search.search_all("ZZZ Universal")
        matching = [g for g in groups if g["model"] == "res.partner"]
        self.assertTrue(matching)
        g = matching[0]
        self.assertIn("model_label", g)
        self.assertIn("icon", g)
        self.assertIn("category", g)
        self.assertIn("results", g)
        if g["results"]:
            r = g["results"][0]
            self.assertIn("id", r)
            self.assertIn("name", r)
            self.assertIn("detail", r)
