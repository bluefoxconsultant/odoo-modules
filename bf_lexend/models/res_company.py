from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    font = fields.Selection(
        selection_add=[("Lexend", "Lexend")],
        ondelete={"Lexend": "set default"},
    )
    report_brand_primary = fields.Char(
        string="Couleur d'avant-plan (marque)",
        default="#714B67",
        help="Couleur d'accent de la marque — utilisée pour les boutons, "
        "liens, badges, barres de progression, bordures d'accent et "
        "bannières de rapports PDF.",
    )
    report_brand_dark = fields.Char(
        string="Couleur d'arrière-plan (marque)",
        default="#212529",
        help="Couleur de fond de la marque — utilisée pour la barre de "
        "navigation, le menu d'apps, les surfaces foncées et les en-têtes "
        "de rapports PDF.",
    )
