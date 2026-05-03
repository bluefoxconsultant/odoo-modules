from odoo import api, fields, models


class BfNoteLink(models.Model):
    _name = "bf.note.link"
    _description = "Lien d'une note vers une fiche"
    _order = "sequence, id"

    note_id = fields.Many2one("bf.note", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    res_model = fields.Char(string="Modèle", required=True, index=True)
    res_id = fields.Many2oneReference(
        string="ID", model_field="res_model", required=True, index=True
    )
    res_name = fields.Char(string="Nom de la fiche", compute="_compute_res_name", store=True)

    _sql_constraints = [
        (
            "uniq_note_target",
            "unique(note_id, res_model, res_id)",
            "Cette note est déjà liée à cette fiche.",
        ),
    ]

    @api.depends("res_model", "res_id")
    def _compute_res_name(self):
        for link in self:
            if link.res_model and link.res_id and link.res_model in self.env:
                try:
                    rec = self.env[link.res_model].sudo().browse(link.res_id).exists()
                    link.res_name = rec.display_name if rec else False
                except Exception:
                    link.res_name = False
            else:
                link.res_name = False

    def action_open(self):
        self.ensure_one()
        if not (self.res_model and self.res_id and self.res_model in self.env):
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "views": [(False, "form")],
            "target": "current",
        }
