# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class HostingHealthCheck(models.Model):
    _name = "hosting.health.check"
    _description = "Vérification de santé du service"
    _order = "check_date desc"

    service_id = fields.Many2one(
        comodel_name="hosting.service",
        string="Service",
        required=True,
        ondelete="cascade",
        index=True,
    )
    check_date = fields.Datetime(
        string="Date de vérification",
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    status = fields.Selection(
        selection=[
            ("up", "En ligne"),
            ("degraded", "Dégradé"),
            ("down", "Hors ligne"),
            ("timeout", "Délai dépassé"),
        ],
        string="État",
        required=True,
    )
    response_time_ms = fields.Integer(
        string="Temps de réponse (ms)",
        help="Temps de réponse en millisecondes",
    )
    http_status_code = fields.Integer(
        string="Code de statut HTTP",
    )
    error_message = fields.Text(
        string="Message d'erreur",
    )
    excluded_from_stats = fields.Boolean(
        string="Exclu des statistiques",
        default=False,
        index=True,
        help="Exclure cette vérification du calcul de disponibilité et du tableau "
        "de bord (p. ex. panne due à un enjeu externe : fournisseur réseau, DNS "
        "client, maintenance planifiée par un tiers). L'enregistrement reste "
        "visible dans l'historique.",
    )
    exclusion_reason = fields.Text(
        string="Raison de l'exclusion",
        help="Brève note expliquant pourquoi cette vérification est exclue "
        "(cause externe, nom du fournisseur, numéro d'incident, etc.).",
    )

    # Champs liés pour les rapports
    partner_id = fields.Many2one(
        related="service_id.partner_id",
        store=True,
        index=True,
    )
    software_id = fields.Many2one(
        related="service_id.software_id",
        store=True,
    )

    def action_toggle_exclusion(self):
        """Bascule l'exclusion des statistiques pour les vérifications sélectionnées."""
        for record in self:
            record.excluded_from_stats = not record.excluded_from_stats
            if not record.excluded_from_stats:
                record.exclusion_reason = False
        # Invalidate the cached uptime_30d compute so the service records refresh.
        self.mapped("service_id").invalidate_recordset(["uptime_30d"])
        return True
