from odoo import _, api, fields, models

# Fields whose presence counts toward the completeness score.
# Companies are not expected to have a job title or a parent company.
_PERSON_CHECKS = ("email", "phone_or_mobile", "function", "company", "address", "website")
_COMPANY_CHECKS = ("email", "phone_or_mobile", "address", "website")


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_enrichment_completeness = fields.Integer(
        string="Complétude",
        compute="_compute_enrichment_completeness",
        store=True,
        help="Pourcentage de coordonnées renseignées (courriel, téléphone, "
             "fonction, société, adresse, site web).",
    )

    @api.depends("email", "phone", "mobile", "function", "parent_id",
                 "company_name", "street", "city", "website", "is_company")
    def _compute_enrichment_completeness(self):
        for p in self:
            signals = {
                "email": bool(p.email),
                "phone_or_mobile": bool(p.phone or p.mobile),
                "function": bool(p.function),
                "company": bool(p.parent_id or p.company_name),
                "address": bool(p.street or p.city),
                "website": bool(p.website),
            }
            checks = _COMPANY_CHECKS if p.is_company else _PERSON_CHECKS
            p.x_enrichment_completeness = round(
                100 * sum(signals[c] for c in checks) / len(checks)
            )

    # ── Central apply path (used by every enrichment flow) ──────────

    def _apply_contact_vals(self, vals, source="enrichissement", overwrite=False):
        """Write contact fields, by default only filling blanks.

        ``vals`` maps res.partner field names to values (m2o fields carry an
        id). Returns the list of fields actually changed and posts a chatter
        summary. Never clobbers a populated field unless ``overwrite`` is set.
        """
        self.ensure_one()
        to_write = {}
        applied = []
        for fname, value in vals.items():
            if value in (None, "", False):
                continue
            field = self._fields.get(fname)
            if field is None:
                continue
            current = self[fname]
            if field.type == "many2one":
                current_id = current.id if current else False
                if (overwrite or not current_id) and current_id != value:
                    to_write[fname] = value
                    applied.append(fname)
            else:
                if (overwrite or not current) and current != value:
                    to_write[fname] = value
                    applied.append(fname)
        if to_write:
            self.write(to_write)
            self.message_post(body=self._enrichment_log_html(source, applied))
        return applied

    def _enrichment_log_html(self, source, applied):
        labels = []
        for fname in applied:
            field = self._fields.get(fname)
            labels.append(field.string if field else fname)
        items = "".join("<li>%s</li>" % label for label in labels)
        return _(
            "<p>Contact enrichi via <b>%(source)s</b> :</p><ul>%(items)s</ul>"
        ) % {"source": source, "items": items}

    @api.model
    def _enrich_country_id(self, name):
        """Resolve a free-text country name/code to a res.country id (or False)."""
        if not name:
            return False
        country = self.env["res.country"].search(
            ["|", ("name", "=ilike", name.strip()), ("code", "=ilike", name.strip())],
            limit=1,
        )
        return country.id if country else False

    # ── Wizard launchers (header / smart buttons) ───────────────────

    def action_scan_business_card(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Numériser une carte d'affaires"),
            "res_model": "bf.contact.card.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_target_partner_id": self.id},
        }

    def action_enrich_from_emails(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enrichir depuis les courriels"),
            "res_model": "bf.contact.enrich.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_partner_id": self.id, "default_source": "signature"},
        }

    def action_enrich_from_web(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enrichir depuis le site web"),
            "res_model": "bf.contact.enrich.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_partner_id": self.id, "default_source": "web"},
        }
