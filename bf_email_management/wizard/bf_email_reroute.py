"""Reroute wizard: import an IMAP-only bf.email row into an Odoo chatter.

Builds a real ``mail.message`` on the chosen target record while preserving
the original Message-ID (so the RFC 2822 thread stays intact and the
``_should_sync`` cron path will skip the duplicate). Then promotes the
existing bf.email row from ``source='imap'`` orphan to a chatter row.
"""

import base64
import logging

from odoo import _, api, exceptions, fields, models

from ..models import bf_email_imap

_logger = logging.getLogger(__name__)


# Priority models surfaced first in the dropdown.
_PRIORITY_MODELS = (
    "project.task",
    "helpdesk.ticket",
    "res.partner",
    "crm.lead",
    "calendar.event",
    "account.move",
    "sale.order",
    "purchase.order",
    "mail.channel",
)


class BfEmailReroute(models.TransientModel):
    _name = "bf.email.reroute"
    _description = "Importer un courriel dans un chatter"

    bf_email_ids = fields.Many2many(
        comodel_name="bf.email",
        string="Courriels",
        required=True,
    )
    bf_email_count = fields.Integer(
        string="Nb courriels",
        compute="_compute_bf_email_count",
    )
    sample_subject = fields.Char(
        string="Sujet (échantillon)",
        compute="_compute_sample",
    )
    sample_from = fields.Char(
        string="De (échantillon)",
        compute="_compute_sample",
    )

    target_reference = fields.Reference(
        selection="_get_thread_models",
        string="Dossier cible",
        required=True,
        help="Sélectionnez le modèle puis l'enregistrement (tâche, ticket, "
             "contact, opportunité, événement, facture, etc.) sur lequel "
             "poster le courriel.",
    )
    mark_replied = fields.Boolean(
        string="Marquer comme répondu",
        default=False,
        help="Si activé, les courriels entrants seront marqués 'Répondu' "
             "après import (utile lorsque vous routez la réponse en même temps).",
    )
    archive_after = fields.Boolean(
        string="Archiver après import",
        default=False,
        help="Archive la ligne bf.email après le re-routage réussi.",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Prêt"),
            ("done", "Terminé"),
        ],
        default="draft",
    )
    result_text = fields.Text(
        string="Résultat",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Defaults / computes
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = self.env.context
        ids = ctx.get("default_bf_email_ids") or ctx.get("active_ids") or []
        if isinstance(ids, list) and ids and isinstance(ids[0], (list, tuple)):
            # form (6, 0, ids) command
            ids = ids[0][2] if len(ids[0]) > 2 else []
        if ids:
            vals.setdefault("bf_email_ids", [(6, 0, ids)])
            # Default mark_replied=True if all selected rows are inbound.
            recs = self.env["bf.email"].browse(ids)
            if recs and all(r.direction == "in" for r in recs):
                vals.setdefault("mark_replied", True)
        return vals

    @api.depends("bf_email_ids")
    def _compute_bf_email_count(self):
        for rec in self:
            rec.bf_email_count = len(rec.bf_email_ids)

    @api.depends("bf_email_ids")
    def _compute_sample(self):
        for rec in self:
            first = rec.bf_email_ids[:1]
            rec.sample_subject = first.subject or ""
            rec.sample_from = first.email_from or ""

    @api.model
    def _get_thread_models(self):
        """Return [(model, name)] for every model with mail.thread."""
        Model = self.env["ir.model"].sudo()
        records = Model.search([
            ("is_mail_thread", "=", True),
            ("transient", "=", False),
        ])
        items = [(r.model, r.name) for r in records if r.model]
        items.sort(key=lambda x: (
            _PRIORITY_MODELS.index(x[0]) if x[0] in _PRIORITY_MODELS else len(_PRIORITY_MODELS),
            x[1] or x[0],
        ))
        return items

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if not self.target_reference:
            raise exceptions.UserError(_("Veuillez sélectionner un dossier cible."))
        if not self.bf_email_ids:
            raise exceptions.UserError(_("Aucun courriel à router."))

        target = self.target_reference
        target_model = target._name
        target_id = target.id

        # Read access check on the target.
        try:
            self.env[target_model].check_access_rights("write")
            target.check_access_rule("write")
        except exceptions.AccessError as exc:
            raise exceptions.UserError(_(
                "Accès refusé sur %(model)s #%(id)s : %(err)s",
                model=target_model, id=target_id, err=exc,
            )) from exc

        results = []
        successes = 0
        for bf in self.bf_email_ids:
            try:
                msg_id = self._reroute_one(bf, target_model, target_id)
                results.append(f"OK {bf.id} → mail.message #{msg_id}")
                successes += 1
            except Exception as exc:  # pragma: no cover (defensive)
                _logger.warning(
                    "Reroute bf.email #%s failed: %s", bf.id, exc, exc_info=True,
                )
                results.append(f"ERR {bf.id} → {exc}")

        self.write({
            "state": "done",
            "result_text": "\n".join(results) + f"\n\n{successes}/{len(self.bf_email_ids)} importés.",
        })

        if successes == 1 and len(self.bf_email_ids) == 1:
            # Single reroute: open the target record.
            return {
                "type": "ir.actions.act_window",
                "res_model": target_model,
                "res_id": target_id,
                "view_mode": "form",
                "views": [[False, "form"]],
                "target": "current",
            }
        # Bulk: keep the wizard open with results.
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    def _reroute_one(self, bf, target_model, target_id):
        """Import one bf.email row into a chatter and promote the row.

        Returns the new ``mail.message.id`` posted on the target record.
        Raises if the row has neither a stored RFC822 nor a linked mail.message.
        """
        if bf.mail_message_id:
            # Already a chatter row; simply re-link to the target chatter.
            # We post a copy on the target (preserving Message-ID is unsafe
            # for an already-routed message, so we use a fresh internal note
            # with the same content). For now, raise: the user wanted to
            # reroute IMAP-only rows, not duplicate chatter rows.
            raise exceptions.UserError(_(
                "Le courriel #%s est déjà attaché à un chatter (%s #%s). "
                "Le re-routage des courriels déjà en chatter n'est pas supporté.",
                bf.id, bf.res_model, bf.res_id,
            ))

        if not bf.raw_rfc822:
            raise exceptions.UserError(_(
                "Le courriel #%s n'a pas de RFC 2822 stocké. "
                "Impossible de le re-poster sur le chatter.", bf.id,
            ))

        raw_bytes = base64.b64decode(bf.raw_rfc822)
        msg = bf_email_imap.parse_rfc822(raw_bytes)

        body_html, body_plain = bf_email_imap.extract_body(msg)
        body = body_html or (f"<pre>{body_plain}</pre>" if body_plain else "")

        # Attachments: re-create as ir.attachment owned by the target record.
        att_ids = []
        for filename, content in bf_email_imap.extract_attachments(msg):
            att = self.env["ir.attachment"].create({
                "name": filename,
                "datas": bf_email_imap.attachment_to_b64(content),
                "res_model": target_model,
                "res_id": target_id,
            })
            att_ids.append(att.id)

        post_kwargs = {
            "body": body,
            "subject": bf.subject or str(msg.get("Subject", "")),
            "message_type": "email",
            "subtype_xmlid": "mail.mt_comment",
            "email_from": bf.email_from or str(msg.get("From", "")),
            "author_id": bf.author_id.id if bf.author_id else False,
            "body_is_html": True,
        }
        if bf.message_id_header:
            post_kwargs["message_id"] = bf.message_id_header
        if bf.date:
            post_kwargs["date"] = fields.Datetime.to_string(bf.date)
        if att_ids:
            post_kwargs["attachment_ids"] = att_ids

        target = self.env[target_model].browse(target_id)
        target_with_ctx = target.with_context(
            mail_create_nosubscribe=True,
            mail_create_nolog=True,
            mail_notify_force_send=False,
            mail_auto_subscribe_no_notify=True,
            tracking_disable=True,
        )
        new_msg = target_with_ctx.message_post(**post_kwargs)

        # Fix double-encoded HTML if present.
        if new_msg and new_msg.body:
            fixed = bf_email_imap.unwrap_double_encoded_html(new_msg.body)
            if fixed != new_msg.body:
                new_msg.write({"body": fixed})

        # Promote the bf.email row.
        promote_vals = {
            "mail_message_id": new_msg.id if new_msg else False,
            "res_model": target_model,
            "res_id": target_id,
            "record_name": (target.display_name or "")[:200],
            "source": "gateway",
        }
        if self.mark_replied and bf.direction == "in" and bf.status in ("new", "read"):
            promote_vals["status"] = "replied"
        bf.write(promote_vals)

        if self.archive_after:
            bf.write({"active": False, "status": "archived"})

        return new_msg.id if new_msg else False
