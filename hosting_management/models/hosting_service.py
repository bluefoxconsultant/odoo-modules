# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from markupsafe import escape as _esc

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import pytz
except ImportError:
    pytz = None


class HostingService(models.Model):
    _name = "hosting.service"
    _description = "Service d'hébergement"
    _order = "code"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Nom du service",
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string="Référence",
        readonly=True,
        copy=False,
        default="New",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Client",
        required=True,
        tracking=True,
        domain="[('is_company', '=', True)]",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    software_id = fields.Many2one(
        comodel_name="hosting.software",
        string="Logiciel",
        required=True,
        tracking=True,
    )
    installed_version_id = fields.Many2one(
        comodel_name="hosting.software.version",
        string="Version installée",
        domain="[('software_id', '=', software_id)]",
        tracking=True,
    )
    target_version_id = fields.Many2one(
        comodel_name="hosting.software.version",
        string="Version cible",
        domain="[('software_id', '=', software_id)]",
        help="Version vers laquelle mettre à jour",
    )
    version_policy = fields.Selection(
        selection=[
            ("latest", "Toujours la dernière"),
            ("lts", "LTS uniquement"),
            ("manual", "Mises à jour manuelles"),
            ("frozen", "Gelée (aucune mise à jour)"),
        ],
        string="Politique de version",
        default="manual",
        required=True,
        tracking=True,
    )
    version_notes = fields.Text(
        string="Notes de version",
        help="Raison de la version gelée ou instructions spéciales",
    )
    update_available = fields.Boolean(
        string="Mise à jour disponible",
        compute="_compute_update_available",
        store=True,
    )

    # Environnement
    environment = fields.Selection(
        selection=[
            ("production", "Production"),
            ("staging", "Préproduction"),
            ("development", "Développement"),
            ("testing", "Test"),
        ],
        string="Environnement",
        default="production",
        required=True,
        tracking=True,
    )
    linked_production_id = fields.Many2one(
        comodel_name="hosting.service",
        string="Production liée",
        domain="[('environment', '=', 'production'), ('software_id', '=', software_id), ('partner_id', '=', partner_id)]",
        help="Lier la préproduction/développement au service de production",
    )

    # Connexion
    server_url = fields.Char(
        string="URL du service",
        tracking=True,
    )
    domain_id = fields.Many2one(
        comodel_name="hosting.domain",
        string="Domaine",
        tracking=True,
    )
    domain_name = fields.Char(
        string="Nom de domaine",
    )

    # Serveur / Docker
    server_id = fields.Many2one(
        comodel_name="hosting.server",
        string="Serveur",
        tracking=True,
        help="Serveur sur lequel ce service est hébergé",
    )
    docker_host = fields.Char(
        string="Hôte Docker",
        compute="_compute_docker_host",
        store=True,
        help="Nom d'hôte du serveur (calculé depuis le serveur)",
    )
    docker_container = fields.Char(
        string="Nom du conteneur",
        help="Nom du conteneur Docker (ex. : vaultwarden-alvea)",
    )

    # Stockage
    storage_quota_gb = fields.Float(
        string="Quota de stockage (Go)",
        digits=(10, 2),
    )
    storage_used_gb = fields.Float(
        string="Stockage utilisé (Go)",
        digits=(10, 2),
    )
    storage_used_percent = fields.Float(
        string="Stockage utilisé (%)",
        compute="_compute_storage_percent",
        store=True,
    )
    storage_alert = fields.Boolean(
        string="Alerte de stockage",
        compute="_compute_storage_alert",
        store=True,
        help="Vrai si l'utilisation du stockage dépasse le seuil",
    )
    storage_alert_threshold = fields.Float(
        string="Seuil d'alerte (%)",
        default=80.0,
    )

    # Configuration de mesure de stockage
    storage_check_type = fields.Selection(
        selection=[
            ("none", "Aucun"),
            ("nextcloud_db", "Base Nextcloud (filecache)"),
            ("postgres", "Base PostgreSQL"),
            ("mariadb", "Base MariaDB"),
            ("container_directory", "Répertoire conteneur"),
            ("docker_volume", "Volume Docker"),
            ("host_directory", "Répertoire hôte"),
        ],
        string="Type de mesure",
        default="none",
    )
    storage_check_path = fields.Char(
        string="Chemin de mesure",
        help="Chemin du répertoire à mesurer (conteneur, volume ou hôte)",
    )
    storage_check_db_name = fields.Char(
        string="Nom de la base",
        help="Nom de la base de données pour la mesure PostgreSQL/MariaDB/Nextcloud",
    )
    storage_check_db_user = fields.Char(
        string="Utilisateur BD",
        help="Utilisateur de la base de données pour la mesure",
    )
    storage_last_check = fields.Datetime(
        string="Dernière mesure",
        readonly=True,
    )

    # Dates
    date_start = fields.Date(
        string="Date de début",
        default=fields.Date.today,
        tracking=True,
    )
    date_expiration = fields.Date(
        string="Date d'expiration",
        tracking=True,
    )
    days_until_expiration = fields.Integer(
        string="Jours avant expiration",
        compute="_compute_days_until_expiration",
    )
    expiration_activity_created = fields.Boolean(
        string="Activité d'expiration créée",
        default=False,
        copy=False,
        help="Indicateur pour prévenir la création d'activités d'expiration en double",
    )

    # État
    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("active", "Actif"),
            ("suspended", "Suspendu"),
            ("expired", "Expiré"),
            ("cancelled", "Annulé"),
        ],
        string="État",
        default="draft",
        required=True,
        tracking=True,
    )

    # Facturation
    contract_id = fields.Many2one(
        comodel_name="contract.contract",
        string="Contrat",
        tracking=True,
        help="Lien vers le contrat pour la facturation",
    )

    # Étiquettes
    tag_ids = fields.Many2many(
        comodel_name="hosting.service.tag",
        relation="hosting_service_tag_rel",
        column1="service_id",
        column2="tag_id",
        string="Étiquettes",
    )

    # Historique de mise à jour
    update_log_ids = fields.One2many(
        comodel_name="hosting.update.log",
        inverse_name="service_id",
        string="Historique de mise à jour",
    )

    # Vérification de santé
    health_check_ids = fields.One2many(
        comodel_name="hosting.health.check",
        inverse_name="service_id",
        string="Vérifications de santé",
    )

    # Planifications de maintenance
    maintenance_schedule_ids = fields.One2many(
        comodel_name="hosting.maintenance.schedule",
        inverse_name="service_id",
        string="Planifications de maintenance",
    )
    maintenance_schedule_count = fields.Integer(
        string="Tâches de maintenance",
        compute="_compute_maintenance_schedule_count",
    )
    maintenance_overdue_count = fields.Integer(
        string="Maintenance en retard",
        compute="_compute_maintenance_schedule_count",
    )
    last_health_status = fields.Selection(
        selection=[
            ("up", "En ligne"),
            ("degraded", "Dégradé"),
            ("down", "Hors ligne"),
            ("timeout", "Délai dépassé"),
        ],
        string="État de santé",
        compute="_compute_health_status",
        store=True,
    )
    last_health_check = fields.Datetime(
        string="Dernière vérification de santé",
        compute="_compute_health_status",
        store=True,
    )
    is_service_up = fields.Boolean(
        string="Service en ligne",
        compute="_compute_health_status",
        store=True,
    )
    uptime_30d = fields.Float(
        string="Disponibilité 30j (%)",
        compute="_compute_uptime_30d",
        digits=(5, 2),
    )
    health_check_count = fields.Integer(
        string="Nombre de vérifications de santé",
        compute="_compute_health_check_count",
    )

    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    _sql_constraints = [
        ("code_uniq", "UNIQUE(code)", "La référence du service doit être unique !"),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hosting.service"
                ) or "New"
        records = super().create(vals_list)
        AuditLog = self.env["hosting.audit.log"]
        for rec in records:
            AuditLog._log_event(
                action_type="create",
                category="ops",
                description=f"Service créé : {rec.name} ({rec.code})",
                res_model=self._name,
                res_id=rec.id,
                res_name=rec.display_name,
                service_id=rec.id,
                server_id=rec.server_id.id if rec.server_id else None,
            )
        return records

    def write(self, vals):
        # Capture state changes before write
        if "state" in vals:
            state_labels = dict(self._fields["state"].selection)
            for rec in self:
                old_state = rec.state
                new_state = vals["state"]
                if old_state != new_state:
                    severity = (
                        "warning"
                        if new_state in ("suspended", "expired", "cancelled")
                        else "info"
                    )
                    self.env["hosting.audit.log"]._log_event(
                        action_type="state_change",
                        category="ops",
                        description=(
                            f"État du service {rec.name} : "
                            f"{state_labels.get(old_state, old_state)} → "
                            f"{state_labels.get(new_state, new_state)}"
                        ),
                        res_model=self._name,
                        res_id=rec.id,
                        res_name=rec.display_name,
                        service_id=rec.id,
                        server_id=rec.server_id.id if rec.server_id else None,
                        field_name="state",
                        old_value=old_state,
                        new_value=new_state,
                        severity=severity,
                    )
        return super().write(vals)

    def unlink(self):
        AuditLog = self.env["hosting.audit.log"]
        for rec in self:
            AuditLog._log_event(
                action_type="unlink",
                category="ops",
                description=f"Service supprimé : {rec.name} ({rec.code})",
                res_model=self._name,
                res_id=rec.id,
                res_name=rec.display_name,
                service_id=rec.id,
                server_id=rec.server_id.id if rec.server_id else None,
                severity="warning",
            )
        return super().unlink()

    @api.depends("installed_version_id", "software_id.latest_version", "version_policy")
    def _compute_update_available(self):
        for record in self:
            if record.version_policy == "frozen":
                record.update_available = False
            elif not record.installed_version_id or not record.software_id.latest_version:
                record.update_available = False
            else:
                installed = record.installed_version_id.version
                latest = record.software_id.latest_version
                record.update_available = self._is_version_older(installed, latest)

    @staticmethod
    def _parse_version(version_str):
        """Analyser une chaîne de version en composants comparables.

        Gère les formats comme :
        - "25.04.8.1" -> (25, 4, 8, 1)
        - "7.4.2" -> (7, 4, 2)
        - "18.0-20260131" -> (18, 0, 20260131)
        - "v1.2.3" -> (1, 2, 3)

        Retourne un tuple d'entiers pour la comparaison, ou None si non analysable.
        """
        if not version_str:
            return None

        # Retirer les préfixes communs
        version_str = version_str.lstrip("v").lstrip("V")

        # Séparer par points ou tirets
        import re
        parts = re.split(r"[.\-]", version_str)

        try:
            return tuple(int(p) for p in parts if p.isdigit() or p.lstrip("-").isdigit())
        except (ValueError, TypeError):
            return None

    @classmethod
    def _is_version_older(cls, installed, latest):
        """Vérifier si la version installée est plus ancienne que la dernière version.

        Retourne True si installée < dernière (mise à jour disponible).
        Retourne False si installée >= dernière (aucune mise à jour nécessaire).
        """
        if installed == latest:
            return False

        installed_parsed = cls._parse_version(installed)
        latest_parsed = cls._parse_version(latest)

        if installed_parsed and latest_parsed:
            max_len = max(len(installed_parsed), len(latest_parsed))
            installed_padded = installed_parsed + (0,) * (max_len - len(installed_parsed))
            latest_padded = latest_parsed + (0,) * (max_len - len(latest_parsed))
            return installed_padded < latest_padded

        # If either version can't be parsed, we can't determine update status
        # Don't flag as needing update based on string inequality alone
        return False

    @api.depends("storage_quota_gb", "storage_used_gb")
    def _compute_storage_percent(self):
        for record in self:
            if record.storage_quota_gb > 0:
                record.storage_used_percent = (
                    record.storage_used_gb / record.storage_quota_gb
                ) * 100
            else:
                record.storage_used_percent = 0.0

    @api.depends("storage_used_percent", "storage_alert_threshold", "storage_quota_gb")
    def _compute_storage_alert(self):
        for record in self:
            threshold = record.storage_alert_threshold or 80.0
            if record.storage_quota_gb and record.storage_quota_gb > 0:
                record.storage_alert = record.storage_used_percent >= threshold
            else:
                record.storage_alert = False

    @api.depends("date_expiration")
    def _compute_days_until_expiration(self):
        today = fields.Date.today()
        for record in self:
            if record.date_expiration:
                delta = record.date_expiration - today
                record.days_until_expiration = delta.days
            else:
                record.days_until_expiration = 0

    @api.depends("server_id", "server_id.hostname")
    def _compute_docker_host(self):
        for record in self:
            record.docker_host = record.server_id.hostname if record.server_id else False

    @api.depends("health_check_ids", "health_check_ids.status", "health_check_ids.check_date")
    def _compute_health_status(self):
        for record in self:
            latest_check = record.health_check_ids[:1]
            if latest_check:
                record.last_health_status = latest_check.status
                record.last_health_check = latest_check.check_date
                record.is_service_up = latest_check.status == "up"
            else:
                record.last_health_status = False
                record.last_health_check = False
                record.is_service_up = True

    def _compute_uptime_30d(self):
        """Calculer le pourcentage de disponibilité des 30 derniers jours."""
        now = fields.Datetime.now()
        thirty_days_ago = now - timedelta(days=30)
        for record in self:
            checks = record.health_check_ids.filtered(
                lambda c: c.check_date >= thirty_days_ago
            )
            if checks:
                up_count = len(checks.filtered(lambda c: c.status == "up"))
                record.uptime_30d = (up_count / len(checks)) * 100
            else:
                record.uptime_30d = 100.0

    def _compute_health_check_count(self):
        for record in self:
            record.health_check_count = len(record.health_check_ids)

    def _compute_maintenance_schedule_count(self):
        for record in self:
            active_schedules = record.maintenance_schedule_ids.filtered(
                lambda s: s.active
            )
            record.maintenance_schedule_count = len(active_schedules)
            record.maintenance_overdue_count = len(
                active_schedules.filtered(lambda s: s.is_overdue)
            )

    def action_view_maintenance_schedules(self):
        """Voir les planifications de maintenance pour ce service."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Maintenance - {self.name}",
            "res_model": "hosting.maintenance.schedule",
            "views": [[False, "list"], [False, "kanban"], [False, "form"]],
            "domain": [("service_id", "=", self.id)],
            "context": {"default_service_id": self.id},
        }

    def action_activate(self):
        """Activer le service et créer les planifications de maintenance depuis les modèles."""
        self.write({"state": "active"})
        for service in self:
            service._create_maintenance_from_templates()

    def action_suspend(self):
        """Suspendre le service."""
        self.write({"state": "suspended"})

    def action_cancel(self):
        """Annuler le service."""
        self.write({"state": "cancelled"})

    def action_set_draft(self):
        """Remettre le service en brouillon."""
        self.write({"state": "draft"})

    def action_view_contract(self):
        """Ouvrir le contrat lié."""
        self.ensure_one()
        if self.contract_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Contrat",
                "res_model": "contract.contract",
                "views": [[False, "form"]],
                "res_id": self.contract_id.id,
            }

    def action_view_update_history(self):
        """Voir l'historique de mise à jour pour ce service."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Historique de mise à jour - {self.name}",
            "res_model": "hosting.update.log",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("service_id", "=", self.id)],
            "context": {"default_service_id": self.id},
        }

    def action_mark_updated(self):
        """Marquer le service comme mis à jour vers la version cible."""
        self.ensure_one()
        if self.target_version_id:
            self.env["hosting.update.log"].create({
                "service_id": self.id,
                "from_version_id": self.installed_version_id.id,
                "to_version_id": self.target_version_id.id,
                "notes": "Mise à jour manuelle marquée comme complétée.",
            })
            self.installed_version_id = self.target_version_id
            self.target_version_id = False

    def action_update_to_latest(self):
        """Marquer le service comme mis à jour vers la dernière version disponible."""
        self.ensure_one()
        if not self.update_available or not self.software_id.latest_version:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Aucune mise à jour disponible",
                    "message": "Ce service est déjà à la dernière version.",
                    "type": "info",
                },
            }

        Version = self.env["hosting.software.version"]
        latest_version_record = Version.search([
            ("software_id", "=", self.software_id.id),
            ("version", "=", self.software_id.latest_version),
        ], limit=1)

        if not latest_version_record:
            latest_version_record = Version.create({
                "software_id": self.software_id.id,
                "version": self.software_id.latest_version,
                "release_date": self.software_id.latest_version_date,
            })

        self.env["hosting.update.log"].create({
            "service_id": self.id,
            "from_version_id": self.installed_version_id.id,
            "to_version_id": latest_version_record.id,
            "notes": "Mise à jour manuelle vers la dernière version.",
        })

        old_version = self.installed_version_id.version or "inconnue"
        self.installed_version_id = latest_version_record

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Version mise à jour",
                "message": f"Mise à jour de {old_version} vers {latest_version_record.version}",
                "type": "success",
            },
        }

    def _create_maintenance_from_templates(self):
        """Créer les planifications de maintenance depuis les modèles spécifiques au logiciel et par défaut."""
        self.ensure_one()
        MaintenanceSchedule = self.env["hosting.maintenance.schedule"]
        MaintenanceTemplate = self.env["hosting.maintenance.template"]
        today = fields.Date.today()

        # Obtenir les modèles spécifiques au logiciel
        templates = MaintenanceTemplate.search([
            ("software_id", "=", self.software_id.id),
            ("active", "=", True),
        ])

        # Obtenir aussi les modèles par défaut (aucun logiciel spécifié)
        default_templates = MaintenanceTemplate.search([
            ("software_id", "=", False),
            ("active", "=", True),
        ])

        all_templates = templates | default_templates

        created_schedules = []
        created_activities = []

        for template in all_templates:
            for line in template.line_ids.filtered(lambda l: l.active):
                # Vérifier si la planification existe déjà depuis cette ligne de modèle
                existing = MaintenanceSchedule.search([
                    ("service_id", "=", self.id),
                    ("template_line_id", "=", line.id),
                ], limit=1)
                if existing:
                    continue

                if line.frequency == "once":
                    due_date = today + timedelta(days=line.days_after_activation)

                    if line.create_activity:
                        activity_type = self.env.ref(
                            "mail.mail_activity_data_todo",
                            raise_if_not_found=False,
                        )
                        self.env["mail.activity"].create({
                            "res_model_id": self.env["ir.model"]._get_id("hosting.service"),
                            "res_id": self.id,
                            "activity_type_id": activity_type.id if activity_type else False,
                            "summary": line.name,
                            "note": line.instructions or f"Tâche de configuration pour {self.name}",
                            "date_deadline": due_date,
                            "user_id": self.user_id.id or self.env.user.id,
                        })
                        created_activities.append(line.name)

                    continue

                # Créer la planification de maintenance récurrente
                schedule_vals = {
                    "name": line.name,
                    "service_id": self.id,
                    "maintenance_type": line.maintenance_type,
                    "frequency": line.frequency,
                    "instructions": line.instructions,
                    "user_id": self.user_id.id or self.env.user.id,
                    "template_line_id": line.id,
                    "last_performed": today,
                }
                schedule = MaintenanceSchedule.create(schedule_vals)
                created_schedules.append(schedule.name)

        # Journaliser la création
        if created_schedules or created_activities:
            message_parts = []
            if created_schedules:
                message_parts.append(
                    f"<strong>Planifications de maintenance créées :</strong><ul>"
                    + "".join(f"<li>{_esc(name)}</li>" for name in created_schedules)
                    + "</ul>"
                )
            if created_activities:
                message_parts.append(
                    f"<strong>Activités de configuration créées :</strong><ul>"
                    + "".join(f"<li>{_esc(name)}</li>" for name in created_activities)
                    + "</ul>"
                )
            self.message_post(
                body="".join(message_parts),
                message_type="notification",
            )

    def action_apply_maintenance_templates(self):
        """Appliquer manuellement les modèles de maintenance à ce service."""
        self.ensure_one()
        self._create_maintenance_from_templates()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Modèles appliqués",
                "message": "Les planifications de maintenance ont été créées depuis les modèles.",
                "type": "success",
            },
        }

    @api.model
    def _cron_check_expirations(self):
        """Tâche planifiée pour créer des activités pour les services expirant bientôt."""
        warning_days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hosting.expiration_warning_days", "90")
        )
        today = fields.Date.today()
        warning_date = today + timedelta(days=warning_days)

        services = self.search([
            ("state", "=", "active"),
            ("date_expiration", "<=", warning_date),
            ("date_expiration", ">=", today),
            ("expiration_activity_created", "=", False),
        ])

        activity_type = self.env.ref(
            "hosting_management.mail_activity_type_hosting_expiration",
            raise_if_not_found=False,
        )

        for service in services:
            self.env["mail.activity"].create({
                "res_model_id": self.env["ir.model"]._get_id("hosting.service"),
                "res_id": service.id,
                "activity_type_id": activity_type.id if activity_type else False,
                "summary": f"Le service expire dans {service.days_until_expiration} jours",
                "note": f"Le service d'hébergement « {service.name} » pour {service.partner_id.name} "
                        f"expirera le {service.date_expiration}. Veuillez contacter le client "
                        f"pour discuter du renouvellement.",
                "date_deadline": service.date_expiration,
                "user_id": service.user_id.id or self.env.user.id,
            })
            service.expiration_activity_created = True

    @api.model
    def _cron_auto_expire(self):
        """Tâche planifiée pour expirer automatiquement les services en retard."""
        today = fields.Date.today()
        services = self.search([
            ("state", "=", "active"),
            ("date_expiration", "<", today),
        ])
        services.write({"state": "expired"})

    @api.model
    def _is_in_maintenance_window(self):
        """Vérifier si l'heure actuelle est dans la fenêtre de maintenance configurée.

        Returns:
            bool: True si actuellement dans la fenêtre de maintenance, False sinon
        """
        ICP = self.env["ir.config_parameter"].sudo()

        maintenance_enabled = ICP.get_param(
            "hosting.maintenance_window_enabled", "True"
        )
        if maintenance_enabled.lower() not in ("true", "1"):
            return False

        try:
            start_hour = float(ICP.get_param("hosting.maintenance_start_hour", "1.5"))
            end_hour = float(ICP.get_param("hosting.maintenance_end_hour", "2.5"))
        except (ValueError, TypeError):
            _logger.warning("Configuration de fenêtre de maintenance invalide, utilisation des valeurs par défaut")
            start_hour = 1.5
            end_hour = 2.5

        timezone_str = ICP.get_param("hosting.maintenance_timezone", "America/Toronto")

        from datetime import datetime

        if pytz:
            try:
                tz = pytz.timezone(timezone_str)
                now = datetime.now(tz)
            except Exception:
                _logger.warning(
                    "Fuseau horaire invalide %s, retour à UTC", timezone_str
                )
                now = datetime.utcnow()
        else:
            _logger.warning("pytz non disponible, utilisation de UTC pour la fenêtre de maintenance")
            now = datetime.utcnow()

        current_hour = now.hour + (now.minute / 60.0)

        if start_hour <= end_hour:
            in_window = start_hour <= current_hour < end_hour
        else:
            in_window = current_hour >= start_hour or current_hour < end_hour

        if in_window:
            _logger.info(
                "Actuellement dans la fenêtre de maintenance (%s à %s %s), alertes supprimées",
                self._format_hour(start_hour),
                self._format_hour(end_hour),
                timezone_str,
            )

        return in_window

    @staticmethod
    def _format_hour(decimal_hour):
        """Convertir une heure décimale au format HH:MM."""
        hours = int(decimal_hour)
        minutes = int((decimal_hour - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    @api.model
    def _cron_health_check(self):
        """Vérifier la santé de tous les services actifs avec URL."""
        try:
            import requests
        except ImportError:
            _logger.warning("Bibliothèque requests non installée, vérifications de santé ignorées")
            return

        services = self.search([
            ("state", "=", "active"),
            ("server_url", "!=", False),
        ])

        response_time_threshold = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hosting.response_time_threshold_ms", "5000")
        )

        services_now_down = []
        services_recovered = []
        services_slow = []

        for service in services:
            previous_status = service.last_health_status
            new_status = None
            error_message = None
            response_time_ms = None

            try:
                response = requests.get(
                    service.server_url,
                    timeout=10,
                    allow_redirects=True,
                    headers={"User-Agent": "Odoo-Hosting-Health-Check/1.0"},
                )
                new_status = "up" if response.status_code < 400 else "degraded"
                response_time_ms = int(response.elapsed.total_seconds() * 1000)
                self.env["hosting.health.check"].create({
                    "service_id": service.id,
                    "status": new_status,
                    "response_time_ms": response_time_ms,
                    "http_status_code": response.status_code,
                })
            except requests.Timeout:
                new_status = "timeout"
                error_message = "La requête a expiré après 10 secondes"
                self.env["hosting.health.check"].create({
                    "service_id": service.id,
                    "status": "timeout",
                    "error_message": error_message,
                })
            except requests.RequestException as e:
                new_status = "down"
                error_message = str(e)[:500]
                self.env["hosting.health.check"].create({
                    "service_id": service.id,
                    "status": "down",
                    "error_message": error_message,
                })
            except Exception as e:
                _logger.exception("Erreur lors de la vérification de santé pour le service %s", service.name)
                new_status = "down"
                error_message = f"Erreur inattendue : {str(e)[:450]}"
                self.env["hosting.health.check"].create({
                    "service_id": service.id,
                    "status": "down",
                    "error_message": error_message,
                })

            if previous_status == "up" and new_status in ("down", "timeout", "degraded"):
                services_now_down.append({
                    "service": service,
                    "status": new_status,
                    "error": error_message,
                })

            if previous_status in ("down", "timeout", "degraded") and new_status == "up":
                services_recovered.append({
                    "service": service,
                    "response_time_ms": response_time_ms,
                })

            if (new_status == "up" and response_time_ms
                    and response_time_ms > response_time_threshold):
                services_slow.append({
                    "service": service,
                    "response_time_ms": response_time_ms,
                    "threshold_ms": response_time_threshold,
                })

        if self._is_in_maintenance_window():
            if services_now_down:
                _logger.info(
                    "Fenêtre de maintenance : alerte HORS LIGNE supprimée pour %d service(s)",
                    len(services_now_down),
                )
            if services_recovered:
                _logger.info(
                    "Fenêtre de maintenance : alerte RÉTABLI supprimée pour %d service(s)",
                    len(services_recovered),
                )
            if services_slow:
                _logger.info(
                    "Fenêtre de maintenance : alerte LENT supprimée pour %d service(s)",
                    len(services_slow),
                )
        else:
            if services_now_down:
                self._send_health_alert_email(services_now_down, alert_type="down")
                self._send_ntfy_alert(services_now_down, alert_type="down")

            if services_recovered:
                self._send_health_alert_email(services_recovered, alert_type="recovered")
                self._send_ntfy_alert(services_recovered, alert_type="recovered")

            if services_slow:
                self._send_health_alert_email(services_slow, alert_type="slow")

    def _send_ntfy_alert(self, services_list, alert_type="down"):
        """Envoyer une notification push via ntfy pour les événements de santé.

        Args:
            services_list: Liste de dicts avec les informations de service
            alert_type: "down" ou "recovered"
        """
        try:
            import requests as req
        except ImportError:
            return

        ICP = self.env["ir.config_parameter"].sudo()
        ntfy_url = ICP.get_param("hosting.ntfy_url", "").strip().rstrip("/")
        ntfy_token = ICP.get_param("hosting.ntfy_token", "").strip()
        ntfy_topic = ICP.get_param("hosting.ntfy_topic", "").strip()

        if not all([ntfy_url, ntfy_token, ntfy_topic]):
            _logger.debug("ntfy non configuré, notification push ignorée")
            return

        count = len(services_list)
        if alert_type == "down":
            title = f"ALERTE : {count} service(s) hors ligne"
            priority = "urgent"
            tags = "rotating_light"
            lines = []
            for item in services_list:
                svc = item["service"]
                status = item.get("status", "down").upper()
                error = item.get("error") or ""
                line = f"- {svc.name} ({svc.partner_id.name or 'N/D'}) [{status}]"
                if error:
                    line += f" : {error[:80]}"
                lines.append(line)
        elif alert_type == "recovered":
            title = f"RÉTABLI : {count} service(s) de nouveau en ligne"
            priority = "default"
            tags = "white_check_mark"
            lines = []
            for item in services_list:
                svc = item["service"]
                rt = item.get("response_time_ms", 0)
                lines.append(f"- {svc.name} ({svc.partner_id.name or 'N/D'}) [{rt}ms]")
        else:
            return

        body = "\n".join(lines)

        try:
            req.post(
                f"{ntfy_url}/{ntfy_topic}",
                data=body.encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {ntfy_token}",
                    "Title": title,
                    "Priority": priority,
                    "Tags": tags,
                },
                timeout=10,
            )
        except Exception:
            _logger.exception("Erreur lors de l'envoi de la notification ntfy")

    def _send_health_alert_email(self, services_list, alert_type="down"):
        """Envoyer un courriel d'alerte pour les événements de santé.

        Args:
            services_list: Liste de dicts avec les informations de service
            alert_type: "down", "recovered" ou "slow"
        """
        from . import hosting_email_template as email_tpl

        alert_email = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hosting.health_alert_email", "")
        )

        if not alert_email:
            _logger.warning(
                "Aucun courriel d'alerte de santé configuré. Définir 'hosting.health_alert_email' "
                "dans les paramètres système pour recevoir les alertes."
            )
            return

        if alert_type == "down":
            subject = f"ALERTE : {len(services_list)} service(s) d'hébergement hors ligne"
            title = "Alerte de service"
            description = f"Les <strong>{len(services_list)}</strong> service(s) suivant(s) sont actuellement <strong>HORS LIGNE</strong> ou rencontrent des problèmes :"
            headers = ["Service", "Client", "URL", "État", "Erreur"]
        elif alert_type == "recovered":
            subject = f"RÉTABLI : {len(services_list)} service(s) d'hébergement de nouveau en ligne"
            title = "Rétablissement de service"
            description = f"Les <strong>{len(services_list)}</strong> service(s) suivant(s) ont été <strong>RÉTABLIS</strong> et sont maintenant opérationnels :"
            headers = ["Service", "Client", "URL", "Temps de réponse"]
        elif alert_type == "slow":
            subject = f"AVERTISSEMENT : {len(services_list)} service(s) d'hébergement lent(s)"
            title = "Avertissement de performance"
            description = f"Les <strong>{len(services_list)}</strong> service(s) suivant(s) connaissent des <strong>TEMPS DE RÉPONSE LENTS</strong> :"
            headers = ["Service", "Client", "URL", "Temps de réponse", "Seuil"]
        else:
            return

        table_rows = []
        for item in services_list:
            service = item["service"]
            safe_url = _esc(service.server_url or "")
            url_link = f'<a href="{safe_url}" style="color:#29abe2; text-decoration:none;">{safe_url}</a>'
            svc_cell = f"{_esc(service.name)}<br/><span style='color:#6B7280; font-size:12px;'>{_esc(service.code)}</span>"
            partner_cell = _esc(service.partner_id.name or "")

            if alert_type == "down":
                status = item.get("status", "DOWN").upper()
                status_badge = email_tpl.get_status_badge(status, "small")
                error = item.get("error") or "N/D"
                safe_error = _esc(error[:50]) + ("..." if len(error) > 50 else "")
                row = [
                    svc_cell,
                    partner_cell,
                    url_link,
                    status_badge,
                    f"<span style='font-size:13px; color:#6B7280;'>{safe_error}</span>",
                ]
            elif alert_type == "recovered":
                response_time = item.get("response_time_ms", 0)
                row = [
                    svc_cell,
                    partner_cell,
                    url_link,
                    f"<span style='color:#198754; font-weight:600;'>{response_time} ms</span>",
                ]
            elif alert_type == "slow":
                response_time = item.get("response_time_ms", 0)
                threshold = item.get("threshold_ms", 5000)
                row = [
                    svc_cell,
                    partner_cell,
                    url_link,
                    f"<span style='color:#ffc107; font-weight:600;'>{response_time} ms</span>",
                    f"{threshold} ms",
                ]

            table_rows.append(row)

        content_parts = [
            f'<p style="font-family:\'Lexend\',\'Segoe UI\',Arial,sans-serif; font-size:16px; line-height:26px; color:#374151; margin:0 0 20px 0;">{description}</p>',
            email_tpl.get_data_table(headers, table_rows),
            email_tpl.get_contact_footer(),
        ]

        content = "".join(content_parts)
        body_html = email_tpl.get_email_wrapper(title, content, alert_type)

        try:
            mail_values = {
                "subject": subject,
                "email_from": self.env.company.email or self.env.user.email_formatted,
                "email_to": alert_email,
                "body_html": body_html,
                "auto_delete": True,
            }
            mail = self.env["mail.mail"].sudo().create(mail_values)
            mail.send()
            _logger.info("Courriel d'alerte de santé (%s) envoyé à %s pour %d service(s)",
                        alert_type, alert_email, len(services_list))
        except Exception as e:
            _logger.exception("Échec de l'envoi du courriel d'alerte de santé : %s", str(e))

    def action_view_health_history(self):
        """Voir l'historique des vérifications de santé pour ce service."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Historique de santé - {self.name}",
            "res_model": "hosting.health.check",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("service_id", "=", self.id)],
            "context": {"default_service_id": self.id},
        }

    def action_run_health_check(self):
        """Exécuter manuellement la vérification de santé pour ce service."""
        self.ensure_one()
        if not self.server_url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Aucune URL",
                    "message": "Ce service n'a pas d'URL configurée pour les vérifications de santé.",
                    "type": "warning",
                },
            }

        try:
            import requests
        except ImportError:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Bibliothèque manquante",
                    "message": "La bibliothèque requests n'est pas installée.",
                    "type": "danger",
                },
            }

        try:
            response = requests.get(
                self.server_url,
                timeout=10,
                allow_redirects=True,
                headers={"User-Agent": "Odoo-Hosting-Health-Check/1.0"},
            )
            status = "up" if response.status_code < 400 else "degraded"
            self.env["hosting.health.check"].create({
                "service_id": self.id,
                "status": status,
                "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                "http_status_code": response.status_code,
            })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Vérification de santé terminée",
                    "message": f"État : {status.upper()}, Réponse : {response.status_code}",
                    "type": "success" if status == "up" else "warning",
                },
            }
        except requests.Timeout:
            self.env["hosting.health.check"].create({
                "service_id": self.id,
                "status": "timeout",
                "error_message": "La requête a expiré après 10 secondes",
            })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Vérification de santé terminée",
                    "message": "Délai du service dépassé",
                    "type": "danger",
                },
            }
        except Exception as e:
            self.env["hosting.health.check"].create({
                "service_id": self.id,
                "status": "down",
                "error_message": str(e)[:500],
            })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Vérification de santé terminée",
                    "message": f"Service hors ligne : {str(e)[:100]}",
                    "type": "danger",
                },
            }

    @api.model
    def _cron_check_docker_versions(self):
        """Tâche planifiée pour les vérifications de version Docker."""
        results = self._check_docker_versions()
        _logger.info(
            "Vérification de version Docker terminée : %d vérifiés, %d mis à jour, %d erreurs",
            results["checked"],
            results["updated"],
            len(results["errors"]),
        )
        if results["errors"]:
            for error in results["errors"][:10]:
                _logger.warning("Erreur de vérification de version Docker : %s", error)
        return results

    def action_check_docker_version(self):
        """Déclencher manuellement la vérification de version Docker pour ce service."""
        self.ensure_one()
        if not self.docker_host or not self.docker_container:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Configuration manquante",
                    "message": "L'hôte Docker et le conteneur doivent être configurés pour vérifier la version.",
                    "type": "warning",
                },
            }

        results = self._check_docker_versions()
        if results["errors"]:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Échec de la vérification de version",
                    "message": results["errors"][0] if results["errors"] else "Erreur inconnue",
                    "type": "danger",
                },
            }
        elif results["updated"]:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Version mise à jour",
                    "message": f"Version installée mise à jour vers {self.installed_version_id.version}",
                    "type": "success",
                },
            }
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Vérification de version terminée",
                    "message": f"Version actuelle : {self.installed_version_id.version or 'Inconnue'}",
                    "type": "info",
                },
            }

    @api.model
    def _check_docker_versions(self):
        """Vérifier les versions des conteneurs Docker.

        Utilise le socket Docker local si disponible, sinon SSH vers les hôtes distants.
        Retourne un dict avec les résultats.
        """
        import os
        import shlex
        import subprocess

        results = {
            "checked": 0,
            "updated": 0,
            "errors": [],
        }

        has_local_docker = os.path.exists("/var/run/docker.sock")

        services = self.search([
            ("docker_host", "!=", False),
            ("docker_container", "!=", False),
            ("state", "=", "active"),
        ])

        if not services:
            return results

        # Regrouper les services par hôte
        hosts = {}
        for service in services:
            host = service.docker_host
            if host not in hosts:
                hosts[host] = []
            hosts[host].append(service)

        for host, host_services in hosts.items():
            container_names = [s.docker_container for s in host_services]

            try:
                if has_local_docker:
                    cmd = [
                        "docker", "inspect",
                        "--format", "{{.Name}}|{{.Config.Image}}",
                    ] + container_names
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                else:
                    # Shell-quote each container name to prevent command injection
                    containers_arg = " ".join(
                        shlex.quote(name) for name in container_names
                    )
                    cmd = [
                        "ssh", "-o", "StrictHostKeyChecking=accept-new",
                        "-o", "ConnectTimeout=10",
                        f"root@{host}",
                        f"docker inspect --format '{{{{.Name}}}}|{{{{.Config.Image}}}}' {containers_arg} 2>/dev/null || true"
                    ]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                if result.returncode != 0 and result.stderr:
                    method = "Docker" if has_local_docker else "SSH"
                    results["errors"].append(f"{host} : erreur {method} - {result.stderr[:100]}")
                    continue

                version_map = {}
                for line in result.stdout.strip().split("\n"):
                    if "|" in line:
                        container_name, image = line.split("|", 1)
                        container_name = container_name.lstrip("/")
                        if ":" in image:
                            version = image.split(":")[-1]
                        else:
                            version = "latest"
                        version_map[container_name] = version

                for service in host_services:
                    results["checked"] += 1
                    container_name = service.docker_container

                    if container_name not in version_map:
                        results["errors"].append(
                            f"{service.name} : conteneur « {container_name} » introuvable sur {host}"
                        )
                        continue

                    docker_version = version_map[container_name]

                    skip_tags = {"latest", "stable", "edge", "dev", "beta", "alpha", "nightly"}
                    if docker_version.lower() in skip_tags:
                        continue

                    clean_version = docker_version
                    if clean_version.startswith("version-"):
                        clean_version = clean_version[8:]
                    elif clean_version.startswith("v") and len(clean_version) > 1 and clean_version[1].isdigit():
                        clean_version = clean_version[1:]

                    Version = self.env["hosting.software.version"]
                    version_record = Version.search([
                        ("software_id", "=", service.software_id.id),
                        ("version", "=", clean_version),
                    ], limit=1)

                    if not version_record:
                        version_record = Version.create({
                            "software_id": service.software_id.id,
                            "version": clean_version,
                        })

                    if service.installed_version_id != version_record:
                        old_version_id = service.installed_version_id.id
                        service.write({"installed_version_id": version_record.id})

                        self.env["hosting.update.log"].create({
                            "service_id": service.id,
                            "from_version_id": old_version_id,
                            "to_version_id": version_record.id,
                            "notes": f"Détection automatique via inspection Docker sur {host}",
                            "success": True,
                        })

                        results["updated"] += 1
                        _logger.info(
                            "Mise à jour de %s vers la version %s (depuis Docker)",
                            service.name, clean_version
                        )

            except subprocess.TimeoutExpired:
                results["errors"].append(f"{host} : délai de connexion SSH dépassé")
            except Exception as e:
                results["errors"].append(f"{host} : {str(e)[:100]}")
                _logger.exception("Erreur lors de la vérification des versions Docker sur %s", host)

        return results
