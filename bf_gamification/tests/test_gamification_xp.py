from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("bf_gamification", "gamification_xp")
class TestGamificationXp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Txn = cls.env["bf.gamification.xp.transaction"]
        cls.Profile = cls.env["bf.gamification.profile"]

        cls.user = cls.env["res.users"].create({
            "name": "XP Tester",
            "login": "xp_tester",
            "email": "xp_tester@example.com",
        })
        cls.profile = cls.Profile._get_or_create_profile(cls.user)

    def _txn(self, xp, source="manual", when=None):
        vals = {
            "user_id": self.user.id,
            "xp_amount": xp,
            "source": source,
            "description": "Test",
        }
        if when:
            vals["date"] = when
        return self.Txn.create(vals)

    def test_transaction_creation_defaults_date_now(self):
        before = fields.Datetime.now() - timedelta(seconds=5)
        t = self._txn(10)
        self.assertGreaterEqual(t.date, before)

    def test_compute_xp_sums_transactions(self):
        self._txn(10)
        self._txn(20)
        self._txn(5)
        self.profile._compute_xp()
        self.assertEqual(self.profile.total_xp, 35)

    def test_compute_xp_period_week_includes_recent_only(self):
        today = fields.Date.today()
        week_start = today - timedelta(days=today.weekday())
        self._txn(100, when=fields.Datetime.to_datetime(week_start))
        # Last week, should NOT count
        self._txn(500, when=fields.Datetime.to_datetime(
            week_start - timedelta(days=3)
        ))
        self.profile._compute_xp_periods()
        self.assertEqual(self.profile.xp_this_week, 100)

    def test_compute_xp_period_month_includes_recent_only(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        self._txn(100, when=fields.Datetime.to_datetime(month_start))
        # Previous month, should NOT count
        self._txn(500, when=fields.Datetime.to_datetime(
            month_start - timedelta(days=5)
        ))
        self.profile._compute_xp_periods()
        self.assertEqual(self.profile.xp_this_month, 100)

    # --- _cron_update_streaks ---

    def test_cron_update_streaks_resets_stale_streak(self):
        self.profile.current_streak = 7
        self.profile.longest_streak = 7
        self.profile.last_activity_date = fields.Date.today() - timedelta(days=30)
        self.Profile._cron_update_streaks()
        self.profile.invalidate_recordset()
        self.assertEqual(self.profile.current_streak, 0)
        # Longest should remain
        self.assertEqual(self.profile.longest_streak, 7)

    def test_cron_update_streaks_preserves_recent_streak(self):
        self.profile.current_streak = 3
        self.profile.last_activity_date = fields.Date.today()
        self.Profile._cron_update_streaks()
        self.profile.invalidate_recordset()
        self.assertEqual(self.profile.current_streak, 3)

    # --- Backfill dedup ---

    def test_backfill_respects_existing_reference_dedup(self):
        """_backfill_recent_xp must not duplicate if a transaction with the
        same reference already exists within the window."""
        # Pre-create a transaction as if backfill had already run
        fake_ref = "project.task,99999999"
        self.Txn.create({
            "user_id": self.user.id,
            "xp_amount": 10,
            "source": "task",
            "description": "Seed",
            "reference": fake_ref,
        })
        count_before = self.Txn.search_count([
            ("reference", "=", fake_ref),
        ])
        # Re-running backfill shouldn't create a second entry for that reference
        self.Profile._backfill_recent_xp(hours=96)
        count_after = self.Txn.search_count([
            ("reference", "=", fake_ref),
        ])
        self.assertEqual(count_before, count_after)
