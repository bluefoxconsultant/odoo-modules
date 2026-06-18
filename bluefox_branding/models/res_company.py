from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    report_brand_primary = fields.Char(
        string="Couleur primaire (marque)",
        default="#714B67",
        help="Couleur d'accent pour la navbar, les boutons et les courriels brandés "
             "(ex: bannière, bulles, barres). Les rapports PDF utilisent plutôt "
             "« Couleur primaire (PDF) ».",
    )
    report_brand_dark = fields.Char(
        string="Couleur foncée (marque)",
        default="#212529",
        help="Couleur de fond foncée pour les en-têtes de courriels brandés et la navbar. "
             "Les rapports PDF utilisent plutôt « Couleur secondaire (PDF) ».",
    )
    report_brand_logo = fields.Binary(
        string="Logo sur fond foncé (marque)",
        attachment=True,
        help="Logo — idéalement blanc/clair — utilisé sur les fonds FONCÉS : en-têtes "
             "de courriels brandés et pages publiques. Le logo standard de la société "
             "(souvent en couleur) reste utilisé sur les documents à fond clair. "
             "Si vide, le logo standard est utilisé partout.",
    )

    brand_email_tagline = fields.Char(
        string="Tagline de marque (courriels)",
        help=(
            "Courte phrase d'accroche affichée sous le nom de la société dans le pied "
            "des courriels brandés. Laissez vide pour utiliser l'en-tête du rapport."
        ),
    )
    brand_email_footer_html = fields.Html(
        string="Pied de page personnalisé (courriels)",
        sanitize=False,
        help=(
            "HTML qui remplace la ligne automatique courriel · téléphone · site web "
            "dans le pied des courriels brandés. Laissez vide pour utiliser les "
            "coordonnées de la société."
        ),
    )
    brand_email_signature_default = fields.Html(
        string="Signature par défaut (courriels)",
        sanitize=False,
        help=(
            "Signature HTML utilisée dans le bloc signature des courriels brandés "
            "quand l'utilisateur n'a pas de signature personnelle. Laissez vide pour "
            "le comportement Odoo standard."
        ),
    )
    brand_privacy_url = fields.Char(
        string="Lien politique de confidentialité (courriels)",
        help=(
            "URL affichée dans le pied des courriels brandés. Laissez vide pour "
            "masquer le lien."
        ),
    )
    brand_terms_url = fields.Char(
        string="Lien conditions (courriels)",
        help=(
            "URL affichée dans le pied des courriels brandés. Laissez vide pour "
            "masquer le lien."
        ),
    )
    favicon = fields.Binary(
        string="Favicon",
        attachment=True,
        help=(
            "Favicon affiché dans les onglets du navigateur pour les rapports web "
            "de la société. Si vide, le logo est utilisé."
        ),
    )
