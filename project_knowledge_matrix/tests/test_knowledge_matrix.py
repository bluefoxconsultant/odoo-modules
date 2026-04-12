from odoo.tests import TransactionCase, tagged


@tagged("project_knowledge_matrix", "knowledge_matrix")
class TestKnowledgeMatrix(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Matrix = cls.env["project.knowledge.matrix"]
        cls.Item = cls.env["project.knowledge.item"]
        cls.Section = cls.env["project.knowledge.section"]

        cls.project = cls.env["project.project"].create({
            "name": "Test Project",
        })
        # Use any existing section (loaded from data file)
        cls.section = cls.Section.search([], limit=1) or cls.Section.create({
            "name": "Test Section", "code": "T01",
        })

    def _make(self, **overrides):
        vals = {"name": "Test Matrix", "project_id": self.project.id}
        vals.update(overrides)
        return self.Matrix.create(vals)

    def _add_item(self, matrix, decision_id="A1", state="pending"):
        return self.Item.create({
            "matrix_id": matrix.id,
            "section_id": self.section.id,
            "decision_id": decision_id,
            "name": f"Item {decision_id}",
            "state": state,
        })

    # --- Lifecycle ---

    def test_create_defaults(self):
        m = self._make()
        self.assertFalse(m.is_template)
        self.assertTrue(m.active)
        self.assertEqual(m.send_frequency, "monthly")

    def test_create_inherits_project_from_context(self):
        m = self.Matrix.with_context(
            default_project_id=self.project.id
        ).create({"name": "Contextual"})
        self.assertEqual(m.project_id, self.project)

    # --- _compute_statistics ---

    def test_statistics_empty_matrix(self):
        m = self._make()
        self.assertEqual(m.item_count, 0)
        self.assertEqual(m.completed_count, 0)
        self.assertEqual(m.progress, 0.0)

    def test_statistics_counts_only_non_na(self):
        m = self._make()
        self._add_item(m, "A1", "done")
        self._add_item(m, "A2", "pending")
        self._add_item(m, "A3", "na")
        m.invalidate_recordset()
        self.assertEqual(m.item_count, 2)
        self.assertEqual(m.completed_count, 1)
        self.assertEqual(m.pending_count, 1)
        self.assertEqual(m.progress, 50.0)

    def test_statistics_done_and_accepted_both_count(self):
        m = self._make()
        self._add_item(m, "A1", "done")
        self._add_item(m, "A2", "accepted")
        m.invalidate_recordset()
        self.assertEqual(m.completed_count, 2)
        self.assertEqual(m.progress, 100.0)

    def test_statistics_all_na_gives_zero_progress(self):
        m = self._make()
        self._add_item(m, "A1", "na")
        self._add_item(m, "A2", "na")
        m.invalidate_recordset()
        self.assertEqual(m.item_count, 0)
        self.assertEqual(m.progress, 0.0)

    # --- Actions ---

    def test_action_view_items_returns_act_window(self):
        m = self._make()
        action = m.action_view_items()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "project.knowledge.item")
        self.assertIn(("matrix_id", "=", m.id), action["domain"])

    def test_action_duplicate_opens_form(self):
        m = self._make()
        action = m.action_duplicate_to_project()
        self.assertEqual(action["target"], "new")
        self.assertIn("Copy", action["context"]["default_name"])

    # --- Report data ---

    def test_get_report_data_returns_expected_keys(self):
        m = self._make()
        self._add_item(m, "A1", "done")
        self._add_item(m, "A2", "pending")
        data = m._get_report_data()
        for key in ("today", "total", "done", "progress", "sections"):
            self.assertIn(key, data)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["done"], 1)
