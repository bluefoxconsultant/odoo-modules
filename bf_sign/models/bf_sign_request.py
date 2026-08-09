import base64
import binascii
import hashlib
import io
import logging
import os
import re
from datetime import timedelta, timezone

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf

from .bf_sign_field import VALUE_TYPES

_logger = logging.getLogger(__name__)

CERTIFICATE_REPORT = "bf_sign.action_report_sign_certificate"

# Magic header of a PNG file — the only image format the signing canvas produces.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Deliberately permissive: this guards against typos on the signing page, it is
# not an address-validity oracle.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Whitespace a signer may paste inside a number (thin, non-breaking, regular).
_NUM_SPACES = (" ", " ", " ", " ")


class BfSignRequest(models.Model):
    """A request to electronically sign a PDF (simple electronic signature).

    Supports multiple signers (parallel or sequential) and visually placed
    signature pads (``bf.sign.field``). When the last signer signs, the placed
    pads are stamped onto the document, a completion certificate is sealed to
    it, SHA-256 imprints are computed, the audit trail is chained, and an
    optional RFC 3161 trusted timestamp is obtained.
    """

    _name = "bf.sign.request"
    _description = "Demande de signature électronique"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Référence", required=True, copy=False, readonly=True,
        default=lambda self: _("Nouvelle"), index=True,
    )
    title = fields.Char(
        string="Titre", copy=False, tracking=True,
        help="Nom convivial pour repérer le document dans la liste. "
             "La référence unique (séquence) reste inchangée.",
    )

    @api.depends("name", "title")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                "%s (%s)" % (rec.title, rec.name) if rec.title else (rec.name or "")
            )

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("sent", "Envoyée"),
            ("in_progress", "En cours"),
            ("signed", "Signée"),
            ("refused", "Refusée"),
            ("expired", "Expirée"),
            ("cancelled", "Annulée"),
        ],
        string="État", default="draft", required=True, tracking=True, copy=False,
    )
    signature_method = fields.Selection(
        selection=[
            ("native_ses", "Native — signature simple (SES)"),
        ],
        string="Méthode de signature", default="native_ses", required=True,
        help="Le module produit une signature électronique simple (SES). "
             "Un palier avancé (AES) ajouterait une valeur ici ; tant qu'il "
             "n'est pas implémenté, la sélection n'en offre pas.",
    )
    signing_order = fields.Selection(
        selection=[("parallel", "En parallèle"), ("sequential", "Séquentiel")],
        string="Ordre de signature", default="parallel", required=True,
        help="Parallèle : tous les signataires reçoivent le lien en même temps. "
             "Séquentiel : chaque signataire est invité à son tour, dans l'ordre.",
    )

    # ── Document ────────────────────────────────────────────────────────────
    document_file = fields.Binary(string="Document (PDF)", attachment=True, copy=False)
    document_filename = fields.Char(string="Nom du fichier")
    signed_attachment_id = fields.Many2one(
        "ir.attachment", string="Document signé", readonly=True, copy=False)
    certificate_attachment_id = fields.Many2one(
        "ir.attachment", string="Certificat de signature", readonly=True, copy=False)

    # ── Signers & placed fields ─────────────────────────────────────────────
    signer_ids = fields.One2many("bf.sign.signer", "request_id", string="Signataires", copy=True)
    field_ids = fields.One2many("bf.sign.field", "request_id", string="Pavés de signature", copy=True)
    signer_count = fields.Integer(compute="_compute_progress")
    signed_count = fields.Integer(compute="_compute_progress")
    progress = fields.Float(compute="_compute_progress", string="Progression (%)")

    # ── Consent ─────────────────────────────────────────────────────────────
    consent_text = fields.Text(
        string="Texte de consentement",
        default=lambda self: self._default_consent_text(),
    )

    # ── Integrity / proof ───────────────────────────────────────────────────
    hash_original = fields.Char(string="Empreinte SHA-256 (original)", readonly=True, copy=False)
    hash_signed = fields.Char(string="Empreinte SHA-256 (document scellé)", readonly=True, copy=False)
    hash_stamped = fields.Char(
        string="Empreinte SHA-256 (contenu horodaté)", readonly=True, copy=False,
        help="Empreinte du document estampé (original + signatures), c.-à-d. le contenu "
             "couvert par le jeton d'horodatage RFC 3161.")
    signed_on = fields.Datetime(string="Finalisé le", readonly=True, copy=False)
    tsa_token = fields.Binary(string="Jeton d'horodatage RFC 3161", readonly=True, copy=False)
    tsa_url = fields.Char(string="Autorité d'horodatage (TSA)", readonly=True, copy=False)
    tsa_timestamp = fields.Datetime(string="Horodatage obtenu le", readonly=True, copy=False)
    tsa_gentime = fields.Datetime(
        string="Heure attestée (TSA)", readonly=True, copy=False,
        help="Heure attestée par l'autorité d'horodatage (genTime du jeton RFC 3161).")
    sealed = fields.Boolean(
        string="Scellé numériquement (PAdES)", readonly=True, copy=False,
        help="Une signature numérique a été apposée sur le document scellé.")

    # ── Lifecycle ───────────────────────────────────────────────────────────
    expiry_date = fields.Datetime(string="Échéance", copy=False)
    company_id = fields.Many2one(
        "res.company", string="Société", required=True,
        # Prefer the creator's MAIN company over the session's active company, so
        # a signature request is branded by the user's primary org even when
        # another company is selected in the multi-company switcher (the field
        # stays editable in draft if a different company is ever needed).
        default=lambda self: self.env.user.company_id)

    res_model = fields.Char(string="Modèle source")
    res_id = fields.Integer(string="ID source")

    require_signer_otp = fields.Boolean(
        string="Vérification par code (OTP)",
        default=lambda self: self._default_require_otp(), copy=False,
        help="Le signataire doit saisir un code envoyé à son courriel avant de "
             "pouvoir consulter et signer le document.")

    log_ids = fields.One2many("bf.sign.log", "request_id", string="Piste de vérification")
    log_count = fields.Integer(compute="_compute_log_count")

    # ── Defaults / computes ──────────────────────────────────────────────────
    @api.model
    def _default_require_otp(self):
        return (self.env["ir.config_parameter"].sudo().get_param(
            "bf_sign.require_signer_otp") or "") in ("1", "True", "true")

    @api.model
    def _default_consent_text(self):
        param = self.env["ir.config_parameter"].sudo().get_param("bf_sign.default_consent_text")
        return param or _(
            "Je consens à signer ce document par voie électronique et je reconnais "
            "que ma signature électronique a la même valeur qu'une signature manuscrite."
        )

    @api.depends("log_ids")
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    @api.depends("signer_ids", "signer_ids.state")
    def _compute_progress(self):
        for rec in self:
            total = len(rec.signer_ids)
            signed = len(rec.signer_ids.filtered(lambda s: s.state == "signed"))
            rec.signer_count = total
            rec.signed_count = signed
            rec.progress = (signed / total * 100.0) if total else 0.0

    # ── Creation ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nouvelle")) == _("Nouvelle"):
                vals["name"] = self.env["ir.sequence"].next_by_code("bf.sign.request") or _("Nouvelle")
        records = super().create(vals_list)
        for rec in records:
            self.env["bf.sign.log"]._append(
                rec, "created", actor=self.env.user.name, identity_method="internal_user")
        return records

    @api.model
    def create_from_record(self, record, report_ref=None, document_file=None,
                           document_filename=None, signers=None, field_template=None,
                           send=False, vals=None):
        """Create a signature request from any source record.

        Used by the ``bf.sign.mixin`` so other modules (Sales, Purchase, HR…) can
        send their document for signature.
        - ``record``: the single source recordset → linked via res_model/res_id.
        - ``report_ref``: report xmlid (or record) rendered to PDF when
          ``document_file`` is not supplied.
        - ``document_file``: base64 PDF (alternative to ``report_ref``).
        - ``signers``: list of dicts ``[{'name','email','partner_id'}, …]``.
        - ``field_template``: a ``bf.sign.field.template`` (record or id) to apply.
        - ``send``: when True, also call ``action_send()``.
        """
        record.ensure_one()
        if not document_file:
            if not report_ref:
                raise UserError(_("Aucun document ni rapport fourni pour la signature."))
            report_id = report_ref if isinstance(report_ref, str) else report_ref.report_name
            pdf_bytes, _ext = self.env["ir.actions.report"]._render_qweb_pdf(
                report_id, record.ids)
            document_file = base64.b64encode(pdf_bytes)
        create_vals = {
            "document_file": document_file,
            "document_filename": document_filename or ("%s.pdf" % (
                record.display_name or record._name).replace("/", "-")),
            "res_model": record._name,
            "res_id": record.id,
        }
        if signers:
            create_vals["signer_ids"] = [(0, 0, s) for s in signers]
        if vals:
            create_vals.update(vals)
        request = self.create(create_vals)
        if field_template:
            tmpl_id = field_template if isinstance(field_template, int) else field_template.id
            request.apply_field_template(tmpl_id)
        if send:
            request.action_send()
        return request

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _get_base_url(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            or self.get_base_url()
        )

    @staticmethod
    def _sha256_hex(data_bytes):
        return hashlib.sha256(data_bytes).hexdigest()

    # ── Input validation (defensive — public, untrusted submissions) ─────────
    def _max_signature_bytes(self):
        kb = int(self.env["ir.config_parameter"].sudo().get_param(
            "bf_sign.max_signature_kb", "5120") or 5120)
        return max(kb, 1) * 1024

    def _max_document_bytes(self):
        mb = int(self.env["ir.config_parameter"].sudo().get_param(
            "bf_sign.max_document_mb", "25") or 25)
        return max(mb, 1) * 1024 * 1024

    def _validate_signature_png(self, b64, label):
        """Validate a base64 PNG drawn pad before it is stored or stamped.

        Rejects oversize payloads, non-PNG data and corrupt images up front, so
        a bad submission fails cleanly on the signing page instead of crashing
        the finalize step (reportlab ImageReader) after the signer was already
        marked as signed. Returns the decoded bytes.
        """
        if not b64:
            raise UserError(_("La %s est requise.") % label)
        max_bytes = self._max_signature_bytes()
        # Cheap guard on the base64 string before allocating the decoded buffer.
        if len(b64) > max_bytes // 3 * 4 + 8:
            raise UserError(_("L'image de %s dépasse la taille maximale autorisée.") % label)
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise UserError(_("L'image de %s est illisible (encodage invalide).") % label)
        if len(raw) > max_bytes:
            raise UserError(_("L'image de %s dépasse la taille maximale autorisée.") % label)
        if not raw.startswith(_PNG_MAGIC):
            raise UserError(_("L'image de %s doit être au format PNG.") % label)
        try:
            from PIL import Image
            Image.open(io.BytesIO(raw)).verify()
        except UserError:
            raise
        except Exception:
            raise UserError(_("L'image de %s est corrompue ou illisible.") % label)
        return raw

    def _validate_document_pdf(self, b64):
        """Validate the uploaded document is a readable, unencrypted PDF.

        Run on send (before computing ``hash_original``) so a non-PDF, oversize
        or encrypted file is rejected before it can break the placement widget
        or the stamping engine. Returns the decoded bytes.
        """
        if not b64:
            raise UserError(_("Veuillez joindre un document PDF avant l'envoi."))
        max_bytes = self._max_document_bytes()
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise UserError(_("Le document est illisible (encodage invalide)."))
        if len(raw) > max_bytes:
            raise UserError(_("Le document PDF dépasse la taille maximale autorisée."))
        if not raw.startswith(b"%PDF-"):
            raise UserError(_("Le document doit être un fichier PDF."))
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise UserError(_(
                    "Le PDF est protégé (chiffré) et ne peut être signé. "
                    "Veuillez fournir un PDF non protégé."))
            if len(reader.pages) < 1:
                raise UserError(_("Le PDF ne contient aucune page."))
        except UserError:
            raise
        except Exception:
            raise UserError(_("Le PDF est illisible ou endommagé."))
        return raw

    def _tsa_enabled(self):
        return self.env["ir.config_parameter"].sudo().get_param("bf_sign.rfc3161_enabled") in (
            "1", "True", "true")

    def _seal_enabled(self):
        # Active as soon as a sealing certificate exists, unless explicitly turned
        # off (the toggle is an off-switch — default on once a cert is present).
        if not self.env["bf.sign.seal"].has_cert():
            return False
        return self.env["ir.config_parameter"].sudo().get_param(
            "bf_sign.pdf_seal_enabled", "1") not in ("0", "False", "false")

    def _current_turn_signer(self):
        """For sequential signing, the signer whose turn it is (lowest order, not signed)."""
        self.ensure_one()
        pending = self.signer_ids.filtered(lambda s: s.state != "signed").sorted("sequence")
        return pending[:1]

    def _signer_can_sign(self, signer):
        """Whether this signer may sign right now (turn gating for sequential)."""
        self.ensure_one()
        if self.state not in ("sent", "in_progress"):
            return False
        if signer.state == "signed":
            return False
        if self.signing_order == "sequential":
            return self._current_turn_signer() == signer
        return True

    # ── Actions ──────────────────────────────────────────────────────────────
    def action_send(self):
        for rec in self:
            if rec.state not in ("draft", "sent", "in_progress"):
                raise UserError(_("Cette demande ne peut être envoyée dans son état actuel."))
            doc_bytes = rec._validate_document_pdf(rec.document_file)
            if not rec.signer_ids:
                raise UserError(_("Ajoutez au moins un signataire."))
            if not all(s.email for s in rec.signer_ids):
                raise UserError(_("Chaque signataire doit avoir un courriel."))
            # A request with no pad at all is legitimate (seal-only). But once
            # pads exist, a signer without one would receive a signing page with
            # nothing to sign and leave no visible mark on the document.
            if rec.field_ids:
                orphans = rec.signer_ids.filtered(lambda s: not s.field_ids)
                if orphans:
                    raise UserError(_(
                        "Ces signataires n'ont aucun pavé sur le document : %s. "
                        "Placez-leur au moins un pavé, ou retirez-les de la demande."
                    ) % ", ".join(orphans.mapped("name")))
            rec._ensure_signer_partners()
            rec.hash_original = rec._sha256_hex(doc_bytes)
            if not rec.expiry_date:
                days = int(self.env["ir.config_parameter"].sudo().get_param(
                    "bf_sign.default_expiry_days", "30") or 30)
                rec.expiry_date = fields.Datetime.now() + timedelta(days=days)
            rec.state = "sent"
            self.env["bf.sign.log"]._append(
                rec, "sent", actor=self.env.user.name, identity_method="internal_user",
                hash_before=rec.hash_original,
                note=_("Envoyée à %s") % ", ".join(rec.signer_ids.mapped("email")))
            # Email the right signers depending on the order.
            if rec.signing_order == "sequential":
                first = rec._current_turn_signer()
                if first:
                    rec._email_signer(first)
            else:
                for signer in rec.signer_ids:
                    rec._email_signer(signer)
        return True

    def _email_signer(self, signer):
        template = self.env.ref("bf_sign.mail_template_sign_request", raise_if_not_found=False)
        if not template:
            return
        # SECURITY: send the invitation as a bare mail.mail (no model/res_id,
        # auto_delete) so the signing token in the body NEVER lands in a
        # document-linked, persisted mail.message — otherwise any sign user able
        # to read bf.sign.signer could recover the token from the message body
        # and sign on the signer's behalf. Rendered under sudo because
        # access_token is manager-only and the sender may be a basic user.
        tmpl = template.sudo()
        body = tmpl._render_field("body_html", signer.ids, compute_lang=True)[signer.id]
        subject = tmpl._render_field("subject", signer.ids, compute_lang=True)[signer.id]
        company = signer.request_id.company_id
        self.env["mail.mail"].sudo().create({
            "subject": subject,
            "email_from": company.email_formatted or self.env.user.email_formatted,
            "email_to": signer.email,
            "body_html": body,
            "auto_delete": True,
        }).send()

    def _ensure_signer_partners(self):
        """Link each signer to a contact, creating one from name+email if needed."""
        self.ensure_one()
        Partner = self.env["res.partner"]
        for signer in self.signer_ids:
            if signer.partner_id or not signer.email:
                continue
            partner = Partner.search([("email", "=ilike", signer.email)], limit=1)
            if not partner:
                partner = Partner.create({
                    "name": signer.name or signer.email,
                    "email": signer.email,
                })
            elif signer.name and (partner.name or "").strip().lower() == \
                    (partner.email or "").strip().lower():
                # Contact auto-created earlier with email as name → enrich it.
                partner.name = signer.name
            signer.partner_id = partner.id

    # ── Field-layout templates (called from the placement widget) ────────────
    def save_field_template(self, name):
        """Save the current pad layout as a reusable template. Returns the id."""
        self.ensure_one()
        if not self.field_ids:
            raise UserError(_("Aucun pavé à enregistrer."))
        signers = self.signer_ids.sorted("sequence")
        idx = {s.id: i for i, s in enumerate(signers)}
        lines = [(0, 0, {
            "signer_index": idx.get(f.signer_id.id, 0),
            "field_type": f.field_type, "page": f.page,
            "pos_x": f.pos_x, "pos_y": f.pos_y, "width": f.width, "height": f.height,
            "fill_mode": f.fill_mode, "required": f.required, "value_text": f.value_text,
            "sequence": f.sequence,
        }) for f in self.field_ids]
        tmpl = self.env["bf.sign.field.template"].create({
            "name": name or _("Modèle — %s") % (self.document_filename or self.name),
            "line_ids": lines,
        })
        return tmpl.id

    def apply_field_template(self, template_id, replace=True):
        """Create pads from a template, mapping signer rank → the request's
        signers (by sequence). Returns {'created': n, 'skipped': n}."""
        self.ensure_one()
        tmpl = self.env["bf.sign.field.template"].browse(template_id)
        if not tmpl.exists():
            raise UserError(_("Modèle introuvable."))
        signers = self.signer_ids.sorted("sequence")
        if not signers:
            raise UserError(_("Ajoutez au moins un signataire avant d'appliquer un modèle."))
        if replace and self.field_ids:
            self.field_ids.unlink()
        Field = self.env["bf.sign.field"]
        created = skipped = 0
        for line in tmpl.line_ids:
            if line.signer_index >= len(signers):
                skipped += 1
                continue
            Field.create({
                "request_id": self.id, "signer_id": signers[line.signer_index].id,
                "field_type": line.field_type, "page": line.page,
                "pos_x": line.pos_x, "pos_y": line.pos_y,
                "width": line.width, "height": line.height,
                "fill_mode": line.fill_mode, "required": line.required,
                "value_text": line.value_text, "sequence": line.sequence,
            })
            created += 1
        return {"created": created, "skipped": skipped}

    def action_cancel(self):
        for rec in self:
            if rec.state == "signed":
                raise UserError(_("Un document signé ne peut être annulé."))
            rec.state = "cancelled"
            self.env["bf.sign.log"]._append(rec, "cancelled", actor=self.env.user.name)
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == "signed":
                raise UserError(_("Un document signé ne peut être remis en brouillon."))
            rec.state = "draft"
        return True

    def action_download_signed(self):
        self.ensure_one()
        if not self.signed_attachment_id:
            raise UserError(_("Aucun document signé disponible."))
        return {"type": "ir.actions.act_url",
                "url": "/web/content/%s?download=true" % self.signed_attachment_id.id,
                "target": "self"}

    def action_download_certificate(self):
        self.ensure_one()
        if not self.certificate_attachment_id:
            raise UserError(_("Aucun certificat disponible."))
        return {"type": "ir.actions.act_url",
                "url": "/web/content/%s?download=true" % self.certificate_attachment_id.id,
                "target": "self"}

    # ── Integrity verification ───────────────────────────────────────────────
    def _verify_integrity(self):
        """Recompute every integrity proof for a signed request.

        Returns a dict with three checks:
        * ``chain_ok``  — the append-only log hash-chain is intact;
        * ``content_ok``— SHA-256 of the stored signed PDF still equals ``hash_signed``;
        * ``tsa_ok``    — None if no RFC 3161 token, else whether the token's
                          messageImprint matches ``hash_stamped`` and was granted.
        """
        self.ensure_one()
        chain_ok = True
        if self.log_ids:
            chain_ok = self.log_ids[0].verify_chain()
        content_ok = False
        if self.signed_attachment_id and self.hash_signed:
            data = self.signed_attachment_id.datas
            content_ok = bool(data) and self._sha256_hex(
                base64.b64decode(data)) == self.hash_signed
        tsa_ok = None
        if self.tsa_token:
            tsa_ok = False
            try:
                from asn1crypto import tsp
                tsr = tsp.TimeStampResp.load(base64.b64decode(self.tsa_token))
                imprint = self._tsa_message_imprint_hex(tsr)
                status = tsr["status"]["status"].native
                tsa_ok = (
                    bool(imprint)
                    and imprint == (self.hash_stamped or "")
                    and status in ("granted", "granted_with_mods"))
            except Exception:  # noqa: BLE001
                tsa_ok = False
        seal_ok = None
        if self.sealed and self.signed_attachment_id and self.signed_attachment_id.datas:
            seal_ok = self.env["bf.sign.seal"].verify_pdf(
                base64.b64decode(self.signed_attachment_id.datas))
        return {"chain_ok": chain_ok, "content_ok": content_ok,
                "tsa_ok": tsa_ok, "seal_ok": seal_ok}

    def action_verify_integrity(self):
        self.ensure_one()
        if self.state != "signed":
            raise UserError(_("La vérification n'est disponible que pour une demande signée."))
        res = self._verify_integrity()
        ok = (res["chain_ok"] and res["content_ok"]
              and res["tsa_ok"] is not False and res["seal_ok"] is not False)
        lines = [
            _("Chaîne du journal : %s") % (_("intacte") if res["chain_ok"] else _("ALTÉRÉE")),
            _("Document scellé : %s") % (_("conforme") if res["content_ok"] else _("ALTÉRÉ")),
        ]
        if res["tsa_ok"] is None:
            lines.append(_("Horodatage RFC 3161 : non utilisé"))
        else:
            # We check the timestamp's messageImprint matches hash_stamped and the
            # request was granted — not the TSA's CMS signature chain (palier 2).
            lines.append(_("Horodatage RFC 3161 : %s") % (
                _("empreinte concordante") if res["tsa_ok"] else _("NON CONCORDANTE")))
        if res["seal_ok"] is None:
            lines.append(_("Sceau numérique : non utilisé"))
        else:
            lines.append(_("Sceau numérique (PAdES) : %s") % (
                _("valide") if res["seal_ok"] else _("INVALIDE")))
        title = _("Intégrité confirmée") if ok else _("Problème d'intégrité")
        self.message_post(body="<strong>%s</strong><br/>%s" % (title, "<br/>".join(lines)))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": " · ".join(lines),
                "type": "success" if ok else "danger",
                "sticky": True,
            },
        }

    # ── Signing flow (called from the public controller, per signer) ─────────
    def register_signer_view(self, signer, ip=None, user_agent=None):
        self.ensure_one()
        if signer.state == "pending":
            signer.sudo().state = "viewed"
        self.env["bf.sign.log"].sudo()._append(
            self, "viewed", actor=signer.email, ip_address=ip, user_agent=user_agent,
            identity_method=signer._identity_method(), note=_("Signataire : %s") % signer.name)

    def _apply_field_values(self, signer, field_values):
        """Validate and store the values a signer typed into their fillable pads.

        ``field_values`` maps str(field_id) -> value (from the public form).
        Only the signer's own ``fill_mode='signer'`` fields are considered.
        """
        self.ensure_one()
        max_len = int(self.env["ir.config_parameter"].sudo().get_param(
            "bf_sign.max_field_chars", "200") or 200)
        for f in signer.field_ids.filtered(
                lambda x: x.field_type in VALUE_TYPES and x.fill_mode == "signer"):
            raw = (field_values.get(str(f.id)) or "").strip()
            if f.field_type == "checkbox":
                # An unchecked box posts nothing at all, so absence is the value.
                checked = raw.lower() in ("1", "on", "true", "oui", "yes")
                if f.required and not checked:
                    raise UserError(_("Veuillez cocher toutes les cases obligatoires."))
                f.filled_value = "on" if checked else ""
                continue
            if not raw:
                if f.required:
                    raise UserError(_("Veuillez remplir tous les champs obligatoires."))
                f.filled_value = ""
                continue
            if len(raw) > max_len:
                raise UserError(_("Une valeur saisie dépasse la longueur maximale."))
            if f.field_type == "date":
                try:
                    fields.Date.to_date(raw)
                except (ValueError, TypeError):
                    raise UserError(_("Format de date invalide (attendu AAAA-MM-JJ)."))
            elif f.field_type == "number":
                cleaned = raw.replace(",", ".")
                for space in _NUM_SPACES:
                    cleaned = cleaned.replace(space, "")
                try:
                    float(cleaned)
                except (ValueError, TypeError):
                    raise UserError(_("Valeur numérique invalide : %s") % raw)
            elif f.field_type == "email" and not EMAIL_RE.match(raw):
                raise UserError(_("Adresse courriel invalide : %s") % raw)
            f.filled_value = raw

    def register_signer_signature(self, signer, signature_b64, initials_b64,
                                  consent, ip=None, user_agent=None, field_values=None):
        """Record one signer's signature. Triggers finalize when all have signed."""
        self.ensure_one()
        if not self._signer_can_sign(signer):
            raise UserError(_("Vous ne pouvez pas signer cette demande pour le moment."))
        if not consent:
            raise UserError(_("Le consentement est requis pour signer."))
        # Validate the drawn images BEFORE marking the signer as signed, so a
        # malformed payload fails on the signing page rather than crashing
        # finalize after the fact.
        self._validate_signature_png(signature_b64, _("signature"))
        if initials_b64:
            self._validate_signature_png(initials_b64, _("paraphe"))
        # Validate + store the values the signer typed into their fillable fields.
        self._apply_field_values(signer, field_values or {})
        if self.expiry_date and self.expiry_date < fields.Datetime.now():
            self.state = "expired"
            self.env["bf.sign.log"]._append(self, "expired", actor=signer.email, ip_address=ip)
            raise UserError(_("Ce lien de signature a expiré."))

        now = fields.Datetime.now()
        vals = {
            "signature_image": signature_b64,
            "consent_given": True,
            "consent_timestamp": now,
            "signed_on": now,
            "signer_ip": ip,
            "signer_user_agent": user_agent,
            "state": "signed",
        }
        if initials_b64:
            vals["initials_image"] = initials_b64
        signer.write(vals)

        Log = self.env["bf.sign.log"]
        identity = signer._identity_method()
        Log._append(self, "consented", actor=signer.email, ip_address=ip,
                    user_agent=user_agent, identity_method=identity,
                    note=self.consent_text)
        Log._append(self, "signed", actor=signer.email, ip_address=ip,
                    user_agent=user_agent, identity_method=identity,
                    hash_before=self.hash_original,
                    note=_("Signataire : %s") % signer.name)
        self._post_sign_progress()
        return True

    def register_signer_refusal(self, signer, reason=None, ip=None, user_agent=None):
        """Record a signer declining to sign — the whole request is refused."""
        self.ensure_one()
        if self.state not in ("sent", "in_progress"):
            raise UserError(_("Cette demande ne peut être refusée dans son état actuel."))
        if signer.state == "signed":
            raise UserError(_("Vous avez déjà signé cette demande."))
        signer.write({"state": "refused"})
        self.state = "refused"
        note = (_("Refusé par %s. Motif : %s") % (signer.name, reason)) if reason \
            else _("Refusé par %s.") % signer.name
        self.env["bf.sign.log"]._append(
            self, "refused", actor=signer.email, ip_address=ip, user_agent=user_agent,
            identity_method="email_link_token", note=note)
        template = self.env.ref("bf_sign.mail_template_sign_refused", raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        return True

    def _post_sign_progress(self):
        self.ensure_one()
        if all(s.state == "signed" for s in self.signer_ids):
            self._finalize()
        else:
            self.state = "in_progress"
            if self.signing_order == "sequential":
                nxt = self._current_turn_signer()
                if nxt:
                    self._email_signer(nxt)

    def _finalize(self):
        """Seal the document once all signers have signed."""
        self.ensure_one()
        if self.state == "signed":
            return
        # Serialize concurrent "last signer" submissions (parallel signing): take
        # a row lock and re-read the authoritative state from the cursor (not the
        # ORM cache) so the document is finalized exactly once — no double
        # attachments, no double completion email.
        self.env.cr.execute(
            "SELECT state FROM bf_sign_request WHERE id = %s FOR UPDATE", (self.id,))
        row = self.env.cr.fetchone()
        if row and row[0] == "signed":
            return

        original_bytes = base64.b64decode(self.document_file)
        self.invalidate_recordset(["signer_ids", "field_ids", "log_ids"])

        stamped_bytes = self._stamp_document(original_bytes) if self.field_ids else original_bytes
        hash_stamped = self._sha256_hex(stamped_bytes)

        # Trusted timestamp BEFORE rendering the certificate, so the certificate
        # (which gets baked into the sealed PDF) can actually display the RFC 3161
        # stamp. The token covers the stamped content (hash_stamped), not the
        # final bundle — a certificate embedded in a PDF cannot timestamp that
        # same PDF. ``hash_signed`` (logged + re-derivable) covers the assembly.
        self.hash_stamped = hash_stamped
        if self._tsa_enabled():
            self._request_tsa_timestamp(stamped_bytes)

        cert_pdf, _ext = self.env["ir.actions.report"]._render_qweb_pdf(
            CERTIFICATE_REPORT, self.ids)
        signed_pdf = merge_pdf([stamped_bytes, cert_pdf])

        # Digital seal (PAdES/PKCS#7) — DocuSeal-style tamper-proof signature.
        # Done last so it covers the whole sealed bundle; the TSA timestamp (if
        # enabled) is embedded inside the signature.
        sealed = False
        if self._seal_enabled():
            try:
                tsa = self.env["ir.config_parameter"].sudo().get_param(
                    "bf_sign.tsa_url") if self._tsa_enabled() else None
                signed_pdf = self.env["bf.sign.seal"].seal_pdf(
                    signed_pdf,
                    reason=_("Document signé via %s") % (self.company_id.name or ""),
                    location=self.company_id.name or "",
                    tsa_url=tsa)
                sealed = True
            except Exception as exc:  # noqa: BLE001
                _logger.warning("bf_sign: PDF seal failed for %s: %s", self.name, exc)
        hash_signed = self._sha256_hex(signed_pdf)

        signed_name = self._signed_filename()
        att_signed = self.env["ir.attachment"].create({
            "name": signed_name, "datas": base64.b64encode(signed_pdf),
            "res_model": self._name, "res_id": self.id, "mimetype": "application/pdf"})
        att_cert = self.env["ir.attachment"].create({
            "name": "Certificat - %s.pdf" % self.name, "datas": base64.b64encode(cert_pdf),
            "res_model": self._name, "res_id": self.id, "mimetype": "application/pdf"})
        self.write({
            "signed_attachment_id": att_signed.id,
            "certificate_attachment_id": att_cert.id,
            "hash_signed": hash_signed,
            "signed_on": fields.Datetime.now(),
            "state": "signed",
            "sealed": sealed,
        })

        self.env["bf.sign.log"]._append(
            self, "finalized", actor="system",
            hash_before=self.hash_original, hash_after=hash_signed,
            note=_("Document scellé (%d signataire(s) + certificat).") % len(self.signer_ids))

        self.message_post(
            body=_("Document signé par tous les signataires. Empreinte SHA-256 : %s") % hash_signed,
            attachment_ids=[att_signed.id, att_cert.id])
        template = self.env.ref("bf_sign.mail_template_sign_completed", raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True, email_values={
                "attachment_ids": [(6, 0, [att_signed.id, att_cert.id])]})
        self._notify_source_signed()

    def _notify_source_signed(self):
        """Post the signed document back to the source record (res_model/res_id),
        when the request was created from one. Attaches the signed PDF +
        certificate and a chatter note; never changes the source's state. Failures
        are logged, never raised (must not break finalization)."""
        self.ensure_one()
        if not (self.res_model and self.res_id and self.signed_attachment_id):
            return
        if self.res_model not in self.env:
            return
        try:
            record = self.env[self.res_model].sudo().browse(self.res_id).exists()
            if not record or not hasattr(record, "message_post"):
                return
            # res_model/res_id are user-settable via RPC; only post back to a
            # source the request creator could actually write — never let the
            # sudo finalize attach the signed PDF to an arbitrary record.
            try:
                record.with_user(self.create_uid).check_access("write")
            except Exception:  # noqa: BLE001 — fail closed on any access error
                return
            new_atts = self.env["ir.attachment"].sudo()
            for att in (self.signed_attachment_id, self.certificate_attachment_id):
                if att:
                    new_atts |= att.sudo().copy({
                        "res_model": record._name, "res_id": record.id})
            record.message_post(
                body=_("Document signé électroniquement (%(n)s signataire(s)) — "
                       "empreinte SHA-256 : %(h)s",
                       n=len(self.signer_ids), h=self.hash_signed or ""),
                attachment_ids=new_atts.ids)
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "bf_sign: source notify failed for %s (%s,%s): %s",
                self.name, self.res_model, self.res_id, exc)

    def _signed_filename(self):
        base = (self.document_filename or self.name or "document")
        if base.lower().endswith(".pdf"):
            base = base[:-4]
        return "%s - signé.pdf" % base

    # ── Stamping engine ──────────────────────────────────────────────────────
    def _stamp_document(self, original_bytes):
        """Overlay each placed field onto the document at its page/coordinates.

        Coordinates are fractions of the page from the top-left; we convert to
        PDF's bottom-left origin per page using each page's media box.
        """
        self.ensure_one()
        from PyPDF2 import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader

        reader = PdfReader(io.BytesIO(original_bytes))
        writer = PdfWriter()
        fields_by_page = {}
        for f in self.field_ids:
            fields_by_page.setdefault(f.page, []).append(f)

        for idx, page in enumerate(reader.pages, start=1):
            page_fields = fields_by_page.get(idx)
            if page_fields:
                pw = float(page.mediabox.width)
                ph = float(page.mediabox.height)
                buf = io.BytesIO()
                c = canvas.Canvas(buf, pagesize=(pw, ph))
                for f in page_fields:
                    x = f.pos_x * pw
                    w = max(f.width * pw, 1.0)
                    h = max(f.height * ph, 1.0)
                    y = ph - (f.pos_y * ph) - h  # top-origin → bottom-origin
                    self._draw_field(c, f, x, y, w, h, ImageReader)
                c.save()
                buf.seek(0)
                page.merge_page(PdfReader(buf).pages[0])
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def _draw_field(self, c, field, x, y, w, h, ImageReader):
        signer = field.signer_id
        if field.field_type in ("signature", "initials"):
            data = signer.signature_image
            if field.field_type == "initials":
                data = signer.initials_image or signer.signature_image
            if data:
                img = ImageReader(io.BytesIO(base64.b64decode(data)))
                c.drawImage(img, x, y, width=w, height=h, mask="auto",
                            preserveAspectRatio=True, anchor="sw")
        elif field.field_type == "checkbox":
            self._draw_checkbox(c, field, x, y, w, h)
        elif field.field_type in VALUE_TYPES:
            val = field._display_value()
            if val:
                self._draw_text(c, val, x, y, w, h)

    # Text is fitted to the pad instead of being drawn at a fixed 9 pt: a pad
    # resized in the placement editor now actually changes the stamped size, and
    # a value too long for its box is shortened rather than bleeding across the
    # page.
    _TEXT_FONT = "Helvetica"
    _TEXT_MIN_SIZE = 5.0
    _TEXT_MAX_SIZE = 14.0

    def _draw_text(self, c, value, x, y, w, h, padding=2.0):
        avail_w = max(w - 2 * padding, 1.0)
        size = min(max(h * 0.62, self._TEXT_MIN_SIZE), self._TEXT_MAX_SIZE)
        while size > self._TEXT_MIN_SIZE and \
                c.stringWidth(value, self._TEXT_FONT, size) > avail_w:
            size -= 0.5
        if c.stringWidth(value, self._TEXT_FONT, size) > avail_w:
            value = self._ellipsize(c, value, avail_w, size)
        c.setFont(self._TEXT_FONT, size)
        # Vertically centred on the pad, on the text baseline.
        c.drawString(x + padding, y + (h - size * 0.72) / 2.0, value)

    def _ellipsize(self, c, value, avail_w, size):
        ell = "…"
        if c.stringWidth(ell, self._TEXT_FONT, size) > avail_w:
            return ""
        while value and c.stringWidth(value + ell, self._TEXT_FONT, size) > avail_w:
            value = value[:-1]
        return value + ell if value else ell

    def _draw_checkbox(self, c, field, x, y, w, h):
        """A square box, sized to the pad, ticked when the pad reads as checked."""
        side = max(min(w, h) * 0.8, 4.0)
        bx = x + (w - side) / 2.0
        by = y + (h - side) / 2.0
        c.setLineWidth(max(side * 0.06, 0.6))
        c.rect(bx, by, side, side, stroke=1, fill=0)
        if field._is_checked():
            c.setLineWidth(max(side * 0.12, 0.8))
            c.line(bx + side * 0.20, by + side * 0.52,
                   bx + side * 0.42, by + side * 0.24)
            c.line(bx + side * 0.42, by + side * 0.24,
                   bx + side * 0.80, by + side * 0.76)

    # ── RFC 3161 trusted timestamp (optional, defensive) ─────────────────────
    def _request_tsa_timestamp(self, data_bytes):
        self.ensure_one()
        url = self.env["ir.config_parameter"].sudo().get_param(
            "bf_sign.tsa_url", "https://freetsa.org/tsr")
        try:
            import requests
            from asn1crypto import tsp, algos, core

            digest = hashlib.sha256(data_bytes).digest()
            req = tsp.TimeStampReq({
                "version": "v1",
                "message_imprint": tsp.MessageImprint({
                    "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                    "hashed_message": digest,
                }),
                "nonce": core.Integer(int.from_bytes(os.urandom(8), "big")),
                "cert_req": True,
            })
            resp = requests.post(url, data=req.dump(),
                                 headers={"Content-Type": "application/timestamp-query"},
                                 timeout=10)
            resp.raise_for_status()
            tsr = tsp.TimeStampResp.load(resp.content)
            if tsr["status"]["status"].native not in ("granted", "granted_with_mods"):
                return False
            self.write({
                "tsa_token": base64.b64encode(resp.content),
                "tsa_url": url,
                "tsa_timestamp": fields.Datetime.now(),
                "tsa_gentime": self._tsa_gentime(tsr),
            })
            self.env["bf.sign.log"]._append(
                self, "tsa_stamped", actor="system", identity_method="rfc3161",
                note=_("Horodatage RFC 3161 obtenu de %s") % url,
                hash_after=self._sha256_hex(data_bytes))
            return True
        except Exception as exc:  # noqa: BLE001
            _logger.warning("RFC 3161 timestamp failed for %s: %s", self.name, exc)
            return False

    @staticmethod
    def _tsa_tst_info(tsr):
        """Extract the TSTInfo structure from a parsed RFC 3161 TimeStampResp.

        Importing ``asn1crypto.tsp`` registers the id-ct-TSTInfo OID, so the
        encapsulated content auto-parses: ``.parsed`` yields the TSTInfo object
        (``.native`` would be an already-decoded dict, not byte string).
        """
        from asn1crypto import tsp  # noqa: F401  (registers TSTInfo OID)
        return tsr["time_stamp_token"]["content"]["encap_content_info"]["content"].parsed

    @api.model
    def _tsa_gentime(self, tsr):
        """The authoritative time attested by the TSA (genTime), as naive UTC."""
        try:
            gen = self._tsa_tst_info(tsr)["gen_time"].native
            if not gen:
                return False
            if gen.tzinfo is not None:
                gen = gen.astimezone(timezone.utc).replace(tzinfo=None)
            return gen
        except Exception:  # noqa: BLE001
            return False

    @api.model
    def _tsa_message_imprint_hex(self, tsr):
        """Hex of the digest the TSA actually timestamped (messageImprint)."""
        try:
            return self._tsa_tst_info(tsr)["message_imprint"]["hashed_message"].native.hex()
        except Exception:  # noqa: BLE001
            return ""

    # ── Cron ──────────────────────────────────────────────────────────────────
    @api.model
    def _cron_expire_requests(self):
        now = fields.Datetime.now()
        stale = self.search([
            ("state", "in", ("sent", "in_progress")),
            ("expiry_date", "!=", False), ("expiry_date", "<", now)])
        for rec in stale:
            rec.state = "expired"
            self.env["bf.sign.log"]._append(rec, "expired", actor="system")
        return True

    # ── Guards ────────────────────────────────────────────────────────────────
    def unlink(self):
        if any(rec.state == "signed" for rec in self):
            raise UserError(_("Une demande signée ne peut être supprimée (valeur probante)."))
        return super(BfSignRequest, self.with_context(bf_sign_gc=True)).unlink()
