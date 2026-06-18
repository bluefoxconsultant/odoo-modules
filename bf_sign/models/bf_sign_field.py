from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Fields the signing flow is allowed to write once the request has left draft.
# Everything else (placement, type, signer, fill rules) is frozen after sending.
_PROCESS_FIELDS = frozenset({"filled_value"})


class BfSignField(models.Model):
    """A signature pad placed on the document.

    Position is stored as fractions of the page (0..1) measured from the
    TOP-LEFT corner, so it is resolution-independent and maps directly to how
    the placement widget (and PDF.js) render the page in the browser. The
    stamping engine converts these to PDF coordinates (bottom-left origin).
    """

    _name = "bf.sign.field"
    _description = "Pavé de signature"
    _order = "page, sequence, id"

    request_id = fields.Many2one(
        "bf.sign.request", required=True, ondelete="cascade", index=True,
    )
    signer_id = fields.Many2one(
        "bf.sign.signer", string="Signataire", required=True, ondelete="cascade",
    )
    field_type = fields.Selection(
        selection=[
            ("signature", "Signature"),
            ("initials", "Paraphe"),
            ("date", "Date"),
            ("text", "Texte"),
        ],
        string="Type", default="signature", required=True,
    )
    page = fields.Integer(string="Page", default=1, required=True)
    pos_x = fields.Float(string="X (fraction)", default=0.60)
    pos_y = fields.Float(string="Y (fraction)", default=0.80)
    width = fields.Float(string="Largeur (fraction)", default=0.25)
    height = fields.Float(string="Hauteur (fraction)", default=0.08)
    value_text = fields.Char(string="Valeur fixe (texte/date)")
    # How a date/text pad gets its value:
    #   auto   — date pad filled with the signer's signing date
    #   fixed  — value set here by the preparer (``value_text``)
    #   signer — the signer types it on the signing page (stored in ``filled_value``)
    fill_mode = fields.Selection(
        selection=[
            ("auto", "Automatique (date de signature)"),
            ("fixed", "Valeur fixe (préparateur)"),
            ("signer", "Rempli par le signataire"),
        ],
        string="Mode de remplissage", default="signer", required=True,
    )
    required = fields.Boolean(
        string="Obligatoire", default=True,
        help="Pour un champ rempli par le signataire : la saisie est obligatoire.")
    filled_value = fields.Char(string="Valeur saisie", readonly=True, copy=False)
    sequence = fields.Integer(default=10)

    @api.constrains("request_id", "signer_id")
    def _check_signer_request(self):
        for rec in self:
            if rec.signer_id.request_id != rec.request_id:
                raise ValidationError(
                    _("Le signataire d'un pavé doit appartenir à la même demande.")
                )

    # ── Structural lock: pads are frozen once the request leaves draft ──────────
    @staticmethod
    def _assert_draft(requests):
        locked = requests.filtered(lambda r: r.state != "draft")
        if locked:
            raise UserError(_(
                "Les pavés ne peuvent être ajoutés, déplacés ou supprimés qu'en "
                "brouillon. Remettez la demande en brouillon pour la modifier."))

    @api.model_create_multi
    def create(self, vals_list):
        reqs = self.env["bf.sign.request"].browse(
            [v.get("request_id") for v in vals_list if v.get("request_id")])
        self._assert_draft(reqs.exists())
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) - _PROCESS_FIELDS:
            self._assert_draft(self.request_id)
        return super().write(vals)

    def unlink(self):
        self._assert_draft(self.request_id)
        return super().unlink()
