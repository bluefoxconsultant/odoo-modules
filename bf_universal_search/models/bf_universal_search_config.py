from odoo import fields, models


class BfUniversalSearchConfig(models.Model):
    _name = "bf.universal.search.config"
    _description = "Configuration de recherche universelle"
    _order = "sequence, id"

    name = fields.Char(string="Libellé", required=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Modèle",
        required=True,
        ondelete="cascade",
    )
    model_name = fields.Char(
        related="model_id.model",
        string="Nom technique",
        store=True,
    )
    search_fields = fields.Char(
        string="Champs de recherche",
        required=True,
        help="Noms de champs séparés par des virgules (ex: name,email,phone)",
    )
    icon = fields.Char(
        string="Icône FontAwesome",
        default="fa fa-search",
        help="Classe CSS FontAwesome (ex: fa fa-users)",
    )
    category = fields.Char(
        string="Catégorie",
        required=True,
        help="Clé de catégorie pour le regroupement (ex: search_contacts)",
    )
    sequence = fields.Integer(string="Séquence", default=100)
    limit = fields.Integer(
        string="Limite par modèle",
        default=5,
        help="Nombre maximum de résultats retournés par modèle",
    )
    active = fields.Boolean(string="Actif", default=True)
