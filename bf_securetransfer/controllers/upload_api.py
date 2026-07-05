"""JSON API driving the public upload page (st_upload.js).

All routes are type="json" auth="public" POST. Success responses return the
data directly; failures return {"error": "<code>", "message": "<safe FR/EN
text>"} — internal details never leave the server (UserError messages are
considered safe by construction, anything else is logged and replaced by a
generic message).

Every transfer-scoped route resolves the draft through its upload_token
(uuid4.hex, constant-time compare, failed lookups rate-limited) and never
exposes S3 internals beyond the presigned URLs themselves.
"""

import functools
import logging
import re
import uuid

from odoo import _
from odoo.exceptions import UserError
from odoo.http import Controller, request, route
from odoo.tools import email_normalize

from ..models import s3
from .main import (
    HONEYPOT_FIELD,
    _UPLOAD_OPS_MAX,
    _client_ip,
    _create_limiter,
    _finalize_limiter,
    _rate_create_max,
    _resolve_locale,
    _resolve_transfer_by_upload_token,
    _upload_enabled,
    _upload_ops_limiter,
    _user_agent,
)

_logger = logging.getLogger(__name__)

MAX_RECIPIENTS = 10
MAX_MESSAGE_CHARS = 2000
MAX_SENDER_NAME_CHARS = 128

_SPLIT_RE = re.compile(r"[,;\s]+")


def _err(code, message):
    return {"error": code, "message": message}


