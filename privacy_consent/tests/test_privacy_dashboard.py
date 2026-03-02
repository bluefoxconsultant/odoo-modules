from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("privacy_consent", "privacy_dashboard")
class TestPrivacyDashboard(TransactionCase):
    """Test cases for Privacy Dashboard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
            "email": "test@example.com",
        })
        cls.purpose = cls.env["privacy.purpose"].create({
            "code": "TEST",
            "name": "Test Purpose",
            "default_validity_days": 365,
        })

    def test_dashboard_stats_empty(self):
        """Test dashboard with no data."""
        Dashboard = self.env["privacy.dashboard"]
        stats = Dashboard._get_dashboard_stats()

        self.assertEqual(stats["pending_requests"], 0)
        self.assertEqual(stats["granted_consents"], 0)
        self.assertEqual(stats["consent_rate"], 0)

    def test_dashboard_stats_with_consents(self):
        """Test dashboard statistics calculation."""
        Consent = self.env["privacy.consent"]
        Dashboard = self.env["privacy.dashboard"]

        # Create pending consent
        Consent.create({
            "subject_partner_id": self.partner.id,
            "purpose_id": self.purpose.id,
            "status": "pending",
        })

        # Create granted consent
        Consent.create({
            "subject_partner_id": self.partner.id,
            "purpose_id": self.purpose.id,
            "status": "granted",
            "granted_at": fields.Datetime.now(),
            "expires_at": fields.Datetime.now() + timedelta(days=20),
        })

        stats = Dashboard._get_dashboard_stats()

        self.assertEqual(stats["pending_requests"], 1)
        self.assertEqual(stats["granted_consents"], 1)
        self.assertEqual(stats["expiring_30_days"], 1)

    def test_dashboard_consent_rate(self):
        """Test consent rate calculation."""
        Consent = self.env["privacy.consent"]
        Dashboard = self.env["privacy.dashboard"]

        # Create 3 granted and 1 refused
        for i in range(3):
            Consent.create({
                "subject_partner_id": self.partner.id,
                "purpose_id": self.purpose.id,
                "status": "granted",
                "granted_at": fields.Datetime.now(),
            })

        Consent.create({
            "subject_partner_id": self.partner.id,
            "purpose_id": self.purpose.id,
            "status": "refused",
            "refused_at": fields.Datetime.now(),
        })

        stats = Dashboard._get_dashboard_stats()

        # 3 granted / 4 total = 75%
        self.assertEqual(stats["consent_rate"], 75.0)

    def test_dashboard_action_view_pending(self):
        """Test action to view pending requests."""
        Dashboard = self.env["privacy.dashboard"]
        dashboard = Dashboard.create({})

        action = dashboard.action_view_pending_requests()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "privacy.consent")
        self.assertIn(("status", "=", "pending"), action["domain"])
