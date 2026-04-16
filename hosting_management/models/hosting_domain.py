# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
from datetime import date as date_type, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HostingDomain(models.Model):
    _name = "hosting.domain"
    _description = "Domaine"
    _order = "date_expiration asc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Identity
    name = fields.Char(
        string="Nom de domaine",
        required=True,
        tracking=True,
        help="FQDN du domaine (ex. : exemple.com)",
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

    # Registrar / DNS
    registrar = fields.Char(
        string="Registraire",
        tracking=True,
    )
    dns_provider = fields.Char(
        string="Fournisseur DNS",
        tracking=True,
    )

    # Domain dates
    date_registration = fields.Date(
        string="Date d'enregistrement",
    )
    date_expiration = fields.Date(
        string="Date d'expiration",
        tracking=True,
    )
    days_until_expiration = fields.Integer(
        string="Jours avant expiration",
        compute="_compute_days_until_expiration",
    )
    auto_renew = fields.Boolean(
        string="Renouvellement automatique",
        default=False,
        tracking=True,
    )
    domain_activity_created = fields.Boolean(
        string="Activite d'expiration creee",
        default=False,
        copy=False,
    )

    # SSL
    ssl_type = fields.Selection(
        selection=[
            ("none", "Aucun"),
            ("letsencrypt", "Let's Encrypt"),
            ("commercial", "Commercial"),
            ("self_signed", "Auto-signe"),
        ],
        string="Type SSL",
        default="none",
        tracking=True,
    )
    ssl_issuer = fields.Char(
        string="Emetteur SSL",
    )
    ssl_expiry_date = fields.Date(
        string="Expiration SSL",
        tracking=True,
    )
    days_until_ssl_expiry = fields.Integer(
        string="Jours avant expiration SSL",
        compute="_compute_days_until_ssl_expiry",
    )
    ssl_activity_created = fields.Boolean(
        string="Activite SSL creee",
        default=False,
        copy=False,
    )

    # Cost
    annual_cost = fields.Float(
        string="Cout annuel",
        digits=(10, 2),
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        default=lambda self: self.env.company.currency_id,
    )

    # State
    state = fields.Selection(
        selection=[
            ("active", "Actif"),
            ("expiring_soon", "Expire bientot"),
            ("expired", "Expire"),
            ("transferred", "Transfere"),
        ],
        string="Etat",
        default="active",
        required=True,
        tracking=True,
    )

    # Relations
    service_ids = fields.One2many(
        comodel_name="hosting.service",
        inverse_name="domain_id",
        string="Services",
    )
    service_count = fields.Integer(
        string="Nombre de services",
        compute="_compute_service_count",
    )

    # Meta
    notes = fields.Html(
        string="Notes",
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    _sql_constraints = [
        ("name_uniq", "UNIQUE(name)", "Ce nom de domaine existe deja !"),
    ]

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    @api.depends("date_expiration")
    def _compute_days_until_expiration(self):
        today = fields.Date.today()
        for record in self:
            if record.date_expiration:
                record.days_until_expiration = (record.date_expiration - today).days
            else:
                record.days_until_expiration = 0

    @api.depends("ssl_expiry_date")
    def _compute_days_until_ssl_expiry(self):
        today = fields.Date.today()
        for record in self:
            if record.ssl_expiry_date:
                record.days_until_ssl_expiry = (record.ssl_expiry_date - today).days
            else:
                record.days_until_ssl_expiry = 0

    def _compute_service_count(self):
        for record in self:
            record.service_count = len(record.service_ids)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_view_services(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Services - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("domain_id", "=", self.id)],
            "context": {"default_domain_id": self.id},
        }

    def action_set_active(self):
        self.write({"state": "active"})

    def action_set_transferred(self):
        self.write({"state": "transferred"})

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------

    @api.model
    def _cron_check_domain_expirations(self):
        """Check domain + SSL expirations, create activities, auto-expire."""
        ICP = self.env["ir.config_parameter"].sudo()
        domain_warn_days = int(
            ICP.get_param("hosting.domain_expiration_warning_days", "60")
        )
        ssl_warn_days = int(
            ICP.get_param("hosting.ssl_expiration_warning_days", "30")
        )
        today = fields.Date.today()

        # --- Domain expiration activities ---
        domain_warning_date = today + timedelta(days=domain_warn_days)
        expiring_domains = self.search([
            ("state", "in", ("active", "expiring_soon")),
            ("date_expiration", "<=", domain_warning_date),
            ("date_expiration", ">=", today),
            ("domain_activity_created", "=", False),
        ])

        activity_type_domain = self.env.ref(
            "hosting_management.mail_activity_type_domain_expiration",
            raise_if_not_found=False,
        )

        for domain in expiring_domains:
            self.env["mail.activity"].create({
                "res_model_id": self.env["ir.model"]._get_id("hosting.domain"),
                "res_id": domain.id,
                "activity_type_id": activity_type_domain.id if activity_type_domain else False,
                "summary": f"Le domaine expire dans {domain.days_until_expiration} jours",
                "note": (
                    f"Le domaine {domain.name} pour {domain.partner_id.name} "
                    f"expirera le {domain.date_expiration}. "
                    f"Veuillez proceder au renouvellement."
                ),
                "date_deadline": domain.date_expiration,
                "user_id": domain.user_id.id or self.env.user.id,
            })
            domain.domain_activity_created = True
            if domain.state == "active":
                domain.state = "expiring_soon"

        # --- SSL expiration activities ---
        ssl_warning_date = today + timedelta(days=ssl_warn_days)
        ssl_expiring = self.search([
            ("state", "in", ("active", "expiring_soon")),
            ("ssl_type", "!=", "none"),
            ("ssl_expiry_date", "<=", ssl_warning_date),
            ("ssl_expiry_date", ">=", today),
            ("ssl_activity_created", "=", False),
        ])

        activity_type_ssl = self.env.ref(
            "hosting_management.mail_activity_type_ssl_expiration",
            raise_if_not_found=False,
        )

        for domain in ssl_expiring:
            self.env["mail.activity"].create({
                "res_model_id": self.env["ir.model"]._get_id("hosting.domain"),
                "res_id": domain.id,
                "activity_type_id": activity_type_ssl.id if activity_type_ssl else False,
                "summary": f"Certificat SSL expire dans {domain.days_until_ssl_expiry} jours",
                "note": (
                    f"Le certificat SSL pour {domain.name} "
                    f"({domain.ssl_type}) expirera le {domain.ssl_expiry_date}. "
                    f"Veuillez proceder au renouvellement."
                ),
                "date_deadline": domain.ssl_expiry_date,
                "user_id": domain.user_id.id or self.env.user.id,
            })
            domain.ssl_activity_created = True

        # --- Auto-expire past-due domains ---
        expired_domains = self.search([
            ("state", "in", ("active", "expiring_soon")),
            ("date_expiration", "<", today),
        ])
        if expired_domains:
            expired_domains.write({"state": "expired"})
            _logger.info(
                "Auto-expire : %d domaine(s) marque(s) comme expire(s)",
                len(expired_domains),
            )

        # --- ntfy push summary for newly flagged expirations ---
        if expiring_domains or ssl_expiring or expired_domains:
            Ntfy = self.env["hosting.ntfy"]
            body_lines = []
            if expired_domains:
                body_lines.append(f"Domaines expirés : {len(expired_domains)}")
                for d in expired_domains[:5]:
                    body_lines.append(f"- {d.name} ({d.date_expiration})")
            if expiring_domains:
                body_lines.append("")
                body_lines.append(f"Domaines proches expiration : {len(expiring_domains)}")
                for d in expiring_domains[:5]:
                    body_lines.append(
                        f"- {d.name} — {d.days_until_expiration} j ({d.date_expiration})"
                    )
            if ssl_expiring:
                body_lines.append("")
                body_lines.append(f"Certificats SSL proches expiration : {len(ssl_expiring)}")
                for d in ssl_expiring[:5]:
                    body_lines.append(
                        f"- {d.name} — {d.days_until_ssl_expiry} j ({d.ssl_expiry_date})"
                    )
            has_expired = bool(expired_domains)
            Ntfy.send(
                title=("DOMAINES/SSL : expirations détectées"
                       + (" — domaines déjà expirés" if has_expired else "")),
                body="\n".join(body_lines),
                priority="urgent" if has_expired else "high",
                tags="lock,calendar",
            )

    @api.model
    def _cron_sync_cloudflare_domains(self):
        """Synchroniser les domaines depuis l'API Cloudflare Registrar."""
        try:
            import requests  # noqa: PLC0415
        except ImportError:
            _logger.error("Le module 'requests' est requis pour la synchronisation Cloudflare.")
            return

        ICP = self.env["ir.config_parameter"].sudo()
        cf_email = ICP.get_param("hosting.cloudflare_email", "")
        cf_api_key = ICP.get_param("hosting.cloudflare_api_key", "")
        cf_account_id = ICP.get_param("hosting.cloudflare_account_id", "")

        if not cf_email or not cf_api_key or not cf_account_id:
            _logger.info(
                "Sync Cloudflare : identifiants non configures, synchronisation ignoree."
            )
            return

        headers = {
            "X-Auth-Email": cf_email,
            "X-Auth-Key": cf_api_key,
            "Content-Type": "application/json",
        }

        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/registrar/domains"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            _logger.error("Sync Cloudflare : erreur API - %s", exc)
            return

        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            _logger.error("Sync Cloudflare : erreur API - %s", errors)
            return

        domains_data = data.get("result", [])
        updated = 0
        created = 0

        for cf_domain in domains_data:
            domain_name = cf_domain.get("name", "")
            if not domain_name:
                continue
            try:
                result = self._sync_single_cloudflare_domain(cf_domain, domain_name)
                if result == "updated":
                    updated += 1
                elif result == "created":
                    created += 1
            except Exception:
                _logger.exception(
                    "Sync Cloudflare : erreur lors du traitement de %s", domain_name
                )

        ICP.set_param(
            "hosting.last_cloudflare_sync",
            fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        _logger.info(
            "Sync Cloudflare terminee : %d domaine(s) mis a jour, %d cree(s) sur %d retourne(s).",
            updated,
            created,
            len(domains_data),
        )

    @api.model
    def _sync_single_cloudflare_domain(self, cf_data, domain_name):
        """Synchroniser un seul domaine depuis les donnees Cloudflare.

        Returns:
            str: 'updated', 'created', or 'skipped'
        """
        # Parse expiration date
        expires_at = cf_data.get("expires_at", "")
        expiration_date = False
        if expires_at:
            try:
                expiration_date = date_type.fromisoformat(expires_at[:10])
            except (ValueError, TypeError):
                _logger.warning(
                    "Sync Cloudflare : date d'expiration invalide pour %s : %s",
                    domain_name,
                    expires_at,
                )

        auto_renew = cf_data.get("auto_renew", False)
        registrar = "Cloudflare"

        # Search existing domain
        existing = self.search([("name", "=ilike", domain_name)], limit=1)

        if existing:
            vals = {}
            if expiration_date and existing.date_expiration != expiration_date:
                vals["date_expiration"] = expiration_date
            if existing.auto_renew != auto_renew:
                vals["auto_renew"] = auto_renew
            if existing.registrar != registrar:
                vals["registrar"] = registrar

            if vals:
                existing.write(vals)
                # Build chatter message
                changes = []
                if "date_expiration" in vals:
                    changes.append(f"Expiration : {expiration_date}")
                if "auto_renew" in vals:
                    changes.append(
                        f"Renouvellement auto : {'Oui' if auto_renew else 'Non'}"
                    )
                if "registrar" in vals:
                    changes.append(f"Registraire : {registrar}")
                existing.message_post(
                    body=f"<p>Synchronisation Cloudflare — {', '.join(changes)}</p>",
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
                return "updated"
            return "skipped"

        # Domain not found — create it
        new_domain = self.create({
            "name": domain_name,
            "partner_id": self.env.company.partner_id.id,
            "registrar": registrar,
            "date_expiration": expiration_date,
            "auto_renew": auto_renew,
            "state": "active",
        })
        new_domain.message_post(
            body=f"<p>Domaine cree automatiquement depuis la synchronisation Cloudflare.</p>",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return "created"