def _api_guard(func):
    """UserError → safe message; anything else → log + generic message.

    Keeps the JSON-RPC layer from serializing tracebacks to the public.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except UserError as exc:
            return _err("invalid", str(exc))
        except Exception:
            _logger.exception(
                "bf_securetransfer: API failure in %s", func.__name__)
            return _err("server_error",
                        _("Une erreur est survenue. Veuillez réessayer plus tard."))
    return wrapper


# ── Input validation helpers ──────────────────────────────────────────────────

def _clean_recipients(value):
    """Normalize the recipient list (list or separated string).

    Returns (comma_joined_str, error_dict_or_None). Duplicates are dropped,
    every address must normalize through odoo.tools.email_normalize.
    """
    if not value:
        return "", None
    if isinstance(value, str):
        parts = [p for p in _SPLIT_RE.split(value) if p]
    elif isinstance(value, (list, tuple)):
        parts = [str(p).strip() for p in value if str(p).strip()]
    else:
        return None, _err("invalid_recipients",
                          _("Liste de destinataires invalide."))
    if len(parts) > MAX_RECIPIENTS:
        return None, _err("too_many_recipients",
                          _("Maximum %s destinataires.", MAX_RECIPIENTS))
    cleaned = []
    for part in parts:
        normalized = email_normalize(part)
        if not normalized:
            return None, _err(
                "invalid_recipients",
                _("Adresse de destinataire invalide : %s", part[:64]))
        if normalized not in cleaned:
            cleaned.append(normalized)
    return ", ".join(cleaned), None


def _clean_message(value):
    """Returns (message_str, error_dict_or_None)."""
    message = (value or "").strip() if isinstance(value, str) else ""
    if len(message) > MAX_MESSAGE_CHARS:
        return None, _err("message_too_long",
                          _("Le message dépasse %s caractères.", MAX_MESSAGE_CHARS))
    return message, None


def _clean_retention(value, limits):
    """Coerce the requested retention to an allowed choice.

    The JS only offers valid choices; a tampered value silently falls back to
    the default (7 days when offered, first choice otherwise) — no oracle.
    """
    choices = list(limits.get("expiry_choices") or [7])
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = 0
    if days in choices:
        return days
    return 7 if 7 in choices else choices[0]


def _clean_sender_name(value):
    name = (value or "").strip() if isinstance(value, str) else ""
    return name[:MAX_SENDER_NAME_CHARS]


def _ops_rate_error():
    """Burst cap on the upload plumbing (register/presign/multipart/remove):
    120/min/IP across the whole set — anti presign-farming. Returns an error
    dict when over budget, None otherwise."""
    if not _upload_ops_limiter.consume(_client_ip(), _UPLOAD_OPS_MAX):
        return _err("rate_limited",
                    _("Trop de requêtes. Réessayez dans une minute."))
    return None


def _draft_or_error(ut):
    """upload_token → (draft transfer, None) or (None, error dict)."""
    transfer = _resolve_transfer_by_upload_token(ut)
    if transfer is None:
        return None, _err("not_found",
                          _("Lien de téléversement invalide ou expiré."))
    if transfer.state != "draft":
        return None, _err("not_draft",
                          _("Ce transfert n'est plus modifiable."))
    return transfer, None


def _file_or_error(transfer, file_id):
    """file_id → (secure.transfer.file of this transfer, None) or error."""
    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        return None, _err("invalid_file", _("Fichier introuvable."))
    rec_file = transfer.file_ids.filtered(lambda f: f.id == file_id)[:1]
    if not rec_file:
        return None, _err("invalid_file", _("Fichier introuvable."))
    return rec_file, None


class SecureTransferUploadApi(Controller):

    # ── Create draft ──────────────────────────────────────────────────────────
    @route("/secrets/api/create", type="json", auth="public", methods=["POST"])
    @_api_guard
    def api_create(self, **params):
        env = request.env
        # Kill-switch also guards the API: hiding the page is not enough.
        if not _upload_enabled(env):
            return _err("disabled",
                        _("Le service de transfert est temporairement indisponible."))
        # Honeypot: bots that fill the hidden field get a fake success with a
        # throwaway token — every later call on it 404s, nothing is stored. The
        # payload mirrors the real success shape (token + limits) so a bot
        # cannot detect the trap from a missing key.
        if (params.get(HONEYPOT_FIELD) or "").strip():
            _logger.info("bf_securetransfer: honeypot triggered from IP %s",
                         _client_ip())
            decoy = env["secure.transfer.brand"].sudo()._from_request()
            return {"upload_token": uuid.uuid4().hex,
                    "limits": decoy._effective_limits()}
        ip = _client_ip()
        if not _create_limiter.consume(ip, _rate_create_max(env)):
            return _err("rate_limited",
                        _("Trop de transferts créés récemment. Réessayez plus tard."))
        # Personal drop page (/to/<slug>): the page tells us its slug so the
        # draft is bound to the drop brand (fixed recipient), not the
        # Host-resolved brand. Resolving by slug here is safe — sending to a
        # drop page is public by design (anyone may send to its owner).
        brand = None
        drop_slug = (params.get("drop_slug") or "").strip().lower()
        if drop_slug:
            brand = env["secure.transfer.brand"].sudo()._resolve_for_slug(drop_slug)
            if not brand:
                return _err("not_found", _("Page de dépôt introuvable."))
        if not brand:
            brand = env["secure.transfer.brand"].sudo()._from_request()
        limits = brand._effective_limits()
        # The e-mail is OPTIONAL at draft creation: the page lets a file be
        # dropped before the address is typed (the draft is created on the
        # first drop). It is normalized here and REQUIRED at finalize
        # (action_finalize raises when empty). An empty value is accepted; a
        # non-empty one is normalized (garbage becomes empty, re-checked at
        # send). The allowlist check on a present address stays in the model.
        sender_email = email_normalize(params.get("sender_email") or "")
        # Recipients and the message are re-sent and re-validated
        # authoritatively at finalize (with the allowlist). At draft creation
        # they may still be half-typed (the draft is created on the first file
        # drop, before the fields are complete): never hard-fail here — keep
        # what cleans, drop what does not.
        recipients, error = _clean_recipients(params.get("recipient_emails"))
        if error:
            recipients = ""
        message, error = _clean_message(params.get("message"))
        if error:
            message = ""
        vals = {
            "sender_name": _clean_sender_name(params.get("sender_name")),
            "sender_email": sender_email,
            "recipient_emails": recipients,
            "message": message,
            "retention_days": _clean_retention(params.get("retention_days"), limits),
            "max_downloads": 0,
        }
        locale = _resolve_locale(env)
        # api_create enforces the DB-backed daily quotas (IP + sender email)
        # and raises a safe UserError on refusal.
        transfer = env["secure.transfer"].sudo().api_create(
            brand, vals, ip, _user_agent(), locale)
        return {"upload_token": transfer.upload_token, "limits": limits}

    # ── Register one file + presign ───────────────────────────────────────────
    @route("/secrets/api/<string:ut>/presign", type="json", auth="public",
           methods=["POST"])
    @_api_guard
    def api_presign(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        try:
            size = int(params.get("size"))
        except (TypeError, ValueError):
            size = 0
        if size <= 0:
            return _err("invalid_size", _("Taille de fichier invalide."))
        # _register_file locks the row, applies the deny-list and the
        # aggregate quotas, derives s3_key/mimetype server-side and decides
        # the upload mode from the multipart threshold.
        rec_file = transfer._register_file(params.get("filename"), size)
        if rec_file.upload_mode == "simple":
            data = rec_file.presign_simple()
            return {
                "file_id": rec_file.id,
                "mode": "simple",
                "url": data["url"],
                "headers": data["headers"],
            }
        return {
            "file_id": rec_file.id,
            "mode": "multipart",
            "part_size": int(rec_file.part_size),
            "parts_total": int(rec_file.parts_total),
        }

    # ── Multipart cycle ───────────────────────────────────────────────────────
    @route("/secrets/api/<string:ut>/multipart/initiate", type="json",
           auth="public", methods=["POST"])
    @_api_guard
    def api_mpu_initiate(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        rec_file, error = _file_or_error(transfer, params.get("file_id"))
        if error:
            return error
        data = rec_file.mpu_initiate()
        # The UploadId stays server-side: the browser only ever needs the
        # presigned part URLs.
        return {
            "file_id": rec_file.id,
            "part_size": int(data["part_size"]),
            "parts_total": int(data["parts_total"]),
        }

    @route("/secrets/api/<string:ut>/multipart/sign", type="json",
           auth="public", methods=["POST"])
    @_api_guard
    def api_mpu_sign(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        rec_file, error = _file_or_error(transfer, params.get("file_id"))
        if error:
            return error
        raw = params.get("part_numbers")
        if not isinstance(raw, (list, tuple)) or not raw:
            return _err("invalid_parts", _("Numéros de parties invalides."))
        try:
            batch_max = max(1, int(s3.param(request.env, "mpu_sign_batch_max", "20")))
        except (TypeError, ValueError):
            batch_max = 20
        # Bound the request BEFORE any int() conversion: a huge list, or a
        # single giant numeric string, would otherwise burn CPU (int() parsing
        # is ~O(digits^2)) — a cheap-body DoS. Reject an oversized batch and any
        # element that is not a small int / short digit string up front.
        if len(raw) > batch_max:
            return _err("invalid_parts", _("Numéros de parties invalides."))
        numbers = []
        for n in raw:
            if isinstance(n, bool):  # bool is an int subclass — reject
                return _err("invalid_parts", _("Numéros de parties invalides."))
            if isinstance(n, int):
                numbers.append(n)
            elif isinstance(n, str) and n.isdigit() and len(n) <= 7:
                numbers.append(int(n))
            else:
                return _err("invalid_parts", _("Numéros de parties invalides."))
        numbers = sorted(set(numbers))
        parts_total = int(rec_file.parts_total or 0)
        if len(numbers) > batch_max \
                or any(n < 1 or n > parts_total for n in numbers):
            return _err("invalid_parts", _("Numéros de parties invalides."))
        urls = rec_file.mpu_sign(numbers)
        # JSON object keys are strings: normalize here, the JS expects it.
        return {"urls": {str(n): url for n, url in urls.items()}}

    @route("/secrets/api/<string:ut>/multipart/complete", type="json",
           auth="public", methods=["POST"])
    @_api_guard
    def api_mpu_complete(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        rec_file, error = _file_or_error(transfer, params.get("file_id"))
        if error:
            return error
        # Server-side completion rebuilds the part list from ListParts —
        # client-supplied ETags are never trusted.
        rec_file.mpu_complete()
        return {"ok": True}

    @route("/secrets/api/<string:ut>/multipart/abort", type="json",
           auth="public", methods=["POST"])
    @_api_guard
    def api_mpu_abort(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        rec_file, error = _file_or_error(transfer, params.get("file_id"))
        if error:
            return error
        rec_file.mpu_abort()
        return {"ok": True}

    @route("/secrets/api/<string:ut>/multipart/status", type="json",
           auth="public", methods=["POST"])
    @_api_guard
    def api_mpu_status(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        rec_file, error = _file_or_error(transfer, params.get("file_id"))
        if error:
            return error
        # Resume support: the truth comes from ListParts on the bucket.
        return rec_file.mpu_status()

    # ── Remove a file pre-finalize ────────────────────────────────────────────
    @route("/secrets/api/<string:ut>/remove", type="json", auth="public",
           methods=["POST"])
    @_api_guard
    def api_remove(self, ut, **params):
        error = _ops_rate_error()
        if error:
            return error
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        rec_file, error = _file_or_error(transfer, params.get("file_id"))
        if error:
            return error
        # Best-effort bucket cleanup; the draft GC cron sweeps any leftover.
        try:
            if rec_file.upload_mode == "multipart" and rec_file.s3_upload_id:
                rec_file.mpu_abort()
            rec_file._s3_delete()
        except Exception:
            _logger.warning(
                "bf_securetransfer: best-effort S3 cleanup failed for file #%s "
                "of %s", rec_file.id, transfer.name, exc_info=True)
        rec_file.unlink()
        return {"ok": True}

    # ── Finalize ──────────────────────────────────────────────────────────────
    @route("/secrets/api/<string:ut>/finalize", type="json", auth="public",
           methods=["POST"])
    @_api_guard
    def api_finalize(self, ut, **params):
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        env = request.env
        ip = _client_ip()
        if not _finalize_limiter.consume(ip, _rate_create_max(env)):
            return _err("rate_limited",
                        _("Trop de requêtes. Réessayez plus tard."))
        limits = transfer.brand_id._effective_limits()
        # The options panel is filled after the draft was created (create
        # fires on the first file drop), so finalize carries the final values
        # and re-validates them like create did.
        updates = {}
        if "sender_email" in params:
            sender_email = email_normalize(params.get("sender_email") or "")
            if not sender_email:
                return _err("invalid_email",
                            _("Adresse courriel de l'expéditeur invalide."))
            updates["sender_email"] = sender_email
        if "sender_name" in params:
            updates["sender_name"] = _clean_sender_name(params.get("sender_name"))
        # Drop page: the recipient is fixed to the page owner and re-forced by
        # action_finalize — ignore whatever recipients the client submits.
        is_drop = bool(transfer.brand_id.fixed_recipient)
        if not is_drop and "recipient_emails" in params:
            recipients, error = _clean_recipients(params.get("recipient_emails"))
            if error:
                return error
            # Anti-piggyback (destination side): enforce the brand's recipient
            # allowlist on any recipients changed at finalize too.
            bad = [r for r in recipients.split(",")
                   if r.strip() and not transfer.brand_id._recipient_allowed(r.strip())]
            if bad:
                return _err("recipient_not_allowed", _(
                    "Ce service n'autorise l'envoi qu'à certaines adresses : %s")
                    % ", ".join(bad))
            updates["recipient_emails"] = recipients
        if "message" in params:
            message, error = _clean_message(params.get("message"))
            if error:
                return error
            updates["message"] = message
        if "retention_days" in params:
            updates["retention_days"] = _clean_retention(
                params.get("retention_days"), limits)
        # Burn-after-download: only honored when the brand allows it.
        if limits.get("allow_burn"):
            updates["burn_after_download"] = bool(params.get("burn_after_download"))
        if updates:
            transfer.write(updates)
        password = params.get("password")
        password = password.strip() if isinstance(password, str) else None
        if password and not limits.get("allow_password"):
            return _err("password_not_allowed",
                        _("La protection par mot de passe n'est pas offerte ici."))
        # action_finalize HEAD-verifies every file, pins the ETags, rotates
        # the upload token, sets the expiry and sends the emails. Idempotent
        # under row lock.
        result = transfer.action_finalize(password=password or None)
        return result

    @route("/secrets/api/<string:ut>/confirm", type="json", auth="public",
           methods=["POST"])
    @_api_guard
    def api_confirm_sender(self, ut, **params):
        """Sender-OTP confirmation (tenant setting). Verifies the code emailed
        to the sender at finalize, then activates the transfer."""
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        ip = _client_ip()
        if not _finalize_limiter.consume(ip, _rate_create_max(request.env)):
            return _err("rate_limited",
                        _("Trop de requêtes. Réessayez plus tard."))
        try:
            return transfer.confirm_sender_otp(params.get("code") or "")
        except UserError as e:
            return _err("otp_error", e.args[0] if e.args else _("Code invalide."))

    @route("/secrets/api/<string:ut>/confirm/resend", type="json",
           auth="public", methods=["POST"])
    @_api_guard
    def api_confirm_resend(self, ut, **params):
        """Re-send the sender OTP for a draft awaiting confirmation."""
        transfer, error = _draft_or_error(ut)
        if error:
            return error
        if not _finalize_limiter.consume(_client_ip(),
                                         _rate_create_max(request.env)):
            return _err("rate_limited",
                        _("Trop de requêtes. Réessayez plus tard."))
        if transfer.sudo().sender_otp_hash:
            transfer._send_sender_otp()
        return {"resent": True}
