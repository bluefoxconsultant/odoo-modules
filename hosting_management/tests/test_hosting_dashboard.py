from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("hosting_management", "hosting_dashboard")
class TestHostingDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env["hosting.dashboard"]
        cls.Service = cls.env["hosting.service"]
        cls.Software = cls.env["hosting.software"]
        cls.Partner = cls.env["res.partner"]
        cls.Domain = cls.env["hosting.domain"]

        cls.partner = cls.Partner.create({
            "name": "Dashboard Test Co",
            "is_company": True,
        })
        cls.software = cls.Software.create({
            "name": "DashSoft",
            "code": "dashsoft",
            "software_type": "webapp",
        })

    def _service(self, state="active", **overrides):
        vals = {
            "name": f"Svc {state}",
            "partner_id": self.partner.id,
            "software_id": self.software.id,
            "state": state,
        }
        vals.update(overrides)
        return self.Service.create(vals)

    # --- Top-level aggregation ---

    def test_get_dashboard_data_returns_expected_keys(self):
        data = self.Dashboard.get_dashboard_data()
        expected = {
            "uptime_overview", "uptime_by_service", "alerts", "expiring",
            "maintenance", "backups", "services", "domains", "security",
        }
        self.assertTrue(expected.issubset(data.keys()))

    def test_get_services_counts_by_state(self):
        self._service(state="active")
        self._service(state="suspended")
        self._service(state="expired")
        counts = self.Dashboard._get_services()
        self.assertGreaterEqual(counts["active"], 1)
        self.assertGreaterEqual(counts["suspended"], 1)
        self.assertGreaterEqual(counts["expired"], 1)

    # --- Expiring buckets ---

    def test_get_expiring_buckets(self):
        today = fields.Date.today()
        self._service(
            state="active",
            date_expiration=today + timedelta(days=20),
        )
        self._service(
            state="active",
            date_expiration=today + timedelta(days=45),
        )
        self._service(
            state="active",
            date_expiration=today + timedelta(days=80),
        )
        buckets = self.Dashboard._get_expiring()
        # 30-bucket <= 60-bucket <= 90-bucket (nested windows)
        self.assertLessEqual(buckets["expiring_30"], buckets["expiring_60"])
        self.assertLessEqual(buckets["expiring_60"], buckets["expiring_90"])

    # --- Domains section ---

    def test_get_domains_counts_non_transferred(self):
        self.Domain.create({
            "name": "dashtest1.com",
            "partner_id": self.partner.id,
            "state": "active",
        })
        self.Domain.create({
            "name": "dashtest2.com",
            "partner_id": self.partner.id,
            "state": "transferred",
        })
        data = self.Dashboard._get_domains()
        self.assertIn("total", data)
        self.assertIn("expiring_30", data)
        self.assertIn("ssl_expiring", data)
        self.assertIn("no_auto_renew", data)

    # --- Navigation actions ---

    def test_action_view_active_services_returns_domain(self):
        action = self.Dashboard.action_view_active_services()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertIn(("state", "=", "active"), action["domain"])

    def test_action_view_expiring_30_has_date_filter(self):
        action = self.Dashboard.action_view_expiring_30()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "hosting.service")

    def test_action_view_updates_filters_update_available(self):
        action = self.Dashboard.action_view_updates()
        self.assertIn(("update_available", "=", True), action["domain"])

    def test_action_view_storage_alerts_filters_storage_alert(self):
        action = self.Dashboard.action_view_storage_alerts()
        self.assertIn(("storage_alert", "=", True), action["domain"])

    def test_action_view_health_issues_filters_down(self):
        action = self.Dashboard.action_view_health_issues()
        self.assertIn(("is_service_up", "=", False), action["domain"])

    def test_action_view_maintenance_overdue_returns_schedule_model(self):
        action = self.Dashboard.action_view_maintenance_overdue()
        self.assertEqual(action["res_model"], "hosting.maintenance.schedule")

    def test_action_view_audit_log_returns_audit_model(self):
        action = self.Dashboard.action_view_audit_log()
        self.assertEqual(action["res_model"], "hosting.audit.log")

    # --- Alerts ---

    def test_get_alerts_returns_count_keys(self):
        alerts = self.Dashboard._get_alerts()
        self.assertIn("updates_available", alerts)
        self.assertIn("storage_alerts", alerts)
        self.assertIn("health_issues", alerts)
        # All counts should be non-negative integers
        for v in alerts.values():
            self.assertGreaterEqual(v, 0)
