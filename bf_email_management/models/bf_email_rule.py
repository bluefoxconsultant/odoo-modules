"""bf.email.rule — minimal rule engine for auto-categorization.

Rules fire on bf.email.create() after _compute_category, so manual writes
still win. Mass action ``action_replay_rules`` backfills existing rows.

Restricted to ``group_email_manager`` (safe_eval risk on domain conditions).
"""

import logging
import re

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class BfEmailRule(models.Model):
    _name = "bf.email.rule"
    _description = "Règle de catégorisation courriels"
    _order = "sequence, id"

    name = fields.Char(string="Nom", required=True)
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)

    condition_type = fields.Selection(
        selection=[
            ("domain", "Domaine Odoo"),
            ("regex_subject", "Regex sur l'objet"),
            ("regex_from", "Regex sur l'expéditeur"),
            ("regex_body", "Regex sur l'aperçu"),
            ("header_present", "En-tête présent"),
            ("partner_tag", "Champ partenaire (booléen ou comparaison)"),
        ],
        string="Type de condition",
        required=True,
        default="regex_from",
        help=(
            "domain : expression Odoo évaluée contre l'enregistrement (record). "
            "regex_* : motif Python regex (insensible à la casse). "
            "header_present : chaîne à chercher dans raw_headers (ex: List-Unsubscribe). "
            "partner_tag : expression booléenne sur partner — ex: customer_rank > 0."
        ),
    )
    condition_value = fields.Text(
        string="Valeur",
        required=True,
        help="Voir l'aide du type de condition.",
    )

    set_category = fields.Selection(
        selection=[
            ("client", "Client"),
            ("internal", "Interne"),
            ("vendor", "Fournisseur"),
            ("notification", "Notification"),
            ("marketing", "Marketing"),
        ],
        string="Définir la catégorie",
    )
    set_priority = fields.Selection(
        selection=[
            ("0", "Normal"),
            ("1", "Faible"),
            ("2", "Élevée"),
            ("3", "Urgente"),
        ],
        string="Définir la priorité",
    )
    set_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Lier au contact",
    )
    set_handled = fields.Boolean(
        string="Marquer comme traité",
        help="Sort le courriel de la boîte de réception (utile pour "
             "marketing/notifications qui ne demandent pas d'action).",
    )
    stop_processing = fields.Boolean(
        string="Arrêter ici",
        help="Si coché, les règles suivantes ne sont pas évaluées.",
    )

    description = fields.Text(string="Notes")

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    def _match(self, record):
        """Return True if this rule's condition matches ``record`` (bf.email)."""
        self.ensure_one()
        if not self.active:
            return False
        try:
            if self.condition_type == "domain":
                domain = safe_eval(self.condition_value, {
                    "record": record,
                    "rec": record,
                    "uid": self.env.uid,
                    "user": self.env.user,
                })
                if isinstance(domain, list):
                    return bool(record.search_count(
                        domain + [("id", "=", record.id)]
                    ))
                return bool(domain)
            if self.condition_type == "regex_subject":
                return bool(re.search(
                    self.condition_value, record.subject or "",
                    re.IGNORECASE,
                ))
            if self.condition_type == "regex_from":
                return bool(re.search(
                    self.condition_value, record.email_from or "",
                    re.IGNORECASE,
                ))
            if self.condition_type == "regex_body":
                return bool(re.search(
                    self.condition_value, record.body_preview or "",
                    re.IGNORECASE,
                ))
            if self.condition_type == "header_present":
                return self.condition_value.lower() in (
                    record.raw_headers or ""
                ).lower()
            if self.condition_type == "partner_tag":
                partner = record.partner_id or record.author_id
                if not partner:
                    return False
                return bool(safe_eval(self.condition_value, {
                    "partner": partner,
                    "p": partner,
                }))
        except Exception:
            _logger.warning(
                "bf.email.rule %s: evaluation error on record %s",
                self.id, record.id, exc_info=True,
            )
            return False
        return False

    # ------------------------------------------------------------------
    # Mass action: replay rules over existing rows
    # ------------------------------------------------------------------
    @api.model
    def action_replay_rules(self):
        """Re-run all rules over every bf.email row not yet handled.

        Bound as a server action; intended for backfill after editing rules.
        """
        BfEmail = self.env["bf.email"].sudo()
        rows = BfEmail.search([("is_handled", "=", False)])
        rows._apply_rules()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Règles rejouées",
                "message": f"{len(rows)} courriel(s) ré-évalué(s).",
                "type": "success",
                "sticky": False,
            },
        }
