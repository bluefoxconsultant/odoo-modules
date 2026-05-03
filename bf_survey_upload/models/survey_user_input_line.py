from odoo import fields, models


class SurveyUserInputLine(models.Model):
    _inherit = "survey.user_input.line"

    bf_attachment_ids = fields.Many2many(
        "ir.attachment",
        "bf_survey_input_line_attachment_rel",
        "line_id",
        "attachment_id",
        string="Fichiers téléversés",
    )
