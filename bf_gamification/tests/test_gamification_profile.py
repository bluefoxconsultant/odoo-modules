from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("bf_gamification", "gamification_profile")
class TestGamificationProfile(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["bf.gamification.profile"]
        cls.Level = cls.env["bf.gamification.level"]
        cls.UserBadge = cls.env["bf.gamification.user.badge"]
        cls.Badge = cls.env["bf.gamification.badge"]

        cls.user = cls.env["res.users"].create({
            "name": "Fox Tester",
            "login": "foxtester",
            "email": "foxtester@example.com",
        })

        # Ensure deterministic levels for this test class
        cls.level_rookie = cls.Level.search([("min_xp", "=", 0)], limit=1) or \
            cls.Level.create({"name": "Test Rookie", "title": "Test Rookie", "min_xp": 0})
        cls.level_pro = cls.Level.create({
            "name": "Test Pro", "title": "Test Pro", "min_xp": 999_900,
        })
        cls.level_legend = cls.Level.create({
            "name": "Test Legend", "title": "Test Legend", "min_xp": 1_000_000,
        })

    def _profile(self):
        return self.Profile._get_or_create_profile(self.user)

    # --- Profile lifecycle ---

    def test_get_or_create_profile_creates_once(self):
        p1 = self._profile()
        p2 = self._profile()
        self.assertEqual(p1, p2)

    def test_user_unique_constraint(self):
        self._profile()
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.Profile.create({"user_id": self.user.id})

    # --- Showcase constraint ---

    def test_showcase_limit_max_five(self):
        profile = self._profile()
        badge = self.Badge.create({"name": "Test Badge", "unique": False})
        ubs = [self.UserBadge.create({
            "user_id": self.user.id, "badge_id": badge.id,
        }) for _ in range(6)]
        with self.assertRaises(ValidationError):
            profile.showcase_badge_ids = [(6, 0, [u.id for u in ubs])]

    def test_showcase_allows_exactly_five(self):
        profile = self._profile()
        badge = self.Badge.create({"name": "B", "unique": False})
        ubs = [self.UserBadge.create({
            "user_id": self.user.id, "badge_id": badge.id,
        }) for _ in range(5)]
        profile.showcase_badge_ids = [(6, 0, [u.id for u in ubs])]
        self.assertEqual(len(profile.showcase_badge_ids), 5)

    # --- _award_xp ---

    def test_award_xp_creates_transaction_and_updates_total(self):
        profile = self._profile()
        self.assertEqual(profile.total_xp, 0)
        profile._award_xp(50, "manual", "Test award")
        self.assertEqual(profile.total_xp, 50)
        txns = self.env["bf.gamification.xp.transaction"].search([
            ("user_id", "=", self.user.id),
        ])
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns.xp_amount, 50)
        self.assertEqual(txns.source, "manual")

    def test_award_xp_triggers_level_up(self):
        profile = self._profile()
        profile._award_xp(1_000_000, "manual", "Massive award")
        profile.invalidate_recordset()
        self.assertEqual(profile.level_id, self.level_legend)

    def test_total_xp_never_negative(self):
        """Negative XP transactions shouldn't push total below 0."""
        profile = self._profile()
        self.env["bf.gamification.xp.transaction"].create({
            "user_id": self.user.id,
            "xp_amount": -500,
            "source": "manual",
            "description": "Correction",
        })
        profile._compute_xp()
        self.assertEqual(profile.total_xp, 0)

    # --- Streak logic ---

    def test_streak_starts_at_one_on_first_award(self):
        profile = self._profile()
        profile._award_xp(10, "manual", "First")
        self.assertEqual(profile.current_streak, 1)
        self.assertEqual(profile.longest_streak, 1)
        self.assertEqual(profile.last_activity_date, fields.Date.today())

    def test_streak_increments_within_reset_window(self):
        profile = self._profile()
        profile._award_xp(10, "manual", "Day 1")
        # Simulate yesterday's activity
        profile.last_activity_date = fields.Date.today() - timedelta(days=1)
        profile.current_streak = 3
        profile.longest_streak = 3
        profile._award_xp(10, "manual", "Day 2")
        self.assertEqual(profile.current_streak, 4)
        self.assertEqual(profile.longest_streak, 4)

    def test_streak_resets_after_gap(self):
        profile = self._profile()
        profile._award_xp(10, "manual", "Seed")
        # Gap larger than default reset window (2 days)
        profile.last_activity_date = fields.Date.today() - timedelta(days=10)
        profile.current_streak = 5
        profile.longest_streak = 5
        profile._award_xp(10, "manual", "Return")
        self.assertEqual(profile.current_streak, 1)
        # Longest streak is preserved
        self.assertEqual(profile.longest_streak, 5)

    def test_same_day_award_does_not_bump_streak(self):
        profile = self._profile()
        profile._award_xp(10, "manual", "Morning")
        profile._award_xp(10, "manual", "Afternoon")
        self.assertEqual(profile.current_streak, 1)
