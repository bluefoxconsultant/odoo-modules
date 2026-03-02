# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    hosting_service_ids = fields.One2many(
        comodel_name="hosting.service",
        inverse_name="partner_id",
        string="Services d'hébergement",
    )
    hosting_service_count = fields.Integer(
        string="Nombre de services d'hébergement",
        compute="_compute_hosting_service_count",
    )
    hosting_services_expiring_count = fields.Integer(
        string="Services expirant",
        compute="_compute_hosting_alerts",
    )
    hosting_services_updates_count = fields.Integer(
        string="Mises à jour disponibles",
        compute="_compute_hosting_alerts",
    )
    hosting_services_storage_alert_count = fields.Integer(
        string="Alertes de stockage",
        compute="_compute_hosting_alerts",
    )

    @api.depends("hosting_service_ids")
    def _compute_hosting_service_count(self):
        for partner in self:
            partner.hosting_service_count = len(partner.hosting_service_ids)

    @api.depends(
        "hosting_service_ids",
        "hosting_service_ids.state",
        "hosting_service_ids.date_expiration",
        "hosting_service_ids.update_available",
        "hosting_service_ids.storage_alert",
    )
    def _compute_hosting_alerts(self):
        today = fields.Date.today()
        warning_date = today + timedelta(days=90)
        for partner in self:
            services = partner.hosting_service_ids.filtered(
                lambda s: s.state == "active"
            )
            partner.hosting_services_expiring_count = len(
                services.filtered(
                    lambda s: s.date_expiration
                    and today < s.date_expiration <= warning_date
                )
            )
            partner.hosting_services_updates_count = len(
                services.filtered(lambda s: s.update_available)
            )
            partner.hosting_services_storage_alert_count = len(
                services.filtered(lambda s: s.storage_alert)
            )

    def action_view_hosting_services(self):
        """Ouvrir les services d'hébergement pour ce partenaire."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Services d'hébergement - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "form"], [False, "kanban"]],
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_view_hosting_services_expiring(self):
        """Ouvrir les services d'hébergement expirant pour ce partenaire."""
        self.ensure_one()
        today = fields.Date.today()
        warning_date = today + timedelta(days=90)
        return {
            "type": "ir.actions.act_window",
            "name": f"Services expirant - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "form"], [False, "kanban"]],
            "domain": [
                ("partner_id", "=", self.id),
                ("state", "=", "active"),
                ("date_expiration", ">", today),
                ("date_expiration", "<=", warning_date),
            ],
            "context": {"default_partner_id": self.id},
        }

    def action_view_hosting_services_updates(self):
        """Ouvrir les services d'hébergement avec mises à jour disponibles."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Mises à jour disponibles - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "form"], [False, "kanban"]],
            "domain": [
                ("partner_id", "=", self.id),
                ("state", "=", "active"),
                ("update_available", "=", True),
            ],
            "context": {"default_partner_id": self.id},
        }

    def action_view_hosting_services_storage_alert(self):
        """Ouvrir les services d'hébergement avec alertes de stockage."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Alertes de stockage - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "form"], [False, "kanban"]],
            "domain": [
                ("partner_id", "=", self.id),
                ("state", "=", "active"),
                ("storage_alert", "=", True),
            ],
            "context": {"default_partner_id": self.id},
        }
