from odoo.tests import TransactionCase, tagged


@tagged("bf_gamification", "gamification_badge")
class TestGamificationBadge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["bf.gamification.profile"]
        cls.Badge = cls.env["bf.gamification.badge"]
        cls.UserBadge = cls.env["bf.gamification.user.badge"]

        cls.user = cls.env["res.users"].create({
            "name": "Badge Tester",
            "login": "badge_tester",
            "email": "badge_tester@example.com",
        })
        cls.profile = cls.Profile._get_or_create_profile(cls.user)

    # --- _grant_badge ---

    def test_grant_unique_badge_creates_user_badge(self):
        badge = self.Badge.create({
            "name": "First Login", "unique": True, "xp_reward": 25,
        })
        ub = self.profile._grant_badge(badge)
        self.assertTrue(ub)
        self.assertEqual(ub.user_id, self.user)
        self.assertEqual(ub.badge_id, badge)

    def test_grant_unique_badge_twice_returns_existing(self):
        badge = self.Badge.create({"name": "One-Shot", "unique": True})
        first = self.profile._grant_badge(badge)
        second = self.profile._grant_badge(badge)
        self.assertEqual(first, second)
        ubs = self.UserBadge.search([
            ("user_id", "=", self.user.id),
            ("badge_id", "=", badge.id),
        ])
        self.assertEqual(len(ubs), 1)

    def test_grant_non_unique_badge_allows_multiple(self):
        badge = self.Badge.create({"name": "Repeatable", "unique": False})
        self.profile._grant_badge(badge)
        self.profile._grant_badge(badge)
        ubs = self.UserBadge.search([
            ("user_id", "=", self.user.id),
            ("badge_id", "=", badge.id),
        ])
        self.assertEqual(len(ubs), 2)

    def test_grant_badge_awards_xp_reward(self):
        badge = self.Badge.create({
            "name": "Worth 100 XP", "unique": True, "xp_reward": 100,
        })
        self.profile._grant_badge(badge)
        self.profile.invalidate_recordset()
        self.assertEqual(self.profile.total_xp, 100)
        txn = self.env["bf.gamification.xp.transaction"].search([
            ("user_id", "=", self.user.id), ("source", "=", "badge"),
        ])
        self.assertEqual(len(txn), 1)

    # --- _check_automatic_badges (threshold) ---

    def test_threshold_badge_awarded_when_xp_crosses_threshold(self):
        self.Badge.create({
            "name": "100 XP Milestone",
            "condition_type": "threshold",
            "threshold_field": "total_xp",
            "condition_threshold": 100,
            "unique": True,
        })
        self.profile._award_xp(100, "manual", "Cross threshold")
        ubs = self.UserBadge.search([
            ("user_id", "=", self.user.id),
        ])
        names = ubs.mapped("badge_id.name")
        self.assertIn("100 XP Milestone", names)

    def test_threshold_badge_not_awarded_below_threshold(self):
        self.Badge.create({
            "name": "1000 XP Club",
            "condition_type": "threshold",
            "threshold_field": "total_xp",
            "condition_threshold": 1000,
            "unique": True,
        })
        self.profile._award_xp(50, "manual", "Tiny award")
        ubs = self.UserBadge.search([("user_id", "=", self.user.id)])
        self.assertNotIn("1000 XP Club", ubs.mapped("badge_id.name"))

    def test_threshold_badge_unique_not_regranted(self):
        self.Badge.create({
            "name": "Solo",
            "condition_type": "threshold",
            "threshold_field": "total_xp",
            "condition_threshold": 10,
            "unique": True,
        })
        self.profile._award_xp(10, "manual", "First")
        self.profile._award_xp(10, "manual", "Second")
        ubs = self.UserBadge.search([
            ("user_id", "=", self.user.id),
            ("badge_id.name", "=", "Solo"),
        ])
        self.assertEqual(len(ubs), 1)

    # --- _get_user_progress ---

    def test_user_progress_threshold(self):
        badge = self.Badge.create({
            "name": "Half Way",
            "condition_type": "threshold",
            "threshold_field": "total_xp",
            "condition_threshold": 200,
        })
        self.profile._award_xp(50, "manual", "Quarter")
        progress = badge._get_user_progress(self.user)
        self.assertEqual(progress["current"], 50)
        self.assertEqual(progress["target"], 200)
        self.assertEqual(progress["percent"], 25.0)
        self.assertFalse(progress["earned"])

    def test_user_progress_manual_binary(self):
        badge = self.Badge.create({
            "name": "Manual Only", "condition_type": "manual", "unique": True,
        })
        progress = badge._get_user_progress(self.user)
        self.assertEqual(progress["current"], 0)
        self.assertFalse(progress["earned"])
        self.profile._grant_badge(badge)
        progress = badge._get_user_progress(self.user)
        self.assertEqual(progress["current"], 1)
        self.assertTrue(progress["earned"])
