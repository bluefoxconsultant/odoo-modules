import base64
import csv
import io
import logging
import re
from xml.etree.ElementTree import Element, SubElement, tostring

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SmsArchiveThread(models.Model):
    _name = "sms.archive.thread"
    _description = "Fil de conversation SMS"
    _order = "last_message_date desc nulls last, id desc"

    phone_raw = fields.Char(
        string="Numéro original",
        help="Numéro tel que lu dans le fichier XML d'export",
    )
    phone_normalized = fields.Char(
        string="Téléphone (E.164)",
        required=True,
        index=True,
        help="Numéro normalisé utilisé comme clé de regroupement",
    )
    contact_name = fields.Char(
        string="Nom du contact",
        help="Dernier nom connu provenant du fichier XML",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact Odoo",
        help="Lien vers un contact Odoo (correspondance automatique par téléphone)",
    )
    owner_id = fields.Many2one(
        comodel_name="res.users",
        string="Propriétaire",
        required=True,
        default=lambda self: self.env.uid,
        index=True,
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
    )
    is_hidden = fields.Boolean(
        string="Confidentiel",
        default=False,
        help="Masquer ce fil des recherches et listes MCP",
    )
    message_ids = fields.One2many(
        comodel_name="sms.archive.message",
        inverse_name="thread_id",
        string="Messages",
    )
    task_ids = fields.Many2many(
        comodel_name="project.task",
        relation="sms_thread_task_rel",
        column1="thread_id",
        column2="task_id",
        string="Tâches liées",
    )
    call_ids = fields.One2many(
        comodel_name="call.archive.call",
        inverse_name="thread_id",
        string="Appels",
    )

    message_count = fields.Integer(
        string="Nombre de messages",
        compute="_compute_message_stats",
        store=True,
    )
    last_message_date = fields.Datetime(
        string="Dernier message",
        compute="_compute_message_stats",
        store=True,
    )
    last_message_preview = fields.Char(
        string="Aperçu",
        compute="_compute_message_stats",
        store=True,
    )

    call_count = fields.Integer(
        string="Nombre d'appels",
        compute="_compute_call_stats",
        store=True,
    )
    last_call_date = fields.Datetime(
        string="Dernier appel",
        compute="_compute_call_stats",
        store=True,
    )

    display_name = fields.Char(
        compute="_compute_display_name",
    )

    _sql_constraints = [
        (
            "phone_owner_uniq",
            "UNIQUE(phone_normalized, owner_id)",
            "Un fil existe déjà pour ce numéro et ce propriétaire.",
        ),
    ]

    @api.depends("message_ids", "message_ids.date_sent", "message_ids.body")
    def _compute_message_stats(self):
        for thread in self:
            messages = thread.message_ids.sorted("date_sent", reverse=True)
            thread.message_count = len(messages)
            if messages:
                thread.last_message_date = messages[0].date_sent
                preview = (messages[0].body or "")[:100]
                thread.last_message_preview = preview
            else:
                thread.last_message_date = False
                thread.last_message_preview = False

    @api.depends("call_ids", "call_ids.date")
    def _compute_call_stats(self):
        for thread in self:
            calls = thread.call_ids.sorted("date", reverse=True)
            thread.call_count = len(calls)
            thread.last_call_date = calls[0].date if calls else False

    @api.depends("contact_name", "partner_id", "phone_normalized")
    def _compute_display_name(self):
        for thread in self:
            name = thread.contact_name or (
                thread.partner_id.name if thread.partner_id else False
            )
            if name:
                thread.display_name = f"{name} ({thread.phone_normalized})"
            else:
                thread.display_name = thread.phone_normalized or "?"

    def write(self, vals):
        """Auto-update contact_name when partner_id is set."""
        res = super().write(vals)
        if "partner_id" in vals and vals["partner_id"]:
            for thread in self:
                if thread.partner_id and thread.partner_id.name:
                    super(SmsArchiveThread, thread).write(
                        {"contact_name": thread.partner_id.name}
                    )
        return res

    def action_view_messages(self):
        """Open messages for this thread."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Messages — {self.display_name}",
            "res_model": "sms.archive.message",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("thread_id", "=", self.id)],
            "context": {"default_thread_id": self.id},
        }

    def action_view_calls(self):
        """Open calls for this thread."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Appels — {self.display_name}",
            "res_model": "call.archive.call",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("thread_id", "=", self.id)],
            "context": {"default_thread_id": self.id},
        }

    def action_match_partner(self):
        """Try to match this thread's phone number to an Odoo contact."""
        self.ensure_one()
        phone = self.phone_normalized
        if not phone:
            return
        partner = self.env["res.partner"].search(
            ["|", ("phone", "ilike", phone[-10:]), ("mobile", "ilike", phone[-10:])],
            limit=1,
        )
        if partner:
            self.partner_id = partner

    # ── Exports ────────────────────────────────────────────────

    def action_export_csv(self):
        """Export conversation as CSV and download."""
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Direction", "Contact", "Contenu", "MMS"])
        for msg in self.message_ids.sorted("date_sent"):
            writer.writerow([
                str(msg.date_sent) if msg.date_sent else "",
                msg.direction,
                msg.contact_name or "",
                msg.body or "",
                "Oui" if msg.is_mms else "Non",
            ])
        data = base64.b64encode(output.getvalue().encode("utf-8-sig"))
        filename = f"sms_{self.phone_normalized}_{fields.Date.today()}.csv"
        att = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": data,
            "mimetype": "text/csv",
            "res_model": "sms.archive.thread",
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "new",
        }

    def action_export_xml(self):
        """Export conversation as SMS Backup & Restore compatible XML."""
        self.ensure_one()
        messages = self.message_ids.sorted("date_sent")
        direction_map = {"in": "1", "out": "2", "draft": "3"}

        root = Element("smses", count=str(len(messages)), type="full")
        for msg in messages:
            SubElement(root, "sms",
                       protocol="0",
                       address=self.phone_raw or self.phone_normalized,
                       date=msg.date_sent_ms or str(int(msg.date_sent.timestamp() * 1000)),
                       type=direction_map.get(msg.direction, "1"),
                       body=msg.body or "",
                       contact_name=msg.contact_name or self.contact_name or "",
                       readable_date=str(msg.date_sent) if msg.date_sent else "")

        xml_bytes = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
        xml_bytes += tostring(root, encoding="unicode").encode("utf-8")
        data = base64.b64encode(xml_bytes)
        filename = f"sms_{self.phone_normalized}_{fields.Date.today()}.xml"
        att = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": data,
            "mimetype": "application/xml",
            "res_model": "sms.archive.thread",
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "new",
        }

    def action_print_pdf(self):
        """Print the conversation as a branded PDF."""
        self.ensure_one()
        return self.env.ref(
            "bf_sms_archive.action_report_sms_thread"
        ).report_action(self)

    # MIME types that wkhtmltopdf (Qt WebKit) can render inline
    _PDF_RENDERABLE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif"}

    # wkhtmltopdf 0.12.6 cannot render supplementary plane Unicode (U+10000+).
    # Map common emoji to their closest BMP equivalents.
    _EMOJI_BMP_MAP = {
        "\U0001F642": "\u263A",  # 🙂 → ☺
        "\U0001F600": "\u263A",  # 😀 → ☺
        "\U0001F601": "\u263A",  # 😁 → ☺
        "\U0001F603": "\u263A",  # 😃 → ☺
        "\U0001F604": "\u263A",  # 😄 → ☺
        "\U0001F60A": "\u263A",  # 😊 → ☺
        "\U0001F60E": "\u263A",  # 😎 → ☺
        "\U0001F609": "\u263A",  # 😉 → ☺
        "\U0001F60D": "\u2665",  # 😍 → ♥
        "\U0001F622": "\u2639",  # 😢 → ☹
        "\U0001F62D": "\u2639",  # 😭 → ☹
        "\U0001F621": "\u2639",  # 😡 → ☹
        "\U0001F614": "\u2639",  # 😔 → ☹
        "\U0001F44D": "\u2713",  # 👍 → ✓
        "\U0001F44E": "\u2717",  # 👎 → ✗
        "\U0001F525": "\u2605",  # 🔥 → ★
        "\U0001F4AA": "\u2605",  # 💪 → ★
        "\U0001F389": "\u2605",  # 🎉 → ★
        "\U0001F44B": "\u263A",  # 👋 → ☺
        "\U0001F64F": "\u263A",  # 🙏 → ☺
    }

    # BMP emoji characters used as replacements
    _BMP_EMOJI = set("\u263A\u2639\u2665\u2605\u2713\u2717\u2726")

    @staticmethod
    def _sanitize_body_for_pdf(text):
        """Replace supplementary plane emoji with BMP equivalents for wkhtmltopdf.

        Also strips trailing lines that contain only emoji (e.g. a lone ☺ on the last line).
        """
        if not text:
            return text
        result = []
        for ch in text:
            if ord(ch) > 0xFFFF:
                mapped = SmsArchiveThread._EMOJI_BMP_MAP.get(ch)
                if mapped:
                    result.append(mapped)
                # else: silently drop (same as wkhtmltopdf would do)
            else:
                result.append(ch)
        sanitized = "".join(result).rstrip()
        # Strip trailing lines that are only emoji (e.g. "\nsome text\n☺" → "\nsome text")
        lines = sanitized.split("\n")
        while lines and all(
            ch in SmsArchiveThread._BMP_EMOJI or ch == " "
            for ch in lines[-1]
        ):
            lines.pop()
        return "\n".join(lines)

    @staticmethod
    def _convert_image_for_pdf(datas_b64, content_type):
        """Convert HEIC/WEBP image to JPEG data URI for wkhtmltopdf.

        Returns a data:image/jpeg;base64,... string, or empty string on failure.
        """
        try:
            # Register HEIC opener if available
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                if "heic" in content_type:
                    return ""

            from PIL import Image
            Image.MAX_IMAGE_PIXELS = 25_000_000
            raw = base64.b64decode(datas_b64)
            try:
                img = Image.open(io.BytesIO(raw))
            except Image.DecompressionBombError:
                _logger.warning("Decompression bomb detected for %s image", content_type)
                return ""
            # Resize if very large (max 800px wide for PDF)
            if img.width > 800:
                ratio = 800 / img.width
                img = img.resize((800, int(img.height * ratio)), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            jpeg_b64 = base64.b64encode(buf.getvalue()).decode()
            return f"data:image/jpeg;base64,{jpeg_b64}"
        except Exception:
            _logger.warning("Failed to convert %s image for PDF", content_type, exc_info=True)
            return ""

    @staticmethod
    def _get_emoji_font_data_uri():
        """Return NotoEmoji font as base64 data URI for embedding in CSS."""
        import os
        font_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "fonts", "NotoEmoji-Regular.ttf",
        )
        try:
            with open(font_path, "rb") as f:
                import base64 as b64mod
                return "data:font/truetype;base64," + b64mod.b64encode(f.read()).decode()
        except FileNotFoundError:
            _logger.warning("NotoEmoji-Regular.ttf not found at %s", font_path)
            return ""

    @staticmethod
    def _build_report_css(brand_primary, brand_dark):
        """Return report CSS with interpolated brand colours as ``Markup``."""
        from markupsafe import Markup
        # Escape values (hex colours are safe, but be defensive)
        p = Markup.escape(brand_primary)
        d = Markup.escape(brand_dark)
        return Markup(
            f".sms-page {{"
            f"  font-family: 'Lexend', 'NotoEmoji', 'Noto Color Emoji', system-ui, sans-serif;"
            f"  font-size: 9pt; color: #333;"
            f"}}"
            f".sms-banner {{"
            f"  background: {d}; padding: 18pt 24pt 16pt 24pt;"
            f"  display: table; width: 100%;"
            f"}}"
            f".sms-banner-logo {{"
            f"  display: table-cell; vertical-align: middle; width: 90pt;"
            f"}}"
            f".sms-banner-logo img {{ max-width: 80pt; max-height: 40pt; }}"
            f".sms-banner-content {{"
            f"  display: table-cell; vertical-align: middle;"
            f"}}"
            f".sms-banner .doc-type {{"
            f"  font-size: 8pt; font-weight: 600; text-transform: uppercase;"
            f"  letter-spacing: 1pt; color: {p}; margin-bottom: 3pt;"
            f"}}"
            f".sms-banner h1 {{"
            f"  font-size: 16pt; font-weight: 600; color: #ffffff;"
            f"  margin: 0; line-height: 1.2;"
            f"}}"
            f".sms-banner .doc-subtitle {{"
            f"  font-size: 9pt; color: rgba(255,255,255,0.7); margin-top: 3pt;"
            f"}}"
            f".sms-accent-bar {{"
            f"  height: 3px; background: {p}; margin: 0; width: 100%;"
            f"}}"
            f".sms-meta {{"
            f"  background: #f8f9fb; padding: 8pt 24pt; display: table;"
            f"  width: 100%; font-size: 8pt; color: #666;"
            f"  border-bottom: 1px solid #e8e8e8;"
            f"}}"
            f".sms-meta-item {{ display: table-cell; padding-right: 24pt; }}"
            f".sms-meta-label {{"
            f"  font-weight: 600; color: #999; text-transform: uppercase;"
            f"  font-size: 7pt; letter-spacing: 0.5pt;"
            f"}}"
            f".sms-meta-value {{ color: #333; font-size: 9pt; }}"
            f".sms-messages {{ padding: 8pt 24pt; }}"
            f".sms-row {{ margin-bottom: 2pt; overflow: hidden; }}"
            f".sms-row-left {{ text-align: left; }}"
            f".sms-row-right {{ text-align: right; }}"
            f".sms-bubble {{"
            f"  display: inline-block; max-width: 85%; text-align: left;"
            f"  padding: 5pt 10pt; border-radius: 8pt; font-size: 9pt;"
            f"  line-height: 1.35; word-wrap: break-word; white-space: pre-line;"
            f"  font-family: 'Lexend', 'NotoEmoji', 'Noto Color Emoji', system-ui, sans-serif;"
            f"}}"
            f".sms-bubble-in {{ background: #f0f0f0; color: #333; }}"
            f".sms-bubble-out {{ background: {p}; color: #ffffff; }}"
            f".sms-bubble-draft {{"
            f"  background: #fef3cd; color: #664d03; border: 1px dashed #ccc;"
            f"}}"
            f".sms-ts {{ font-size: 7pt; color: #999; margin-top: 2pt; white-space: nowrap; }}"
            f".sms-bubble-out .sms-ts {{ color: rgba(255,255,255,0.65); }}"
            f".sms-img {{"
            f"  max-width: 100%; max-height: 200pt; border-radius: 4pt;"
            f"  margin-top: 4pt; display: block;"
            f"}}"
            f".sms-img-placeholder {{"
            f"  font-size: 7pt; color: #999; font-style: italic; margin-top: 4pt;"
            f"}}"
            f".sms-bubble-out .sms-img-placeholder {{ color: rgba(255,255,255,0.6); }}"
            f".sms-date-sep {{"
            f"  text-align: center; font-size: 7pt; font-weight: 600; color: #999;"
            f"  text-transform: uppercase; letter-spacing: 0.5pt; margin: 6pt 0 4pt 0;"
            f"}}"
            f".sms-footer {{"
            f"  font-size: 7pt; color: #999; text-align: center;"
            f"  border-top: 1px solid #ddd; padding-top: 4pt; margin-top: 8pt;"
            f"}}"
        )

    def _get_report_data(self):
        """Prepare data for the PDF report."""
        from odoo.tools.image import image_data_uri

        messages = self.message_ids.sorted("date_sent")

        # Sanitize bodies for PDF (emoji → BMP equivalents)
        msg_bodies = {}
        for msg in messages:
            msg_bodies[msg.id] = self._sanitize_body_for_pdf(msg.body)

        # Pre-build image data for MMS parts
        msg_images = {}
        for msg in messages:
            if msg.is_mms and msg.mms_part_ids:
                images = []
                for part in msg.mms_part_ids:
                    if part.is_image and part.attachment_id and part.attachment_id.datas:
                        ct = (part.content_type or "").lower()
                        if ct in self._PDF_RENDERABLE_TYPES:
                            images.append({
                                "data_uri": image_data_uri(part.attachment_id.datas),
                                "filename": part.filename or "image",
                                "content_type": ct,
                                "renderable": True,
                            })
                        else:
                            # Try to convert HEIC/WEBP to JPEG via Pillow
                            converted = self._convert_image_for_pdf(
                                part.attachment_id.datas, ct,
                            )
                            if converted:
                                images.append({
                                    "data_uri": converted,
                                    "filename": part.filename or "image",
                                    "content_type": "image/jpeg",
                                    "renderable": True,
                                })
                            else:
                                images.append({
                                    "data_uri": "",
                                    "filename": part.filename or "image",
                                    "content_type": ct,
                                    "renderable": False,
                                })
                if images:
                    msg_images[msg.id] = images

        # Brand colours: read from company if bf_lexend installed, else defaults
        company = self.env.company
        brand_primary = getattr(company, 'report_brand_primary', None) or '#714B67'
        brand_dark = getattr(company, 'report_brand_dark', None) or '#212529'

        # Check if bf_lexend is installed (for conditional Lexend CSS link)
        has_lexend = bool(
            self.env['ir.module.module'].sudo().search(
                [('name', '=', 'bf_lexend'), ('state', '=', 'installed')],
                limit=1,
            )
        )

        # Company logo and name
        company_logo = ""
        if company.logo:
            company_logo = image_data_uri(company.logo)
        company_name = company.name or ""

        return {
            "thread": self,
            "messages": messages,
            "msg_bodies": msg_bodies,
            "msg_images": msg_images,
            "emoji_font_uri": self._get_emoji_font_data_uri(),
            "contact": self.contact_name or self.phone_normalized,
            "phone": self.phone_normalized,
            "count": len(messages),
            "report_css": self._build_report_css(brand_primary, brand_dark),
            "has_lexend": has_lexend,
            "company_name": company_name,
            "company_logo": company_logo,
        }

    @staticmethod
    def normalize_phone(raw):
        """Normalize a phone number to E.164-ish format."""
        digits = re.sub(r"[^\d+]", "", raw or "")
        if digits.startswith("+"):
            return digits
        digits = re.sub(r"\D", "", digits)
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return f"+{digits}" if digits else ""
