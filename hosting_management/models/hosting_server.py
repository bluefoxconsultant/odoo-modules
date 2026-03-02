# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class HostingServer(models.Model):
    _name = "hosting.server"
    _description = "Serveur d'hébergement"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Nom du serveur",
        required=True,
        tracking=True,
        help="Nom convivial du serveur (ex. : « Primetime 1 »)",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="Identifiant court (ex. : « PT1 »)",
    )
    hostname = fields.Char(
        string="Nom d'hôte",
        required=True,
        tracking=True,
        help="Nom d'hôte pleinement qualifié (ex. : « server1.example.com »)",
    )
    server_type = fields.Selection(
        selection=[
            ("production", "Production"),
            ("staging", "Préproduction"),
            ("development", "Développement"),
        ],
        string="Type de serveur",
        default="production",
        required=True,
        tracking=True,
    )
    provider = fields.Selection(
        selection=[
            ("hetzner", "Hetzner"),
            ("ovh", "OVH"),
            ("aws", "AWS"),
            ("azure", "Azure"),
            ("gcp", "Google Cloud"),
            ("digitalocean", "DigitalOcean"),
            ("on_premise", "Sur site"),
            ("other", "Autre"),
        ],
        string="Fournisseur",
        tracking=True,
    )
    location = fields.Char(
        string="Emplacement",
        help="Emplacement physique ou centre de données (ex. : « Canada », « EU-West »)",
    )
    ip_address = fields.Char(
        string="Adresse IP",
        help="Adresse IP principale du serveur",
    )
    ssh_user = fields.Char(
        string="Utilisateur SSH",
        default="root",
    )
    ssh_port = fields.Integer(
        string="Port SSH",
        default=22,
    )
    state = fields.Selection(
        selection=[
            ("active", "Actif"),
            ("maintenance", "Maintenance"),
            ("decommissioned", "Décommissionné"),
        ],
        string="État",
        default="active",
        required=True,
        tracking=True,
    )

    # Relations
    service_ids = fields.One2many(
        comodel_name="hosting.service",
        inverse_name="server_id",
        string="Services",
    )
    service_count = fields.Integer(
        string="Nombre de services",
        compute="_compute_service_count",
    )

    # Informations supplémentaires
    notes = fields.Html(
        string="Notes",
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    _sql_constraints = [
        ("code_uniq", "UNIQUE(code)", "Le code du serveur doit être unique !"),
        ("hostname_uniq", "UNIQUE(hostname)", "Le nom d'hôte doit être unique !"),
    ]

    @api.depends("service_ids")
    def _compute_service_count(self):
        for record in self:
            record.service_count = len(record.service_ids)

    def action_view_services(self):
        """Ouvrir les services hébergés sur ce serveur."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Services - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "kanban"], [False, "form"]],
            "domain": [("server_id", "=", self.id)],
            "context": {"default_server_id": self.id},
        }

    def action_set_active(self):
        """Mettre le serveur à l'état actif."""
        self.write({"state": "active"})

    def action_set_maintenance(self):
        """Mettre le serveur en état de maintenance."""
        self.write({"state": "maintenance"})

    def action_decommission(self):
        """Décommissionner le serveur."""
        self.write({"state": "decommissioned"})
