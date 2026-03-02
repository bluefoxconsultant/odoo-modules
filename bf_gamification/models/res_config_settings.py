from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gamification_enabled = fields.Boolean(
        string="Activer Fox Quest",
        config_parameter='bf_gamification.gamification_enabled',
        default=True,
    )
    gamification_show_leaderboard = fields.Boolean(
        string="Afficher le classement",
        config_parameter='bf_gamification.show_leaderboard',
        default=True,
    )
    gamification_popup_enabled = fields.Boolean(
        string="Afficher les popups",
        config_parameter='bf_gamification.popup_enabled',
        default=True,
    )
    gamification_sound_enabled = fields.Boolean(
        string="Activer les sons",
        config_parameter='bf_gamification.sound_enabled',
        default=True,
    )
    gamification_streak_reset_days = fields.Integer(
        string="Jours avant reset du streak",
        config_parameter='bf_gamification.streak_reset_days',
        default=2,
    )
    gamification_confetti_enabled = fields.Boolean(
        string="Activer les confettis",
        config_parameter='bf_gamification.confetti_enabled',
        default=True,
    )
