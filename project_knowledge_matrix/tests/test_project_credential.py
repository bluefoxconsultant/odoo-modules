from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("project_knowledge_matrix", "project_credential")
class TestProjectCredential(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Credential = cls.env["project.credential"]
        cls.CredType = cls.env["project.credential.type"]

        cls.project = cls.env["project.project"].create({"name": "Cred Test"})
        cls.cred_type = cls.CredType.search([], limit=1) or cls.CredType.create({
            "name": "Test Type", "code": "test",
        })

    def _make(self, **overrides):
        vals = {
            "name": "Test Credential",
            "project_id": self.project.id,
            "type_id": self.cred_type.id,
        }
        vals.update(overrides)
        return self.Credential.create(vals)

    # --- Lifecycle ---

    def test_create_defaults(self):
        c = self._make()
        self.assertEqual(c.state, "active")
        self.assertEqual(c.environment, "production")
        self.assertFalse(c.restricted)

    # --- Password encryption ---

    def test_password_roundtrip(self):
        """Password written in clear should be decryptable back."""
        c = self._make()
        c.password = "s3cr3t!"
        c.flush_recordset()
        # Re-read — compute should decrypt
        c.invalidate_recordset()
        self.assertEqual(c.password, "s3cr3t!")
        # Encrypted storage should not equal plaintext
        self.assertNotEqual(c.password_encrypted, "s3cr3t!")

    def test_password_empty_stays_empty(self):
        c = self._make()
        c._compute_password()
        self.assertFalse(c.password)

    # --- State transitions ---

    def test_action_verify_sets_timestamp_and_active(self):
        c = self._make(state="expiring")
        c.action_verify()
        self.assertEqual(c.state, "active")
        self.assertTrue(c.last_verified)

    def test_action_revoke_changes_state(self):
        c = self._make()
        c.action_revoke()
        self.assertEqual(c.state, "revoked")

    def test_action_reactivate_after_revoke(self):
        c = self._make()
        c.action_revoke()
        c.action_reactivate()
        self.assertEqual(c.state, "active")

    def test_action_rotate_opens_wizard(self):
        c = self._make()
        action = c.action_rotate_password()
        self.assertEqual(action["res_model"], "project.credential.rotate.wizard")
        self.assertEqual(action["target"], "new")

    # --- Expiration compute ---

    def test_is_expired_true_for_past_date(self):
        c = self._make(expiration_date=fields.Date.today() - timedelta(days=1))
        c._compute_expiration_status()
        self.assertTrue(c.is_expired)
        self.assertFalse(c.is_expiring_soon)

    def test_is_expiring_soon_within_30_days(self):
        c = self._make(expiration_date=fields.Date.today() + timedelta(days=15))
        c._compute_expiration_status()
        self.assertFalse(c.is_expired)
        self.assertTrue(c.is_expiring_soon)

    def test_is_not_expiring_beyond_30_days(self):
        c = self._make(expiration_date=fields.Date.today() + timedelta(days=60))
        c._compute_expiration_status()
        self.assertFalse(c.is_expired)
        self.assertFalse(c.is_expiring_soon)

    def test_revoked_credential_never_flagged_expired(self):
        c = self._make(
            state="revoked",
            expiration_date=fields.Date.today() - timedelta(days=30),
        )
        c._compute_expiration_status()
        self.assertFalse(c.is_expired)
        self.assertFalse(c.is_expiring_soon)

    def test_no_expiration_date_is_never_expired(self):
        c = self._make()
        c._compute_expiration_status()
        self.assertFalse(c.is_expired)
        self.assertFalse(c.is_expiring_soon)

    # --- Restricted field visibility ---

    def test_restricted_hides_password_from_non_managers(self):
        """Non-manager users see masked password on restricted credentials."""
        c = self._make(restricted=True)
        c.password = "hidden"
        c.flush_recordset()
        non_manager = self.env["res.users"].create({
            "name": "Basic User", "login": "basic_cred_user",
            "email": "basic@example.com",
            "groups_id": [(4, self.env.ref("base.group_user").id)],
        })
        c_as_user = c.with_user(non_manager)
        c_as_user.invalidate_recordset()
        self.assertEqual(c_as_user.password, "********")
