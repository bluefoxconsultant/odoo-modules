"""mail.compose.message override: explicit À / C.c. / C.c.i. fields.

Activated by the ``bf_email_split_recipients`` flag, which the bf_email
reply/forward/reply_all dispatchers set via ``default_bf_email_split_recipients``
in the composer context. When inactive, the composer behaves identically to
stock Odoo (rétro-compat with every other module that opens this wizard).

When active:
  * ``partner_ids`` is computed as the union of the three split lists, so
    Odoo's standard notification + chatter follower flow is unchanged.
  * ``email_cc`` (Char) is injected into the per-record post values so the
    Cc header is set on the resulting ``mail.message`` (visible in chatter +
    propagated to outbound notification mails).
  * BCC partners are present in ``partner_ids`` but absent from ``email_cc``,
    so each BCC recipient receives their own notification mail.mail without
    appearing in the visible Cc header (Gmail-style silent BCC).
"""

from odoo import api, fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    bf_email_split_recipients = fields.Boolean(
        string="Mode À / C.c. / C.c.i.",
        default=False,
        help="Active la séparation explicite des destinataires À / C.c. / C.c.i. "
             "(activé automatiquement par bf_email_management lors d'une réponse "
             "depuis l'inbox unifiée).",
    )
    bf_to_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="bf_compose_to_partner_rel",
        column1="compose_id",
        column2="partner_id",
        string="À",
        help="Destinataires principaux (en-tête To).",
    )
    bf_cc_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="bf_compose_cc_partner_rel",
        column1="compose_id",
        column2="partner_id",
        string="C.c.",
        help="Copie conforme (en-tête Cc).",
    )
    bf_bcc_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="bf_compose_bcc_partner_rel",
        column1="compose_id",
        column2="partner_id",
        string="C.c.i.",
        help="Copie conforme invisible : reçoit le courriel mais n'apparaît "
             "ni dans To ni dans Cc des destinataires.",
    )

    @api.onchange(
        "bf_to_partner_ids",
        "bf_cc_partner_ids",
        "bf_bcc_partner_ids",
        "bf_email_split_recipients",
    )
    def _onchange_bf_split_recipients(self):
        for wiz in self:
            if wiz.bf_email_split_recipients:
                wiz.partner_ids = (
                    wiz.bf_to_partner_ids
                    | wiz.bf_cc_partner_ids
                    | wiz.bf_bcc_partner_ids
                )

    def _action_send_mail(self, auto_commit=False):
        for wiz in self:
            if wiz.bf_email_split_recipients:
                wiz.partner_ids = (
                    wiz.bf_to_partner_ids
                    | wiz.bf_cc_partner_ids
                    | wiz.bf_bcc_partner_ids
                )
        return super()._action_send_mail(auto_commit=auto_commit)

    def _prepare_mail_values_rendered(self, res_ids):
        result = super()._prepare_mail_values_rendered(res_ids)
        self._bf_inject_split_headers(result, res_ids)
        return result

    def _prepare_mail_values_dynamic(self, res_ids):
        result = super()._prepare_mail_values_dynamic(res_ids)
        self._bf_inject_split_headers(result, res_ids)
        return result

    def _bf_inject_split_headers(self, values_by_id, res_ids):
        """Inject email_to / email_cc derived from the split partner lists."""
        self.ensure_one()
        if not self.bf_email_split_recipients:
            return
        to_emails = ",".join(
            p.email for p in self.bf_to_partner_ids if p.email
        )
        cc_emails = ",".join(
            p.email for p in self.bf_cc_partner_ids if p.email
        )
        for res_id in res_ids:
            entry = values_by_id.get(res_id)
            if entry is None:
                continue
            if to_emails:
                entry["email_to"] = to_emails
            if cc_emails:
                entry["email_cc"] = cc_emails
