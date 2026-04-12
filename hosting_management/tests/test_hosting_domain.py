from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("hosting_management", "hosting_domain")
class TestHostingDomain(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Domain = cls.env["hosting.domain"]
        cls.partner = cls.env["res.partner"].create({
            "name": "Domain Client", "is_company": True,
        })

    def _make(self, **overrides):
        vals = {
            "name": "example.com",
            "partner_id": self.partner.id,
        }
        vals.update(overrides)
        return self.Domain.create(vals)

    # --- Lifecycle ---

    def test_create_defaults(self):
        d = self._make()
        self.assertEqual(d.state, "active")
        self.assertEqual(d.ssl_type, "none")
        self.assertFalse(d.auto_renew)

    def test_name_uniqueness(self):
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        self._make()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._make()

    # --- Days until expiration ---

    def test_days_until_expiration_positive_for_future_date(self):
        future = fields.Date.today() + timedelta(days=60)
        d = self._make(name="future.com", date_expiration=future)
        d._compute_days_until_expiration()
        self.assertEqual(d.days_until_expiration, 60)

    def test_days_until_expiration_zero_when_no_date(self):
        d = self._make(name="nodate.com")
        d._compute_days_until_expiration()
        self.assertEqual(d.days_until_expiration, 0)

    def test_days_until_expiration_negative_when_past(self):
        past = fields.Date.today() - timedelta(days=10)
        d = self._make(name="past.com", date_expiration=past)
        d._compute_days_until_expiration()
        self.assertEqual(d.days_until_expiration, -10)

    # --- SSL expiration ---

    def test_days_until_ssl_expiry_positive(self):
        future = fields.Date.today() + timedelta(days=45)
        d = self._make(
            name="ssl.com",
            ssl_type="letsencrypt",
            ssl_expiry_date=future,
        )
        d._compute_days_until_ssl_expiry()
        self.assertEqual(d.days_until_ssl_expiry, 45)

    # --- State transitions ---

    def test_action_set_transferred(self):
        d = self._make()
        d.action_set_transferred()
        self.assertEqual(d.state, "transferred")

    def test_action_set_active(self):
        d = self._make()
        d.action_set_transferred()
        d.action_set_active()
        self.assertEqual(d.state, "active")

    # --- Cron: auto-expire ---

    def test_cron_auto_expires_past_due_domains(self):
        past = fields.Date.today() - timedelta(days=5)
        d = self._make(name="expired.com", date_expiration=past)
        self.Domain._cron_check_domain_expirations()
        d.invalidate_recordset()
        self.assertEqual(d.state, "expired")

    def test_cron_does_not_expire_future_domains(self):
        future = fields.Date.today() + timedelta(days=180)
        d = self._make(name="future2.com", date_expiration=future)
        self.Domain._cron_check_domain_expirations()
        d.invalidate_recordset()
        self.assertNotEqual(d.state, "expired")

    def test_cron_creates_activity_for_soon_expiring(self):
        # Within default 60-day warning window
        soon = fields.Date.today() + timedelta(days=30)
        d = self._make(name="soon.com", date_expiration=soon)
        self.Domain._cron_check_domain_expirations()
        d.invalidate_recordset()
        self.assertTrue(d.domain_activity_created)
        # Should have flipped to expiring_soon
        self.assertEqual(d.state, "expiring_soon")

    def test_cron_dedup_does_not_recreate_activity(self):
        soon = fields.Date.today() + timedelta(days=30)
        d = self._make(name="dedup.com", date_expiration=soon)
        self.Domain._cron_check_domain_expirations()
        initial = self.env["mail.activity"].search_count([
            ("res_model", "=", "hosting.domain"),
            ("res_id", "=", d.id),
        ])
        self.Domain._cron_check_domain_expirations()
        after = self.env["mail.activity"].search_count([
            ("res_model", "=", "hosting.domain"),
            ("res_id", "=", d.id),
        ])
        self.assertEqual(initial, after)

    # --- Actions ---

    def test_action_view_services_returns_act_window(self):
        d = self._make()
        action = d.action_view_services()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "hosting.service")
