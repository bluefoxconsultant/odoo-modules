"""Bridge setting: post-loss survey program."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bf_cx_loss_program_id = fields.Many2one(
        "bf.cx.program",
        string="Programme post-perte",
        config_parameter="bf_cx.loss_program_id",
        help="Programme dont le sondage est envoyé au contact quand une "
             "opportunité est marquée perdue. Vide = aucun envoi.",
    )
