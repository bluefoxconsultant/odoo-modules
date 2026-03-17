# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Paramètres du journal d'audit
    hosting_audit_log_retention_months = fields.Integer(
        string="Rétention du journal d'audit (mois)",
        config_parameter="hosting.audit_log_retention_months",
        default=24,
        help="Nombre de mois de conservation des entrées du journal d'audit. Les entrées plus anciennes sont supprimées automatiquement.",
    )

    # Paramètres d'alerte de santé
    hosting_health_alert_email = fields.Char(
        string="Courriel d'alerte de santé",
        config_parameter="hosting.health_alert_email",
        help="Adresse courriel pour recevoir les alertes de vérification de santé",
    )
    hosting_response_time_threshold_ms = fields.Integer(
        string="Seuil de temps de réponse (ms)",
        config_parameter="hosting.response_time_threshold_ms",
        default=5000,
        help="Seuil de temps de réponse en millisecondes. Les services répondant plus lentement déclencheront un avertissement.",
    )
    hosting_expiration_warning_days = fields.Integer(
        string="Jours d'avertissement d'expiration",
        config_parameter="hosting.expiration_warning_days",
        default=90,
        help="Nombre de jours avant l'expiration pour créer des activités d'avertissement",
    )

    # Paramètres de domaines et SSL
    hosting_domain_expiration_warning_days = fields.Integer(
        string="Jours d'avertissement de domaine",
        config_parameter="hosting.domain_expiration_warning_days",
        default=60,
        help="Nombre de jours avant l'expiration du domaine pour créer des activités d'avertissement",
    )
    hosting_ssl_expiration_warning_days = fields.Integer(
        string="Jours d'avertissement SSL",
        config_parameter="hosting.ssl_expiration_warning_days",
        default=30,
        help="Nombre de jours avant l'expiration du certificat SSL pour créer des activités d'avertissement",
    )

    # Intégration Cloudflare Registrar
    hosting_cloudflare_email = fields.Char(
        string="Courriel Cloudflare",
        config_parameter="hosting.cloudflare_email",
    )
    hosting_cloudflare_api_key = fields.Char(
        string="Clé API globale Cloudflare",
        config_parameter="hosting.cloudflare_api_key",
    )
    hosting_cloudflare_account_id = fields.Char(
        string="ID de compte Cloudflare",
        config_parameter="hosting.cloudflare_account_id",
    )
    hosting_last_cloudflare_sync = fields.Datetime(
        string="Dernière synchronisation Cloudflare",
        config_parameter="hosting.last_cloudflare_sync",
        readonly=True,
    )

    # Notifications push ntfy
    hosting_ntfy_url = fields.Char(
        string="URL du serveur ntfy",
        config_parameter="hosting.ntfy_url",
        help="URL du serveur ntfy (ex. : https://ntfy.example.com)",
    )
    hosting_ntfy_token = fields.Char(
        string="Jeton ntfy",
        config_parameter="hosting.ntfy_token",
        help="Jeton d'authentification pour publier sur le serveur ntfy",
    )
    hosting_ntfy_topic = fields.Char(
        string="Sujet ntfy",
        config_parameter="hosting.ntfy_topic",
        default="hosting-alerts",
        help="Nom du sujet ntfy pour les alertes d'hébergement",
    )

    # Paramètres de fenêtre de maintenance
    hosting_maintenance_window_enabled = fields.Boolean(
        string="Activer la fenêtre de maintenance",
        config_parameter="hosting.maintenance_window_enabled",
        default=True,
        help="Lorsqu'activé, les alertes de santé sont supprimées pendant la fenêtre de maintenance",
    )
    hosting_maintenance_start_hour = fields.Float(
        string="Heure de début de maintenance",
        default=1.5,
        help="Heure de début de la fenêtre de maintenance (format 24h, ex. : 1.5 = 1h30)",
    )
    hosting_maintenance_end_hour = fields.Float(
        string="Heure de fin de maintenance",
        default=2.5,
        help="Heure de fin de la fenêtre de maintenance (format 24h, ex. : 2.5 = 2h30)",
    )
    hosting_maintenance_timezone = fields.Selection(
        selection="_get_timezone_selection",
        string="Fuseau horaire de maintenance",
        default="America/Toronto",
        help="Fuseau horaire pour la fenêtre de maintenance",
    )

    @api.model
    def _get_timezone_selection(self):
        """Retourner la liste des fuseaux horaires courants pour la sélection."""
        return [
            ("America/Toronto", "America/Toronto (Est)"),
            ("America/Montreal", "America/Montreal (Est)"),
            ("America/New_York", "America/New_York (Est)"),
            ("America/Chicago", "America/Chicago (Centre)"),
            ("America/Denver", "America/Denver (Rocheuses)"),
            ("America/Los_Angeles", "America/Los_Angeles (Pacifique)"),
            ("America/Vancouver", "America/Vancouver (Pacifique)"),
            ("UTC", "UTC"),
            ("Europe/London", "Europe/London"),
            ("Europe/Paris", "Europe/Paris"),
        ]

    def set_values(self):
        """Sauvegarder les paramètres de fenêtre de maintenance."""
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "hosting.maintenance_start_hour",
            str(self.hosting_maintenance_start_hour),
        )
        ICP.set_param(
            "hosting.maintenance_end_hour",
            str(self.hosting_maintenance_end_hour),
        )
        ICP.set_param(
            "hosting.maintenance_timezone",
            self.hosting_maintenance_timezone or "America/Toronto",
        )

    @api.model
    def get_values(self):
        """Charger les paramètres de fenêtre de maintenance."""
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            hosting_maintenance_start_hour=float(
                ICP.get_param("hosting.maintenance_start_hour", "1.5")
            ),
            hosting_maintenance_end_hour=float(
                ICP.get_param("hosting.maintenance_end_hour", "2.5")
            ),
            hosting_maintenance_timezone=ICP.get_param(
                "hosting.maintenance_timezone", "America/Toronto"
            ),
        )
        return res

    def action_sync_cloudflare_domains(self):
        """Lancer la synchronisation Cloudflare manuellement."""
        self.env["hosting.domain"]._cron_sync_cloudflare_domains()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Synchronisation Cloudflare"),
                "message": _("Synchronisation des domaines Cloudflare terminée."),
                "type": "success",
                "sticky": False,
            },
        }
