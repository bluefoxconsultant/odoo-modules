import hashlib
import logging
import re
from datetime import datetime, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _ms_to_naive_utc(date_ms):
    """Convert millisecond epoch (int/str) to naive UTC datetime (Odoo convention)."""
    ms = int(date_ms)
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)

# SMS Backup & Restore type mapping
_SMS_TYPE_MAP = {
    "1": "in",     # Received
    "2": "out",    # Sent
    "3": "draft",  # Draft
}

_DIRECTION_LABELS = {
    "in": "←",
    "out": "→",
    "draft": "~",
}


class SmsArchiveMessage(models.Model):
    _name = "sms.archive.message"
    _description = "Message SMS archivé"
    _order = "date_sent asc, id asc"

    thread_id = fields.Many2one(
        comodel_name="sms.archive.thread",
        string="Conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    message_hash = fields.Char(
        string="Hash de dédoublonnage",
        size=64,
        required=True,
        index=True,
    )
    direction = fields.Selection(
        selection=[
            ("in", "Reçu"),
            ("out", "Envoyé"),
            ("draft", "Brouillon"),
        ],
        string="Direction",
        required=True,
    )
    body = fields.Text(
        string="Contenu",
    )
    date_sent = fields.Datetime(
        string="Date",
        required=True,
        index=True,
    )
    date_sent_ms = fields.Char(
        string="Timestamp (ms)",
        help="Timestamp brut en millisecondes conservé du XML",
    )
    is_mms = fields.Boolean(
        string="MMS",
        default=False,
    )
    is_read = fields.Boolean(
        string="Lu",
        default=True,
        help="Faux pour un message entrant live non encore consulté (compteur systray).",
    )
    delivery_state = fields.Selection(
        selection=[
            ("queued", "En file"),
            ("sent", "Envoyé"),
            ("failed", "Échec"),
            ("received", "Reçu"),
        ],
        string="État de livraison",
        help="Pour les messages sortants live. « sent » = accepté par l'API VOIP.ms "
             "(VOIP.ms ne fournit pas d'accusé de livraison fiable).",
    )
    voipms_id = fields.Char(
        string="ID VOIP.ms",
        index=True,
        copy=False,
        help="Identifiant du message côté VOIP.ms (déduplication live).",
    )
    line_id = fields.Many2one(
        comodel_name="sms.archive.line",
        string="Ligne",
        ondelete="set null",
        help="Ligne (DID) VOIP.ms utilisée pour ce message live.",
    )
    error = fields.Text(
        string="Erreur d'envoi",
    )
    contact_name = fields.Char(
        string="Nom du contact",
    )
    owner_id = fields.Many2one(
        related="thread_id.owner_id",
        store=True,
        index=True,
        string="Propriétaire",
    )
    import_batch_id = fields.Char(
        string="Lot d'import",
        help="Identifiant backup_set du fichier XML",
    )
    mms_part_ids = fields.One2many(
        comodel_name="sms.archive.mms.part",
        inverse_name="message_id",
        string="Pièces jointes MMS",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
    )

    _sql_constraints = [
        (
            "hash_uniq",
            "UNIQUE(message_hash)",
            "Ce message existe déjà (hash dupliqué).",
        ),
    ]

    @api.depends("direction", "thread_id.contact_name", "date_sent", "body")
    def _compute_display_name(self):
        for msg in self:
            arrow = _DIRECTION_LABELS.get(msg.direction, "?")
            contact = msg.thread_id.contact_name or msg.thread_id.phone_normalized or "?"
            dt = str(msg.date_sent)[:16] if msg.date_sent else ""
            preview = (msg.body or "")[:40]
            if len(msg.body or "") > 40:
                preview += "…"
            msg.display_name = f"{arrow} {contact} — {dt} — {preview}"

    def action_post_to_task(self):
        """Open wizard to post the selected SMS message(s) to a project task."""
        if not self:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Poster sur une tâche",
            "res_model": "sms.archive.post.to.task.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_message_ids": [(6, 0, self.ids)],
            },
        }

    def action_export_csv(self):
        """Export the selected messages as a single CSV file."""
        if not self:
            return False
        filename = f"sms_selection_{fields.Date.today()}.csv"
        res_id = self.thread_id.id if len(self.thread_id) == 1 else False
        return self.env["sms.archive.thread"]._build_csv_download(
            self, filename=filename, res_id=res_id,
        )

    def action_export_xml(self):
        """Export the selected messages as a single SMS Backup & Restore XML file."""
        if not self:
            return False
        filename = f"sms_selection_{fields.Date.today()}.xml"
        res_id = self.thread_id.id if len(self.thread_id) == 1 else False
        return self.env["sms.archive.thread"]._build_xml_download(
            self, filename=filename, res_id=res_id,
        )

    def action_export_pdf(self):
        """Print the selected messages as a branded PDF."""
        if not self:
            return False
        return self.env.ref(
            "bf_sms_archive.action_report_sms_messages"
        ).report_action(self)

    def _get_messages_report_data(self):
        """Prepare data for the per-message PDF report (binding_model: sms.archive.message)."""
        Thread = self.env["sms.archive.thread"]
        data = Thread._build_shared_report_data()

        threads = self.thread_id.sorted(
            lambda t: (t.last_message_date or fields.Datetime.from_string("1970-01-01")),
            reverse=True,
        )
        groups = []
        for thread in threads:
            thread_msgs = self.filtered(lambda m, t=thread: m.thread_id.id == t.id)
            if thread_msgs:
                groups.append(Thread._build_thread_group(thread, thread_msgs))

        data["groups"] = groups
        data["total_count"] = sum(g["count"] for g in groups)
        data["thread_count"] = len(groups)
        return data

    @api.model
    def _ingest_one(self, *, phone_raw, owner_id, direction, body, date_ms,
                    contact_name=None, is_mms=False, parts=None, batch_id=None,
                    voipms_id=None, delivery_state=None, line_id=None, is_read=None):
        """Single-message ingestion with dedup. Returns (record, created: bool).

        ``parts`` is an optional list of {content_type, filename, data_b64, text}
        forwarded to ``sms.archive.mms.part._ingest_parts`` after the message is created.

        Live-specific optional kwargs (webhook / poller): ``voipms_id`` (preferred
        dedup key when present), ``delivery_state``, ``line_id`` and ``is_read``.
        """
        Thread = self.env["sms.archive.thread"].sudo()
        phone_norm = Thread.normalize_phone(phone_raw)
        body_text = body or ""

        # Préférer l'id VOIP.ms (stable) pour la déduplication quand disponible.
        if voipms_id:
            existing = self.sudo().search([("voipms_id", "=", str(voipms_id))], limit=1)
            if existing:
                return existing, False

        msg_hash = hashlib.sha256(
            f"{phone_norm}|{date_ms}|{body_text}".encode("utf-8")
        ).hexdigest()

        existing = self.sudo().search([("message_hash", "=", msg_hash)], limit=1)
        if existing:
            if voipms_id and not existing.voipms_id:
                existing.sudo().write({"voipms_id": str(voipms_id)})
            return existing, False

        thread = Thread._get_or_create(phone_norm, owner_id, phone_raw, contact_name)
        vals = {
            "thread_id": thread.id,
            "message_hash": msg_hash,
            "direction": direction,
            "body": body_text,
            "date_sent": _ms_to_naive_utc(date_ms),
            "date_sent_ms": str(date_ms),
            "is_mms": bool(is_mms),
            "contact_name": contact_name or "",
            "import_batch_id": batch_id or "android-live",
        }
        if voipms_id:
            vals["voipms_id"] = str(voipms_id)
        if delivery_state:
            vals["delivery_state"] = delivery_state
        if line_id:
            vals["line_id"] = line_id
        if is_read is not None:
            vals["is_read"] = is_read
        rec = self.sudo().create(vals)
        if parts:
            self.env["sms.archive.mms.part"].sudo()._ingest_parts(rec.id, parts)
        return rec, True

    # ── Envoi live (SMS/MMS via VOIP.ms) ───────────────────────────

    _SMS_SEGMENT_LEN = 160

    @staticmethod
    def _split_segments(text, size=160):
        """Découpe un corps en segments ≤ ``size`` (limite VOIP.ms)."""
        text = text or ""
        if not text:
            return [""]
        return [text[i:i + size] for i in range(0, len(text), size)]

    @staticmethod
    def _to_voipms_dst(e164):
        """Numéro destinataire au format VOIP.ms (chiffres, NANP → 10)."""
        digits = re.sub(r"\D", "", e164 or "")
        if len(digits) == 11 and digits.startswith("1"):
            return digits[1:]
        return digits

    @staticmethod
    def _media_to_datauri(media):
        """{content_type, data_b64} → data URI base64 pour sendMMS."""
        ct = media.get("content_type") or "application/octet-stream"
        return f"data:{ct};base64,{media.get('data_b64') or ''}"

    @api.model
    def action_send(self, line_id, dst, body, media=None):
        """Envoie un SMS/MMS depuis ``line_id`` vers ``dst``.

        ``media`` : liste optionnelle de {filename, content_type, data_b64} → MMS.
        Crée un message sortant (avec son état de livraison) et retourne son id.
        """
        Line = self.env["sms.archive.line"].sudo()
        line = Line.browse(int(line_id))
        if not line.exists():
            raise UserError("Ligne d'envoi introuvable.")
        if line.owner_id.id != self.env.uid and not self.env.user.has_group(
            "bf_sms_archive.group_sms_manager"
        ):
            raise UserError("Cette ligne ne vous appartient pas.")

        Thread = self.env["sms.archive.thread"].sudo()
        Voipms = self.env["sms.archive.voipms"]
        dst_norm = Thread.normalize_phone(dst)
        if not dst_norm:
            raise UserError("Numéro destinataire invalide.")
        thread = Thread._get_or_create(dst_norm, line.owner_id.id, dst, None)

        now = fields.Datetime.now()
        date_ms = int(now.replace(tzinfo=timezone.utc).timestamp() * 1000)
        did = Line._voipms_did_value(line.did)
        dst_api = self._to_voipms_dst(dst_norm)
        is_mms = bool(media)

        delivery_state = "sent"
        error = False
        voipms_id = ""
        try:
            if is_mms:
                if not line.mms_enabled:
                    raise UserError("Ligne non activée pour les MMS.")
                medias = [self._media_to_datauri(m) for m in media][:3]
                voipms_id = Voipms._voipms_send_mms(did, dst_api, body or "", medias)
            else:
                if not line.sms_enabled:
                    raise UserError("Ligne non activée pour les SMS.")
                ids = []
                for seg in self._split_segments(body or ""):
                    ids.append(Voipms._voipms_send_sms(did, dst_api, seg))
                voipms_id = ",".join(x for x in ids if x)
        except Exception as e:  # noqa: BLE001 — on journalise l'état, on ne casse pas l'UI
            delivery_state = "failed"
            error = Voipms._voipms_redact(str(e))
            _logger.warning(
                "Envoi SMS/MMS échoué (ligne=%s dst=%s) : %s", line.id, dst_norm, error,
            )

        msg_hash = hashlib.sha256(
            f"{dst_norm}|{date_ms}|{body or ''}|out|{voipms_id}".encode("utf-8")
        ).hexdigest()
        rec = self.sudo().create({
            "thread_id": thread.id,
            "message_hash": msg_hash,
            "direction": "out",
            "body": body or "",
            "date_sent": now,
            "date_sent_ms": str(date_ms),
            "is_mms": is_mms,
            "is_read": True,
            "line_id": line.id,
            "voipms_id": voipms_id or False,
            "delivery_state": delivery_state,
            "error": error or False,
            "import_batch_id": "voipms-live",
        })
        if is_mms and media:
            parts = [{
                "content_type": m.get("content_type"),
                "filename": m.get("filename"),
                "data_b64": m.get("data_b64"),
            } for m in media]
            self.env["sms.archive.mms.part"].sudo()._ingest_parts(rec.id, parts)
        rec._notify_bus(kind="out")
        return rec.id

    def _messenger_dict(self):
        """Sérialisation d'un message pour la SPA « Messagerie »."""
        self.ensure_one()
        media = []
        if self.is_mms:
            for part in self.mms_part_ids:
                if part.attachment_id:
                    att = part.attachment_id
                    media.append({
                        "filename": part.filename or "fichier",
                        "content_type": part.content_type or "",
                        "is_image": part.is_image,
                        "url": (
                            "/web/image/%d" % att.id if part.is_image
                            else "/web/content/%d?download=true" % att.id
                        ),
                    })
                elif part.text_content:
                    media.append({
                        "filename": part.filename or "texte",
                        "content_type": part.content_type or "text/plain",
                        "is_image": False,
                        "text": part.text_content,
                    })
        return {
            "id": self.id,
            "direction": self.direction,
            "body": self.body or "",
            "date_ms": int(self.date_sent_ms) if (self.date_sent_ms or "").isdigit()
            else self.thread_id._dt_to_ms(self.date_sent),
            "is_mms": self.is_mms,
            "delivery_state": self.delivery_state or "",
            "error": self.error or "",
            "media": media,
        }

    def _notify_bus(self, kind="new"):
        """Pousse une notification temps réel au propriétaire (systray + SPA).

        Cible le canal du *partenaire* propriétaire (ACL par utilisateur côté bus),
        jamais un canal-chaîne devinable : aucune fuite inter-utilisateurs.
        """
        for msg in self:
            owner = msg.owner_id or msg.thread_id.owner_id
            if not owner or not owner.partner_id:
                continue
            thread = msg.thread_id
            payload = {
                "kind": kind,  # "new" (entrant) | "out" (sortant)
                "thread_id": thread.id,
                "message_id": msg.id,
                "direction": msg.direction,
                "delivery_state": msg.delivery_state or "",
                "contact": thread.contact_name or thread.phone_normalized or "",
                "preview": (msg.body or "")[:120],
                "date_ms": msg.date_sent_ms or "",
            }
            self.env["bus.bus"]._sendone(
                owner.partner_id, "sms.archive/new", payload,
            )
