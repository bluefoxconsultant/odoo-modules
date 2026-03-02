# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class HostingBackupRun(models.Model):
    """Représente une exécution de sauvegarde (exécution quotidienne de tous les scripts de sauvegarde)."""

    _name = "hosting.backup.run"
    _description = "Exécution de sauvegarde"
    _order = "run_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Référence",
        readonly=True,
        copy=False,
        default="New",
    )
    run_date = fields.Datetime(
        string="Date d'exécution",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    hostname = fields.Char(
        string="Nom d'hôte du serveur",
        tracking=True,
    )
    backup_root = fields.Char(
        string="Emplacement de sauvegarde",
    )
    state = fields.Selection(
        selection=[
            ("success", "Tous réussis"),
            ("partial", "Succès partiel"),
            ("failed", "Échoué"),
        ],
        string="État",
        compute="_compute_state",
        store=True,
        tracking=True,
    )
    total_count = fields.Integer(
        string="Total des services",
        compute="_compute_counts",
        store=True,
    )
    success_count = fields.Integer(
        string="Réussis",
        compute="_compute_counts",
        store=True,
    )
    failed_count = fields.Integer(
        string="Échoués",
        compute="_compute_counts",
        store=True,
    )
    skipped_count = fields.Integer(
        string="Ignorés",
        compute="_compute_counts",
        store=True,
    )
    line_ids = fields.One2many(
        comodel_name="hosting.backup.line",
        inverse_name="run_id",
        string="Détails de sauvegarde",
    )
    notes = fields.Text(
        string="Notes",
    )
    report_sent = fields.Boolean(
        string="Rapport envoyé",
        default=False,
    )
    report_sent_date = fields.Datetime(
        string="Date d'envoi du rapport",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Société",
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hosting.backup.run"
                ) or "New"
        return super().create(vals_list)

    @api.depends("line_ids", "line_ids.status")
    def _compute_counts(self):
        for run in self:
            run.total_count = len(run.line_ids)
            run.success_count = len(
                run.line_ids.filtered(lambda l: l.status == "success")
            )
            run.failed_count = len(run.line_ids.filtered(lambda l: l.status == "failed"))
            run.skipped_count = len(
                run.line_ids.filtered(lambda l: l.status == "skipped")
            )

    @api.depends("line_ids", "line_ids.status", "line_ids.all_verified")
    def _compute_state(self):
        for run in self:
            if not run.line_ids:
                run.state = False
            elif run.failed_count > 0:
                run.state = "failed" if run.success_count == 0 else "partial"
            else:
                # Pas d'échec — les services ignorés (sans conteneurs) sont attendus,
                # donc vérifier uniquement si toutes les sauvegardes réussies sont vérifiées
                has_unverified = any(
                    not line.all_verified
                    for line in run.line_ids
                    if line.status == "success" and line.file_ids
                )
                run.state = "partial" if has_unverified else "success"

    def action_send_report(self):
        """Envoyer le rapport de sauvegarde par courriel."""
        self.ensure_one()
        template = self.env.ref(
            "hosting_management.email_template_backup_report", raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
            self.write(
                {"report_sent": True, "report_sent_date": fields.Datetime.now()}
            )
        return True


class HostingBackupLine(models.Model):
    """Représente une sauvegarde individuelle de service dans une exécution de sauvegarde."""

    _name = "hosting.backup.line"
    _description = "Ligne de sauvegarde"
    _order = "run_id desc, service_name"

    run_id = fields.Many2one(
        comodel_name="hosting.backup.run",
        string="Exécution de sauvegarde",
        required=True,
        ondelete="cascade",
    )
    service_name = fields.Char(
        string="Service",
        required=True,
    )
    status = fields.Selection(
        selection=[
            ("success", "Réussi"),
            ("failed", "Échoué"),
            ("skipped", "Ignoré"),
        ],
        string="État",
        required=True,
    )
    duration = fields.Char(
        string="Durée",
    )
    error_message = fields.Text(
        string="Message d'erreur",
    )
    container_count = fields.Integer(
        string="Conteneurs attendus",
        help="Nombre de conteneurs Docker attendus pour la sauvegarde",
        default=0,
    )
    verified_file_count = fields.Integer(
        string="Archives vérifiées",
        help="Nombre d'archives de sauvegarde vérifiées créées",
        default=0,
    )
    file_ids = fields.One2many(
        comodel_name="hosting.backup.file",
        inverse_name="line_id",
        string="Fichiers de sauvegarde",
    )

    # Champs calculés
    file_count = fields.Integer(
        string="Fichiers",
        compute="_compute_file_count",
    )
    backup_ratio = fields.Char(
        string="État de sauvegarde",
        compute="_compute_backup_ratio",
        help="Ratio d'archives vérifiées par rapport aux conteneurs attendus",
    )
    total_size = fields.Char(
        string="Taille totale",
        compute="_compute_total_size",
    )
    all_verified = fields.Boolean(
        string="Tous vérifiés",
        compute="_compute_all_verified",
    )

    @api.depends("file_ids")
    def _compute_file_count(self):
        for line in self:
            line.file_count = len(line.file_ids)

    @api.depends("file_ids.size")
    def _compute_total_size(self):
        for line in self:
            # Just concatenate sizes for now since they're strings like "1.2G", "456M"
            sizes = line.file_ids.mapped("size")
            line.total_size = ", ".join(filter(None, sizes)) or "-"

    @api.depends("file_ids.verified")
    def _compute_all_verified(self):
        for line in self:
            if line.file_ids:
                line.all_verified = all(f.verified for f in line.file_ids)
            else:
                line.all_verified = False

    @api.depends("container_count", "verified_file_count")
    def _compute_backup_ratio(self):
        for line in self:
            if line.container_count > 0:
                line.backup_ratio = f"{line.verified_file_count}/{line.container_count}"
            elif line.verified_file_count > 0:
                line.backup_ratio = f"{line.verified_file_count}/?"
            else:
                line.backup_ratio = "-"


class HostingBackupFile(models.Model):
    """Représente un fichier de sauvegarde individuel."""

    _name = "hosting.backup.file"
    _description = "Fichier de sauvegarde"
    _order = "line_id, name"

    line_id = fields.Many2one(
        comodel_name="hosting.backup.line",
        string="Ligne de sauvegarde",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Nom de fichier",
        required=True,
    )
    size = fields.Char(
        string="Taille",
    )
    checksum = fields.Char(
        string="Somme de contrôle SHA256",
    )
    verified = fields.Boolean(
        string="Vérifié",
        default=False,
    )
