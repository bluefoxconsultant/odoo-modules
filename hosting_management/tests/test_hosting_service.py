from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("hosting_management", "hosting_service")
class TestHostingService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Service = cls.env["hosting.service"]
        cls.Software = cls.env["hosting.software"]
        cls.Partner = cls.env["res.partner"]

        cls.partner = cls.Partner.create({
            "name": "Test Client Corp",
            "is_company": True,
        })
        cls.software = cls.Software.create({
            "name": "TestSoft",
            "code": "testsoft",
            "software_type": "webapp",
        })

    def _make(self, **overrides):
        vals = {
            "name": "Test Service",
            "partner_id": self.partner.id,
            "software_id": self.software.id,
        }
        vals.update(overrides)
        return self.Service.create(vals)

    # --- Lifecycle ---

    def test_create_sets_sequence_code(self):
        s = self._make()
        self.assertTrue(s.code)
        self.assertNotEqual(s.code, "New")

    def test_default_state_is_draft(self):
        s = self._make()
        self.assertEqual(s.state, "draft")

    def test_action_activate_transitions_to_active(self):
        s = self._make()
        s.action_activate()
        self.assertEqual(s.state, "active")

    def test_action_suspend_transitions_to_suspended(self):
        s = self._make()
        s.action_activate()
        s.action_suspend()
        self.assertEqual(s.state, "suspended")

    def test_action_cancel_transitions_to_cancelled(self):
        s = self._make()
        s.action_cancel()
        self.assertEqual(s.state, "cancelled")

    # --- SSRF prevention (_check_server_url) ---

    def test_server_url_accepts_public_https(self):
        s = self._make(server_url="https://example.com")
        self.assertEqual(s.server_url, "https://example.com")

    def test_server_url_rejects_non_http_scheme(self):
        with self.assertRaises(ValidationError):
            self._make(server_url="ftp://example.com")

    def test_server_url_rejects_localhost(self):
        with self.assertRaises(ValidationError):
            self._make(server_url="http://localhost/health")

    def test_server_url_rejects_loopback_ip(self):
        with self.assertRaises(ValidationError):
            self._make(server_url="http://127.0.0.1/health")

    def test_server_url_rejects_private_ip(self):
        with self.assertRaises(ValidationError):
            self._make(server_url="http://192.168.1.1/health")

    def test_server_url_rejects_internal_domain(self):
        with self.assertRaises(ValidationError):
            self._make(server_url="https://service.internal")

    def test_server_url_rejects_local_domain(self):
        with self.assertRaises(ValidationError):
            self._make(server_url="https://host.local")

    # --- Version comparison ---

    def test_parse_version_simple(self):
        self.assertEqual(self.Service._parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_with_v_prefix(self):
        self.assertEqual(self.Service._parse_version("v1.2.3"), (1, 2, 3))

    def test_parse_version_hyphen_separator(self):
        self.assertEqual(self.Service._parse_version("18.0-20260131"),
                         (18, 0, 20260131))

    def test_parse_version_none_on_empty(self):
        self.assertIsNone(self.Service._parse_version(""))

    def test_is_version_older_true_when_installed_behind(self):
        self.assertTrue(self.Service._is_version_older("1.2.3", "1.2.4"))

    def test_is_version_older_false_when_equal(self):
        self.assertFalse(self.Service._is_version_older("1.2.3", "1.2.3"))

    def test_is_version_older_false_when_installed_ahead(self):
        self.assertFalse(self.Service._is_version_older("2.0.0", "1.9.9"))

    def test_is_version_older_pads_different_lengths(self):
        # 1.2 should be treated as 1.2.0, older than 1.2.1
        self.assertTrue(self.Service._is_version_older("1.2", "1.2.1"))

    # --- update_available compute ---

    def test_update_available_false_when_frozen(self):
        Version = self.env["hosting.software.version"]
        v_old = Version.create({
            "software_id": self.software.id, "version": "1.0.0",
        })
        self.software.latest_version = "2.0.0"
        s = self._make(
            installed_version_id=v_old.id,
            version_policy="frozen",
        )
        s._compute_update_available()
        self.assertFalse(s.update_available)

    def test_update_available_true_when_behind(self):
        Version = self.env["hosting.software.version"]
        v_old = Version.create({
            "software_id": self.software.id, "version": "1.0.0",
        })
        self.software.latest_version = "2.0.0"
        s = self._make(
            installed_version_id=v_old.id,
            version_policy="manual",
        )
        s._compute_update_available()
        self.assertTrue(s.update_available)

    def test_update_available_false_when_at_latest(self):
        Version = self.env["hosting.software.version"]
        v = Version.create({
            "software_id": self.software.id, "version": "2.0.0",
        })
        self.software.latest_version = "2.0.0"
        s = self._make(
            installed_version_id=v.id,
            version_policy="manual",
        )
        s._compute_update_available()
        self.assertFalse(s.update_available)

    # --- Storage compute ---

    def test_storage_percent_zero_when_no_quota(self):
        s = self._make()
        self.assertEqual(s.storage_used_percent, 0.0)

    def test_storage_percent_computed_from_usage(self):
        s = self._make(storage_quota_gb=100.0, storage_used_gb=80.0)
        s._compute_storage_percent()
        self.assertEqual(s.storage_used_percent, 80.0)

    def test_storage_alert_triggers_above_threshold(self):
        s = self._make(
            storage_quota_gb=100.0,
            storage_used_gb=90.0,
            storage_alert_threshold=80.0,
        )
        s._compute_storage_percent()
        s._compute_storage_alert()
        self.assertTrue(s.storage_alert)

    def test_storage_alert_silent_below_threshold(self):
        s = self._make(
            storage_quota_gb=100.0,
            storage_used_gb=50.0,
            storage_alert_threshold=80.0,
        )
        s._compute_storage_percent()
        s._compute_storage_alert()
        self.assertFalse(s.storage_alert)

    # --- Action methods returning act_window ---

    def test_action_view_update_history_returns_act_window(self):
        s = self._make()
        action = s.action_view_update_history()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "hosting.update.log")

    def test_action_update_to_latest_notifies_when_no_update(self):
        s = self._make()
        result = s.action_update_to_latest()
        # Returns a notification action since update_available is False
        self.assertEqual(result.get("type"), "ir.actions.client")
