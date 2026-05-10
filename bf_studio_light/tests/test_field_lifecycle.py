"""Field lifecycle regression tests for bf_studio_light.

Covers create / read / write / unlink and the survival pattern (drop the
underlying ir.model.fields, run the integrity check, verify recovery).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("bf_studio_light", "post_install", "-at_install")
class TestStudioLightLifecycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"]._get("res.partner")

    def test_create_simple_field_and_use(self):
        """Create a date field, write a value, read it back."""
        f = self.env["studio.light.field"].create(
            {
                "label": "Birth date",
                "name": "x_studio_birth_date_test",
                "model_id": self.partner_model.id,
                "field_type": "date",
            }
        )
        self.assertTrue(f.ir_model_field_id, "ir.model.fields should be created")
        self.assertEqual(f.ir_model_field_id.ttype, "date")
        self.assertEqual(f.ir_model_field_id.state, "manual")

        partner = self.env["res.partner"].create({"name": "Test partner"})
        partner.x_studio_birth_date_test = "1990-01-01"
        self.env.invalidate_all()
        self.assertEqual(
            str(self.env["res.partner"].browse(partner.id).x_studio_birth_date_test),
            "1990-01-01",
        )
        f.unlink()

    def test_related_field_no_compute_needed(self):
        """A related field should derive its value automatically."""
        f = self.env["studio.light.field"].create(
            {
                "label": "Parent name",
                "name": "x_studio_parent_name_test",
                "model_id": self.partner_model.id,
                "field_type": "char",
                "is_related": True,
                "related_path": "parent_id.name",
            }
        )
        self.assertEqual(f.ir_model_field_id.related, "parent_id.name")
        self.assertTrue(f.ir_model_field_id.readonly)

        parent = self.env["res.partner"].create({"name": "Parent Co."})
        child = self.env["res.partner"].create(
            {"name": "Child", "parent_id": parent.id}
        )
        self.assertEqual(child.x_studio_parent_name_test, "Parent Co.")
        f.unlink()

    def test_recovery_after_metadata_loss(self):
        """Drop the ir.model.fields row; integrity check must recreate it."""
        f = self.env["studio.light.field"].create(
            {
                "label": "Loss survivor",
                "name": "x_studio_survivor_test",
                "model_id": self.partner_model.id,
                "field_type": "char",
            }
        )
        original_imf = f.ir_model_field_id
        original_imf_name = original_imf.name
        # Detach our reference first so flushing is clean
        f.ir_model_field_id = False
        # Now drop the underlying record via ORM (not raw SQL)
        original_imf.unlink()
        self.env.invalidate_all()
        self.assertFalse(f.ir_model_field_id)

        self.env["studio.light.field"]._ensure_all_provisioned()
        self.env.invalidate_all()
        f = f.browse(f.id)  # re-read
        self.assertTrue(f.ir_model_field_id.exists())
        self.assertEqual(f.ir_model_field_id.name, original_imf_name)
        f.unlink()

    def test_failed_count_field_present(self):
        """The failed_count + auto-deactivate plumbing should be wired.

        The full failure-loop simulation is hard to set up cleanly in a
        TransactionCase (it requires forcing inconsistent SQL state that
        the ORM rejects on flush). We verify the fields exist and that
        the action_toggle_active resets the counter.
        """
        f = self.env["studio.light.field"].create(
            {
                "label": "Tracker check",
                "name": "x_studio_tracker_test",
                "model_id": self.partner_model.id,
                "field_type": "char",
            }
        )
        self.assertEqual(f.failed_count, 0)
        f.failed_count = 5
        f.active = False
        f.action_toggle_active()
        self.assertTrue(f.active)
        self.assertEqual(f.failed_count, 0, "Reactivation should clear failure counter")
        f.unlink()
