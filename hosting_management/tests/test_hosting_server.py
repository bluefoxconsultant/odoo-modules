from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("hosting_management", "hosting_server")
class TestHostingServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Server = cls.env["hosting.server"]

    def _make(self, **overrides):
        vals = {
            "name": "Production 1",
            "code": "P1",
            "hostname": "prod1.example.com",
        }
        vals.update(overrides)
        return self.Server.create(vals)

    # --- Lifecycle ---

    def test_create_defaults(self):
        s = self._make()
        self.assertEqual(s.state, "active")
        self.assertEqual(s.server_type, "production")
        self.assertEqual(s.ssh_user, "root")
        self.assertEqual(s.ssh_port, 22)

    def test_action_set_maintenance_changes_state(self):
        s = self._make()
        s.action_set_maintenance()
        self.assertEqual(s.state, "maintenance")

    def test_action_decommission_changes_state(self):
        s = self._make()
        s.action_decommission()
        self.assertEqual(s.state, "decommissioned")

    # --- SQL constraints ---

    def test_code_uniqueness(self):
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        self._make()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._make(hostname="other.example.com")

    def test_hostname_uniqueness(self):
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        self._make()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._make(code="PT2")

    # --- Hostname validation ---

    def test_hostname_valid_fqdn(self):
        """Standard FQDNs should be accepted."""
        self._make(hostname="valid.example.com", code="V1")

    def test_hostname_rejects_spaces(self):
        with self.assertRaises(ValidationError):
            self._make(hostname="bad hostname", code="BAD")

    def test_hostname_rejects_special_chars(self):
        with self.assertRaises(ValidationError):
            self._make(hostname="bad$host.com", code="BAD")

    # --- IP address validation ---

    def test_ip_address_valid_ipv4(self):
        s = self._make(ip_address="192.168.1.1")
        self.assertEqual(s.ip_address, "192.168.1.1")

    def test_ip_address_valid_ipv6(self):
        s = self._make(ip_address="2001:db8::1")
        self.assertEqual(s.ip_address, "2001:db8::1")

    def test_ip_address_rejects_invalid(self):
        with self.assertRaises(ValidationError):
            self._make(ip_address="not-an-ip")

    # --- Computed counts ---

    def test_service_count_zero_for_new_server(self):
        s = self._make()
        self.assertEqual(s.service_count, 0)

    # --- Actions returning act_window ---

    def test_action_view_services_returns_act_window(self):
        s = self._make()
        action = s.action_view_services()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "hosting.service")
        self.assertIn(("server_id", "=", s.id), action["domain"])
