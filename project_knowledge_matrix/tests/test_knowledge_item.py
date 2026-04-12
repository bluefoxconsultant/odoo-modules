from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("project_knowledge_matrix", "knowledge_item")
class TestKnowledgeItem(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Matrix = cls.env["project.knowledge.matrix"]
        cls.Item = cls.env["project.knowledge.item"]
        cls.Section = cls.env["project.knowledge.section"]

        cls.project = cls.env["project.project"].create({"name": "Item Test Project"})
        cls.matrix = cls.Matrix.create({
            "name": "Test Matrix", "project_id": cls.project.id,
        })
        cls.section = cls.Section.search([], limit=1) or cls.Section.create({
            "name": "Generic", "code": "GEN",
        })

    def _make(self, **overrides):
        vals = {
            "matrix_id": self.matrix.id,
            "section_id": self.section.id,
            "decision_id": "A1",
            "name": "Test decision",
        }
        vals.update(overrides)
        return self.Item.create(vals)

    # --- Lifecycle + defaults ---

    def test_default_state_is_pending(self):
        item = self._make()
        self.assertEqual(item.state, "pending")

    def test_create_uppercases_decision_id(self):
        item = self._make(decision_id="a1")
        self.assertEqual(item.decision_id, "A1")

    def test_write_uppercases_decision_id(self):
        item = self._make()
        item.write({"decision_id": "b2"})
        self.assertEqual(item.decision_id, "B2")

    # --- Decision ID validation ---

    def test_decision_id_valid_format(self):
        self._make(decision_id="IN55")

    def test_decision_id_rejects_spaces(self):
        with self.assertRaises(ValidationError):
            self._make(decision_id="A 1")

    def test_decision_id_rejects_hyphens(self):
        with self.assertRaises(ValidationError):
            self._make(decision_id="A-1")

    def test_decision_id_rejects_trailing_letters(self):
        with self.assertRaises(ValidationError):
            self._make(decision_id="A1B")

    # --- SQL uniqueness on (decision_id, matrix_id) ---

    def test_decision_id_unique_per_matrix(self):
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        self._make(decision_id="A1")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._make(decision_id="A1")

    def test_decision_id_can_repeat_across_matrices(self):
        other = self.Matrix.create({"name": "Other", "project_id": self.project.id})
        self._make(decision_id="A1")
        self.Item.create({
            "matrix_id": other.id,
            "section_id": self.section.id,
            "decision_id": "A1",
            "name": "Same id, different matrix",
        })

    # --- State transitions ---

    def test_action_done_sets_completion_date(self):
        item = self._make()
        item.action_done()
        self.assertEqual(item.state, "done")
        self.assertEqual(item.completion_date, fields.Date.today())

    def test_action_reset_clears_completion_date(self):
        item = self._make()
        item.action_done()
        item.action_reset()
        self.assertEqual(item.state, "pending")
        self.assertFalse(item.completion_date)

    def test_action_accept_autofills_decision_date(self):
        item = self._make()
        item.action_accept()
        self.assertEqual(item.state, "accepted")
        self.assertEqual(item.decision_date, fields.Date.today())

    def test_action_toggle_na_roundtrip(self):
        item = self._make()
        item.action_toggle_na()
        self.assertEqual(item.state, "na")
        item.action_toggle_na()
        self.assertEqual(item.state, "pending")

    def test_action_supersede_creates_successor(self):
        item = self._make(decision_id="SUP1")
        action = item.action_supersede()
        self.assertEqual(item.state, "superseded")
        self.assertTrue(item.superseded_by_id)
        self.assertEqual(action["type"], "ir.actions.act_window")

    # --- is_overdue computed ---

    def test_is_overdue_true_for_past_deadline_pending(self):
        past = fields.Date.today() - timedelta(days=5)
        item = self._make(deadline=past)
        item._compute_is_overdue()
        self.assertTrue(item.is_overdue)

    def test_is_overdue_false_for_done_items(self):
        past = fields.Date.today() - timedelta(days=5)
        item = self._make(deadline=past, state="done")
        item._compute_is_overdue()
        self.assertFalse(item.is_overdue)

    def test_is_overdue_false_without_deadline(self):
        item = self._make()
        item._compute_is_overdue()
        self.assertFalse(item.is_overdue)

    # --- is_blocked computed ---

    def test_is_blocked_true_when_blocker_pending(self):
        blocker = self._make(decision_id="B1")
        item = self._make(decision_id="B2", blocked_by_ids=[(6, 0, [blocker.id])])
        item._compute_is_blocked()
        self.assertTrue(item.is_blocked)

    def test_is_blocked_false_when_blocker_done(self):
        blocker = self._make(decision_id="B3", state="done")
        item = self._make(decision_id="B4", blocked_by_ids=[(6, 0, [blocker.id])])
        item._compute_is_blocked()
        self.assertFalse(item.is_blocked)

    # --- action_create_task ---

    def test_action_create_task_requires_project(self):
        # Matrix without project
        bare_matrix = self.Matrix.create({"name": "No Project"})
        item = self.Item.create({
            "matrix_id": bare_matrix.id,
            "section_id": self.section.id,
            "decision_id": "NP1",
            "name": "No project item",
        })
        with self.assertRaises(UserError):
            item.action_create_task()

    def test_action_create_task_links_and_starts(self):
        item = self._make(decision_id="T1")
        action = item.action_create_task()
        self.assertEqual(action["res_model"], "project.task")
        self.assertEqual(item.state, "in_progress")
        self.assertEqual(len(item.task_ids), 1)

    # --- write side effect: clears followup flag on state change ---

    def test_write_state_resets_followup_flag(self):
        item = self._make(followup_activity_created=True)
        item.write({"state": "in_progress"})
        self.assertFalse(item.followup_activity_created)
