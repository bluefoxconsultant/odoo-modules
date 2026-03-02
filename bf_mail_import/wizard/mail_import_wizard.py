import base64
import email
import email.policy
import logging
from email.utils import parseaddr

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailImportWizard(models.TransientModel):
    _name = "bf.mail.import.wizard"
    _description = "Assistant d'import de courriels .eml"

    res_model = fields.Char("Mod\u00e8le", readonly=True)
    res_id = fields.Integer("ID enregistrement", readonly=True)
    record_display = fields.Char(
        "Enregistrement cible", compute="_compute_record_display"
    )
    eml_files = fields.Many2many(
        "ir.attachment",
        string="Fichiers .eml",
        help="S\u00e9lectionnez un ou plusieurs fichiers .eml \u00e0 importer.",
    )
    file_count = fields.Integer("Nombre de fichiers", compute="_compute_file_count")
    import_result = fields.Text("R\u00e9sultat", readonly=True)
    state = fields.Selection(
        [("draft", "Brouillon"), ("done", "Termin\u00e9")],
        default="draft",
    )

    @api.depends("res_model", "res_id")
    def _compute_record_display(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                try:
                    target = self.env[rec.res_model].browse(rec.res_id)
                    if target.exists():
                        rec.record_display = target.display_name
                        continue
                except Exception:
                    pass
            rec.record_display = False

    @api.depends("eml_files")
    def _compute_file_count(self):
        for rec in self:
            rec.file_count = len(rec.eml_files)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        res_model = ctx.get("active_model")
        res_id = ctx.get("active_id")
        if res_model:
            if res_model not in self.env:
                raise UserError(
                    _("Le mod\u00e8le '%s' n'existe pas.", res_model)
                )
            if not hasattr(self.env[res_model], "message_post"):
                raise UserError(
                    _(
                        "Le mod\u00e8le '%s' ne supporte pas le chatter "
                        "(mail.thread).",
                        res_model,
                    )
                )
            res["res_model"] = res_model
        if res_id:
            res["res_id"] = res_id
        return res

    def _parse_eml(self, raw_bytes):
        """Parse raw .eml bytes via Odoo's message_parse."""
        email_msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
        return self.env["mail.thread"].message_parse(email_msg, save_original=False)

    def _get_target(self):
        """Return the target record, validated."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_("Aucun enregistrement cible d\u00e9fini."))
        target = self.env[self.res_model].browse(self.res_id)
        if not target.exists():
            raise UserError(
                _("L'enregistrement cible a \u00e9t\u00e9 supprim\u00e9.")
            )
        return target

    def action_import(self):
        self.ensure_one()
        target = self._get_target()
        if not self.eml_files:
            raise UserError(
                _("Veuillez s\u00e9lectionner au moins un fichier .eml.")
            )

        imported = 0
        skipped = 0
        errors = []

        for att in self.eml_files:
            try:
                raw = base64.b64decode(att.datas)
                msg_dict = self._parse_eml(raw)

                # Duplicate check via message_id
                message_id = msg_dict.get("message_id")
                if message_id:
                    existing = self.env["mail.message"].search(
                        [("message_id", "=", message_id)], limit=1
                    )
                    if existing:
                        skipped += 1
                        continue

                # Resolve author
                author_id = False
                partner_ids = msg_dict.get("partner_ids", [])
                email_from = msg_dict.get("email_from", "")
                if email_from:
                    # Extract bare email from "Name <email>" format
                    _name, bare_email = parseaddr(email_from)
                    author = self.env["res.partner"].search(
                        [("email", "=ilike", bare_email or email_from)],
                        limit=1,
                    )
                    if not author and partner_ids:
                        author = self.env["res.partner"].browse(
                            partner_ids[:1]
                        ).exists()
                    if author:
                        author_id = author.id

                # Prepare attachments as (name, raw_content) tuples
                post_attachments = list(msg_dict.get("attachments", []))

                # Build kwargs for message_post
                post_kwargs = {
                    "body": Markup(msg_dict.get("body", "")),
                    "subject": msg_dict.get("subject", ""),
                    "message_type": "email",
                    "email_from": email_from,
                    "author_id": author_id,
                    "parent_id": msg_dict.get("parent_id", False),
                    "subtype_xmlid": "mail.mt_comment",
                    "attachments": post_attachments,
                }
                # Pass message_id and date as kwargs — they map to
                # mail.message columns via message_post's **kwargs
                if message_id:
                    post_kwargs["message_id"] = message_id
                date = msg_dict.get("date")
                if date:
                    post_kwargs["date"] = date

                target.with_context(
                    mail_create_nosubscribe=True,
                    mail_create_nolog=True,
                    mail_notify_force_send=False,
                    mail_auto_subscribe_no_notify=True,
                    tracking_disable=True,
                ).message_post(**post_kwargs)

                imported += 1

            except Exception as e:
                _logger.exception("Error importing %s", att.name)
                errors.append(f"{att.name} : {e}")

        _logger.info(
            "EML import on %s,%s: %d imported, %d skipped, %d errors",
            self.res_model, self.res_id, imported, skipped, len(errors),
        )

        # Build result summary
        parts = []
        if imported:
            parts.append(_("%d courriel(s) import\u00e9(s).", imported))
        if skipped:
            parts.append(_("%d doublon(s) ignor\u00e9(s).", skipped))
        if errors:
            parts.append(_("Erreurs :"))
            parts.extend(errors)

        self.import_result = "\n".join(str(p) for p in parts)
        self.state = "done"
        return self._reopen()

    def action_reset(self):
        self.ensure_one()
        self.write({
            "state": "draft",
            "import_result": False,
            "eml_files": [(5, 0, 0)],
        })
        return self._reopen()

    def _reopen(self):
        """Return action to reopen the wizard on the same record."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "views": [[False, "form"]],
            "target": "new",
        }
