# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import re

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HostingSoftware(models.Model):
    _name = "hosting.software"
    _description = "Catalogue de logiciels d'hébergement"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Nom du logiciel",
        required=True,
        translate=True,
        tracking=True,
    )
    code = fields.Char(
        string="Code court",
        required=True,
        help="Identifiant court (ex. : NC pour Nextcloud, OD pour Odoo)",
    )
    software_type = fields.Selection(
        selection=[
            ("self_hosted", "Auto-hébergé"),
            ("saas", "SaaS"),
            ("managed", "Géré"),
        ],
        string="Type",
        default="self_hosted",
        required=True,
        tracking=True,
    )
    latest_version = fields.Char(
        string="Dernière version",
        tracking=True,
    )
    latest_version_date = fields.Date(
        string="Date de la dernière version",
        help="Date de publication de la dernière version",
    )
    update_available = fields.Boolean(
        string="Mises à jour disponibles",
        compute="_compute_update_available",
        store=True,
        help="Vrai si des services nécessitent des mises à jour",
    )
    github_url = fields.Char(
        string="URL GitHub",
        help="URL du dépôt pour la vérification automatique de version",
    )
    docker_image = fields.Char(
        string="Image Docker",
        help="Référence de l'image Docker (ex. : nextcloud:latest)",
    )

    # Configuration de vérification de version
    version_check_method = fields.Selection(
        selection=[
            ("none", "Manuel"),
            ("github", "Versions GitHub"),
            ("docker_hub", "Docker Hub"),
            ("gitlab", "Versions GitLab"),
        ],
        string="Méthode de vérification de version",
        default="none",
        help="Comment vérifier automatiquement les nouvelles versions",
    )
    github_repo = fields.Char(
        string="Dépôt GitHub",
        help="Dépôt au format « propriétaire/dépôt » (ex. : « nextcloud/server »)",
    )
    docker_hub_repo = fields.Char(
        string="Dépôt Docker Hub",
        help="Dépôt au format « propriétaire/image » ou « library/image » pour les images officielles (ex. : « nextcloud » ou « library/postgres »)",
    )
    gitlab_repo = fields.Char(
        string="Dépôt GitLab",
        help="URL complète du projet GitLab (ex. : « https://gitlab.com/cryptpad/cryptpad »)",
    )
    version_regex = fields.Char(
        string="Expression régulière de version",
        default=r"v?(\d+\.\d+\.?\d*)",
        help="Patron regex pour extraire le numéro de version des étiquettes. Utiliser un groupe de capture pour la version.",
    )
    version_prefix = fields.Char(
        string="Préfixe de version",
        help="Préfixe à retirer des étiquettes de version (ex. : « v », « release- »)",
    )
    last_version_check = fields.Datetime(
        string="Dernière vérification de version",
        readonly=True,
    )
    version_check_error = fields.Char(
        string="Dernière erreur de vérification",
        readonly=True,
    )

    image = fields.Image(
        string="Logo",
        max_width=256,
        max_height=256,
    )
    version_ids = fields.One2many(
        comodel_name="hosting.software.version",
        inverse_name="software_id",
        string="Versions",
    )
    service_ids = fields.One2many(
        comodel_name="hosting.service",
        inverse_name="software_id",
        string="Services",
    )
    service_count = fields.Integer(
        string="Nombre de services",
        compute="_compute_service_count",
    )
    maintenance_template_ids = fields.One2many(
        comodel_name="hosting.maintenance.template",
        inverse_name="software_id",
        string="Modèles de maintenance",
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
    )
    notes = fields.Html(
        string="Notes",
        translate=True,
    )

    _sql_constraints = [
        ("code_uniq", "UNIQUE(code)", "Le code du logiciel doit être unique !"),
    ]

    @api.depends("service_ids")
    def _compute_service_count(self):
        for record in self:
            record.service_count = len(record.service_ids)

    @api.depends("service_ids.update_available")
    def _compute_update_available(self):
        for record in self:
            record.update_available = any(
                service.update_available for service in record.service_ids
            )

    def action_view_services(self):
        """Ouvrir les services utilisant ce logiciel."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Services - {self.name}",
            "res_model": "hosting.service",
            "views": [[False, "list"], [False, "form"], [False, "kanban"]],
            "domain": [("software_id", "=", self.id)],
            "context": {"default_software_id": self.id},
        }

    def action_view_versions(self):
        """Ouvrir l'historique des versions pour ce logiciel."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Versions - {self.name}",
            "res_model": "hosting.software.version",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("software_id", "=", self.id)],
            "context": {"default_software_id": self.id},
        }

    def action_check_version(self):
        """Déclencher manuellement la vérification de version pour ce logiciel."""
        self.ensure_one()
        self._check_version()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Vérification de version terminée",
                "message": f"Dernière version : {self.latest_version or 'Non trouvée'}"
                if not self.version_check_error
                else f"Erreur : {self.version_check_error}",
                "type": "success" if not self.version_check_error else "warning",
                "sticky": False,
            },
        }

    def _check_version(self):
        """Vérifier les nouvelles versions selon la méthode configurée."""
        self.ensure_one()
        self.version_check_error = False

        try:
            if self.version_check_method == "github":
                self._check_github_version()
            elif self.version_check_method == "docker_hub":
                self._check_docker_hub_version()
            elif self.version_check_method == "gitlab":
                self._check_gitlab_version()

            self.last_version_check = fields.Datetime.now()
        except Exception as e:
            self.version_check_error = str(e)[:255]
            _logger.warning(
                "Version check failed for %s: %s", self.name, str(e)
            )

    def _check_github_version(self):
        """Vérifier l'API des versions GitHub pour la dernière version."""
        if not self.github_repo:
            raise ValueError("GitHub repository not configured")

        url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
        headers = {"Accept": "application/vnd.github.v3+json"}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            # Try tags instead of releases
            url = f"https://api.github.com/repos/{self.github_repo}/tags"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                tags = response.json()
                if tags:
                    version = self._extract_version(tags[0].get("name", ""))
                    if version:
                        self._update_latest_version(version)
                        return
            raise ValueError(f"No releases or tags found for {self.github_repo}")

        response.raise_for_status()
        data = response.json()

        tag_name = data.get("tag_name", "")
        version = self._extract_version(tag_name)
        if version:
            published_at = data.get("published_at", "")
            release_date = None
            if published_at:
                release_date = fields.Date.to_date(published_at[:10])
            self._update_latest_version(version, release_date)

    def _check_docker_hub_version(self):
        """Vérifier l'API Docker Hub pour la dernière étiquette de version."""
        if not self.docker_hub_repo:
            raise ValueError("Docker Hub repository not configured")

        repo = self.docker_hub_repo
        # Handle official images (no slash)
        if "/" not in repo:
            repo = f"library/{repo}"

        url = f"https://hub.docker.com/v2/repositories/{repo}/tags"
        params = {"page_size": 100, "ordering": "last_updated"}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        tags = data.get("results", [])
        if not tags:
            raise ValueError(f"No tags found for {self.docker_hub_repo}")

        # Find the best version tag (skip 'latest', 'stable', etc.)
        skip_tags = {"latest", "stable", "edge", "dev", "beta", "alpha", "rc", "nightly"}
        for tag_info in tags:
            tag_name = tag_info.get("name", "")
            if tag_name.lower() in skip_tags:
                continue

            version = self._extract_version(tag_name)
            if version:
                last_updated = tag_info.get("last_updated", "")
                release_date = None
                if last_updated:
                    release_date = fields.Date.to_date(last_updated[:10])
                self._update_latest_version(version, release_date)
                return

        raise ValueError(f"No version tags found for {self.docker_hub_repo}")

    def _check_gitlab_version(self):
        """Vérifier l'API des versions GitLab pour la dernière version."""
        if not self.gitlab_repo:
            raise ValueError("GitLab repository not configured")

        # Parse GitLab URL to extract project path
        import urllib.parse

        parsed = urllib.parse.urlparse(self.gitlab_repo)
        gitlab_host = f"{parsed.scheme}://{parsed.netloc}"
        project_path = parsed.path.strip("/")
        encoded_path = urllib.parse.quote(project_path, safe="")

        url = f"{gitlab_host}/api/v4/projects/{encoded_path}/releases"

        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            # Try tags instead
            url = f"{gitlab_host}/api/v4/projects/{encoded_path}/repository/tags"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                tags = response.json()
                if tags:
                    version = self._extract_version(tags[0].get("name", ""))
                    if version:
                        self._update_latest_version(version)
                        return
            raise ValueError(f"No releases or tags found for {self.gitlab_repo}")

        response.raise_for_status()
        data = response.json()

        if not data:
            raise ValueError(f"No releases found for {self.gitlab_repo}")

        release = data[0]
        tag_name = release.get("tag_name", "")
        version = self._extract_version(tag_name)
        if version:
            released_at = release.get("released_at", "")
            release_date = None
            if released_at:
                release_date = fields.Date.to_date(released_at[:10])
            self._update_latest_version(version, release_date)

    def _extract_version(self, tag_name):
        """Extraire le numéro de version du nom d'étiquette en utilisant le regex configuré."""
        if not tag_name:
            return None

        # Strip prefix if configured
        if self.version_prefix and tag_name.startswith(self.version_prefix):
            tag_name = tag_name[len(self.version_prefix):]

        # Apply regex if configured (with timeout to prevent ReDoS)
        if self.version_regex:
            try:
                import signal

                def _timeout_handler(signum, frame):
                    raise TimeoutError("Regex evaluation timed out")

                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(2)  # 2-second timeout
                try:
                    match = re.search(self.version_regex, tag_name[:500])
                    if match:
                        return match.group(1) if match.groups() else match.group(0)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            except (re.error, TimeoutError) as exc:
                _logger.warning("Regex error for %s (%s): %s", self.name, self.version_regex, exc)

        return tag_name

    def _update_latest_version(self, version, release_date=None):
        """Mettre à jour la dernière version et créer un enregistrement de version si nouveau."""
        if self.latest_version != version:
            vals = {"latest_version": version}
            if release_date:
                vals["latest_version_date"] = release_date
            self.write(vals)

            # Create version record if it doesn't exist
            existing = self.env["hosting.software.version"].search([
                ("software_id", "=", self.id),
                ("version", "=", version),
            ], limit=1)
            if not existing:
                self.env["hosting.software.version"].create({
                    "software_id": self.id,
                    "version": version,
                    "release_date": release_date,
                    "support_status": "supported",
                })

            # Trigger recomputation of update_available on services
            self.service_ids._compute_update_available()

    @api.model
    def _cron_check_versions(self):
        """Tâche planifiée pour vérifier les nouvelles versions de tous les logiciels configurés."""
        software_to_check = self.search([
            ("version_check_method", "!=", "none"),
        ])
        updates = []
        for software in software_to_check:
            previous = software.latest_version
            try:
                software._check_version()
                # Commit after each check to avoid losing all progress on error
                self.env.cr.commit()
            except Exception as e:
                _logger.error(
                    "Version check cron failed for %s: %s", software.name, str(e)
                )
                self.env.cr.rollback()
                continue
            software.invalidate_recordset(["latest_version"])
            if software.latest_version and software.latest_version != previous:
                updates.append((software.name, previous or "?", software.latest_version))

        if updates:
            body_lines = [f"- {name} : {old} → {new}" for name, old, new in updates[:15]]
            if len(updates) > 15:
                body_lines.append(f"… et {len(updates) - 15} de plus")
            self.env["hosting.ntfy"].send(
                title=f"VERSIONS : {len(updates)} nouvelle(s) version(s) détectée(s)",
                body="\n".join(body_lines),
                priority="default",
                tags="package,arrow_up",
            )
