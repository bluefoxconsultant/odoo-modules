from odoo import _, api, fields, models


ADDRESSING_LABELS = {
    "tu": "tu",
    "vous": "vous",
    "auto": "auto",
}

TONE_LABELS = {
    "warm": "chaleureux",
    "neutral": "neutre",
    "formal": "formel",
    "tense": "tendu",
    "na": "n/d",
}

PAYER_LABELS = {
    "excellent": "excellent",
    "good": "bon",
    "average": "moyen",
    "slow": "lent",
    "poor": "mauvais",
    "na": "n/d",
}


class ContactPersona(models.Model):
    _name = "contact.persona"
    _description = "Persona d'un contact (préférences, ton, payeur, KPIs)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    partner_id = fields.Many2one(
        "res.partner", required=True, ondelete="cascade", index=True,
        tracking=True,
    )
    name = fields.Char(compute="_compute_name", store=True, index=True)
    active = fields.Boolean(default=True)

    # --- Communication preferences ---------------------------------------
    addressing_style = fields.Selection(
        [("tu", "Tutoiement"), ("vous", "Vouvoiement"), ("auto", "Auto")],
        default="auto", required=True, tracking=True,
    )
    preferred_salutation = fields.Char(
        help="Ex.: 'Bonjour Jean', 'Cher Maître Tremblay'.",
        tracking=True,
    )
    closing_formula = fields.Char(
        help="Ex.: 'Cordialement', 'Bien à vous'.",
    )
    preferred_language = fields.Selection(
        selection="_selection_preferred_language",
        help="Par défaut, la langue du contact.",
    )
    custom_appellations = fields.Text(
        help="Surnoms, titres à utiliser ou à éviter, formules épistolaires.",
    )

    # --- Personal details (sensible) -------------------------------------
    personal_details = fields.Html(
        help="Famille, hobbies, jalons. Visible aux gestionnaires de personas seulement.",
        groups="bf_persona.group_persona_manager",
    )
    shared_knowledge_item_ids = fields.Many2many(
        "project.knowledge.item",
        relation="contact_persona_knowledge_item_rel",
        column1="persona_id",
        column2="item_id",
        string="Éléments partagés avec le contact",
    )

    # --- Payer behavior ---------------------------------------------------
    payer_quality = fields.Selection(
        [
            ("excellent", "Excellent"),
            ("good", "Bon"),
            ("average", "Moyen"),
            ("slow", "Lent"),
            ("poor", "Mauvais"),
            ("na", "N/D"),
        ],
        default="na", tracking=True,
    )
    payer_notes = fields.Text()
    avg_payment_delay_days = fields.Float(
        compute="_compute_avg_payment_delay_days", store=True,
        help="Délai moyen entre la date de facture et la date de paiement (jours).",
    )

    # --- Tone -------------------------------------------------------------
    tone_summary = fields.Selection(
        [
            ("warm", "Chaleureux"),
            ("neutral", "Neutre"),
            ("formal", "Formel"),
            ("tense", "Tendu"),
            ("na", "N/D"),
        ],
        default="na", tracking=True,
        help="Ton du contact envers nous (Blue Fox), observé dans ses courriels reçus.",
    )
    tone_notes = fields.Html(
        help="Notes sur le ton du contact envers nous.",
    )
    our_tone_summary = fields.Selection(
        [
            ("warm", "Chaleureux"),
            ("neutral", "Neutre"),
            ("formal", "Formel"),
            ("tense", "Tendu"),
            ("na", "N/D"),
        ],
        default="na", tracking=True,
        help="Notre ton (Blue Fox) envers le contact, observé dans les courriels sortants.",
    )
    our_tone_notes = fields.Html(
        help="Notes sur notre ton/posture envers le contact.",
    )
    tone_last_assessed = fields.Date()
    tone_is_stale = fields.Boolean(
        default=False, copy=False, index=True,
        help="Mis à True par le cron quand tone_last_assessed est vide ou > 6 mois.",
    )

    # --- Sub-records -----------------------------------------------------
    cc_rule_ids = fields.One2many("contact.cc.rule", "persona_id")
    kpi_ids = fields.One2many("contact.persona.kpi", "persona_id")

    # --- Claude bridge ---------------------------------------------------
    claude_context_summary = fields.Text(
        compute="_compute_claude_context_summary", store=True,
        help="Bloc texte injecté dans Tentaclaude pour guider le ton.",
    )

    _sql_constraints = [
        ("partner_unique", "unique(partner_id)",
         "Il existe déjà un persona pour ce contact."),
    ]

    # --- Compute helpers --------------------------------------------------
    @api.model
    def _selection_preferred_language(self):
        return self.env["res.lang"].get_installed()

    @api.depends("partner_id.display_name")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.partner_id.display_name or _("Persona sans contact")

    @api.depends(
        "partner_id",
        "partner_id.invoice_ids.invoice_date",
        "partner_id.invoice_ids.invoice_payments_widget",
        "partner_id.invoice_ids.payment_state",
    )
    def _compute_avg_payment_delay_days(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            if not rec.partner_id:
                rec.avg_payment_delay_days = 0.0
                continue
            invoices = AccountMove.search([
                ("partner_id", "=", rec.partner_id.id),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("paid", "in_payment", "reversed")),
                ("invoice_date", "!=", False),
            ], limit=200, order="invoice_date desc")
            deltas = []
            for inv in invoices:
                pay_date = inv._get_last_payment_date() if hasattr(inv, "_get_last_payment_date") else False
                if not pay_date:
                    pay_date = self._first_payment_date(inv)
                if pay_date and inv.invoice_date:
                    deltas.append((pay_date - inv.invoice_date).days)
            rec.avg_payment_delay_days = (
                sum(deltas) / len(deltas) if deltas else 0.0
            )

    def _first_payment_date(self, invoice):
        # Fallback: walk through reconciled payment lines and pick the earliest date.
        dates = []
        for line in invoice.line_ids:
            for partial in (line.matched_debit_ids | line.matched_credit_ids):
                counterpart = (
                    partial.debit_move_id
                    if partial.credit_move_id == line
                    else partial.credit_move_id
                )
                move = counterpart.move_id
                if move and move.date and move.id != invoice.id:
                    dates.append(move.date)
        return min(dates) if dates else False

    @api.depends(
        "partner_id.display_name",
        "addressing_style",
        "preferred_salutation",
        "closing_formula",
        "tone_summary",
        "tone_notes",
        "our_tone_summary",
        "our_tone_notes",
        "tone_is_stale",
        "payer_quality",
        "avg_payment_delay_days",
        "cc_rule_ids.category_id",
        "cc_rule_ids.cc_partner_ids",
        "cc_rule_ids.mandatory",
    )
    def _compute_claude_context_summary(self):
        for rec in self:
            rec.claude_context_summary = rec._build_claude_summary()

    def _build_claude_summary(self):
        self.ensure_one()
        from odoo.tools import html2plaintext
        if self.addressing_style == "auto":
            addressing = "auto (par défaut: vous)"
        else:
            addressing = ADDRESSING_LABELS.get(self.addressing_style, "auto")
        salut = self.preferred_salutation or "—"
        close = self.closing_formula or "—"
        tone = TONE_LABELS.get(self.tone_summary or "na", "n/d")
        our_tone = TONE_LABELS.get(self.our_tone_summary or "na", "n/d")
        payer = PAYER_LABELS.get(self.payer_quality or "na", "n/d")
        delay = (
            f" (moy. {self.avg_payment_delay_days:.0f}j)"
            if self.avg_payment_delay_days else ""
        )
        stale_tag = " [ton à rafraîchir]" if self.tone_is_stale else ""
        head = (
            f"[Persona {self.partner_id.display_name or '?'} — "
            f"{addressing}, salutation: \"{salut}\", clôture: \"{close}\", "
            f"ton: {tone}{stale_tag}]"
        )
        lines = [head]
        if self.our_tone_summary and self.our_tone_summary != "na":
            lines.append(f"Notre ton: {our_tone}.")
        lines.append(f"Payeur: {payer}{delay}.")
        rules = []
        for rule in self.cc_rule_ids:
            cc_names = ", ".join(p.display_name for p in rule.cc_partner_ids)
            mark = " (obligatoire)" if rule.mandatory else ""
            rules.append(f"{rule.category_id.name}→{cc_names}{mark}")
        if rules:
            lines.append("C.c. règles: " + "; ".join(rules) + ".")
        if self.tone_notes:
            note = html2plaintext(self.tone_notes).strip()
            if note:
                lines.append(f"Notes ton: {note[:280]}")
        if self.our_tone_notes:
            note = html2plaintext(self.our_tone_notes).strip()
            if note:
                lines.append(f"Notes notre ton: {note[:280]}")
        return "\n".join(lines)

    # --- Cache invalidation on res.partner ------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        partners = records.mapped("partner_id")
        if partners:
            partners.invalidate_recordset(["persona_id", "has_persona", "persona_summary"])
        return records

    def write(self, vals):
        res = super().write(vals)
        if "partner_id" in vals or "active" in vals:
            partners = self.mapped("partner_id")
            if partners:
                self.env.add_to_compute(
                    self.env["res.partner"]._fields["persona_id"], partners
                )
        return res

    def unlink(self):
        partners = self.mapped("partner_id")
        res = super().unlink()
        if partners:
            partners.invalidate_recordset(["persona_id", "has_persona", "persona_summary"])
        return res

    # --- Actions ----------------------------------------------------------
    @api.model
    def action_get_or_create_for_partner(self, partner_id):
        persona = self.with_context(active_test=False).search(
            [("partner_id", "=", partner_id)], limit=1
        )
        if not persona:
            persona = self.create({"partner_id": partner_id})
        elif not persona.active:
            persona.active = True
        return {
            "type": "ir.actions.act_window",
            "res_model": "contact.persona",
            "view_mode": "form",
            "res_id": persona.id,
            "target": "current",
        }

    def action_link_knowledge_items(self):
        self.ensure_one()
        Item = self.env["project.knowledge.item"]
        if not self.partner_id:
            return False
        candidates = Item.search([
            "|", "|",
            ("decision_maker_id", "=", self.partner_id.id),
            ("stakeholder_consulted_ids", "in", self.partner_id.id),
            ("stakeholder_informed_ids", "in", self.partner_id.id),
        ])
        new_items = candidates - self.shared_knowledge_item_ids
        if new_items:
            self.shared_knowledge_item_ids = [(4, item.id) for item in new_items]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Éléments de matrice liés"),
                "message": _("%d nouveau(x) élément(s) ajouté(s).") % len(new_items),
                "type": "success" if new_items else "info",
                "sticky": False,
            },
        }

    def action_launch_persona_skill(self, mode="refresh"):
        """Open the Claude chat panel with the /persona skill pre-filled.

        `mode` may be "read" (default in the skill) or "refresh" (recompute
        KPIs and write back, with confirmation).
        """
        self.ensure_one()
        name = self.partner_id.display_name or self.name or "?"
        prompt = f"/persona {mode} {name}"
        return {
            "type": "ir.actions.client",
            "tag": "claude_chat_launch",
            "params": {"prompt": prompt, "autosend": False},
        }

    @api.model
    def cron_recompute_payment_delay(self):
        # Recompute the stored field for all personas, in batches to keep the
        # cron memory-bounded.
        personas = self.search([])
        for chunk in (personas[i:i + 200] for i in range(0, len(personas), 200)):
            chunk._compute_avg_payment_delay_days()
            self.env.cr.commit()

    @api.model
    def cron_flag_stale_tones(self, threshold_days=180):
        from datetime import date, timedelta
        cutoff = date.today() - timedelta(days=threshold_days)
        stale = self.search([
            "|",
            ("tone_last_assessed", "=", False),
            ("tone_last_assessed", "<", cutoff),
        ])
        fresh = self.search([("tone_last_assessed", ">=", cutoff)])
        if stale:
            stale.filtered(lambda p: not p.tone_is_stale).write({"tone_is_stale": True})
        if fresh:
            fresh.filtered(lambda p: p.tone_is_stale).write({"tone_is_stale": False})
