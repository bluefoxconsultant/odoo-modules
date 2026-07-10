"""Public HTTP pages of the secure transfer product.

Routes here render the standalone QWeb pages (no portal/website layout):

- GET  /secrets                    branded upload page (+ #st-config JSON block)
- GET  /s/<token>                  download page / password gate / neutral 404
- POST /s/<token>/unlock           password submission (session flag)
- GET  /s/<token>/dl/<file_id>     integrity re-check then 302 to presigned GET
- POST /s/<token>/report           abuse report (activity for the managers)

Shared helpers (client IP, rate limiters, token resolution, security headers)
live at module level and are imported by controllers/upload_api.py.

Render context passed to the QWeb templates:

- page_upload:      brand, visuals, limits, locale, st_config_json (Markup)
- page_download:    brand, visuals, transfer, files, token, locked (bool),
                    pw_error, reported
- page_unavailable: brand, visuals, message (optional str)
"""

import hmac
import json
import logging
import re
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

from markupsafe import Markup

from odoo import _, fields
from odoo.http import Controller, request, route
from odoo.tools import html_escape
from odoo.tools.misc import format_date

from ..models import s3

_logger = logging.getLogger(__name__)

HONEYPOT_FIELD = "website_url"

# Tokens are uuid4().hex generated server-side: exactly 32 lowercase hex chars.
# Anything else is rejected before touching the database.
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


# ── Client identification ─────────────────────────────────────────────────────

def _client_ip():
    """Return the real client IP, honoring X-Real-IP / X-Forwarded-For.

    Odoo's proxy_mode applies ProxyFix at the WSGI layer, but that rewrite only
    fires when the raw REMOTE_ADDR matches a trusted proxy. Reading the headers
    ourselves (first hop only) keeps the rate-limit buckets per-client instead
    of per-proxy, mirroring bf_sign.
    """
    try:
        env = request.httprequest.environ
        for key in ("HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR"):
            value = env.get(key, "")
            if value:
                return value.split(",")[0].strip()
        return request.httprequest.remote_addr or "unknown"
    except Exception:
        return "unknown"


def _user_agent():
    try:
        return request.httprequest.headers.get("User-Agent", "")[:512]
    except Exception:
        return ""


# ── In-memory rate limiting ───────────────────────────────────────────────────

class _SlidingWindowLimiter:
    """Per-worker sliding-window event counter (Lock + defaultdict, bf_sign
    pattern). Good enough for burst control; the daily quotas that must be
    exact across workers are DB-backed in secure.transfer.
    """

    def __init__(self, window_seconds):
        self._lock = threading.Lock()
        self._data = defaultdict(list)
        self._window = window_seconds

    def check(self, key, max_events):
        """True when `key` is still under `max_events` in the window."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - self._window
            events = [t for t in self._data[key] if t > cutoff]
            self._data[key] = events
            return len(events) < max_events

    def hit(self, key):
        """Record one event for `key`."""
        with self._lock:
            self._data[key].append(time.monotonic())

    def consume(self, key, max_events):
        """Atomic check-and-record. True when the event was allowed."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - self._window
            events = [t for t in self._data[key] if t > cutoff]
            if len(events) >= max_events:
                self._data[key] = events
                return False
            events.append(now)
            self._data[key] = events
            return True


# Transfer creation (and finalize, same budget size): max per hour per IP,
# ceiling read from ir.config_parameter at request time.
_create_limiter = _SlidingWindowLimiter(3600)
_finalize_limiter = _SlidingWindowLimiter(3600)

# Failed token lookups (fuzzing): uniform 404s once the budget is burnt.
_token_fail_limiter = _SlidingWindowLimiter(300)
_TOKEN_FAIL_MAX = 20

# Failed password attempts, keyed by (IP, transfer).
_password_fail_limiter = _SlidingWindowLimiter(900)
_PASSWORD_FAIL_MAX = 8

# Abuse reports: 5 per day per IP.
_report_limiter = _SlidingWindowLimiter(86400)
_REPORT_MAX = 5

# Recipient OTP verification attempts, keyed by (IP, transfer).
_otp_fail_limiter = _SlidingWindowLimiter(900)
_OTP_FAIL_MAX = 8

# Upload plumbing (register/presign/multipart/remove): 120/min/IP across the
# whole set — anti presign-farming (plan §Table des routes).
_upload_ops_limiter = _SlidingWindowLimiter(60)
_UPLOAD_OPS_MAX = 120


def _rate_create_max(env):
    try:
        return max(1, int(s3.param(env, "rate_create_per_hour", "10")))
    except (TypeError, ValueError):
        return 10


def _upload_enabled(env):
    """Kill-switch: bf_securetransfer.public_upload_enabled (default on)."""
    value = (s3.param(env, "public_upload_enabled", "1") or "").strip().lower()
    return value in ("1", "true", "yes")


# ── Token resolution ──────────────────────────────────────────────────────────

def _resolve_transfer_by_upload_token(ut):
    """upload_token → sudoed secure.transfer, or None (counted as a failure).

    The search is an indexed exact match; compare_digest re-checks the value in
    constant time on the candidate row.
    """
    ip = _client_ip()
    if not _token_fail_limiter.check(ip, _TOKEN_FAIL_MAX):
        _logger.warning("bf_securetransfer: token rate limit exceeded for IP %s", ip)
        return None
    if not ut or not _TOKEN_RE.match(ut):
        _token_fail_limiter.hit(ip)
        return None
    transfer = request.env["secure.transfer"].sudo().search(
        [("upload_token", "=", ut)], limit=1)
    if not transfer or not transfer.upload_token \
            or not hmac.compare_digest(transfer.upload_token, ut):
        _token_fail_limiter.hit(ip)
        return None
    return transfer


def _resolve_transfer_by_token(token):
    """Share token → sudoed secure.transfer, or None (counted as a failure)."""
    ip = _client_ip()
    if not _token_fail_limiter.check(ip, _TOKEN_FAIL_MAX):
        _logger.warning("bf_securetransfer: token rate limit exceeded for IP %s", ip)
        return None
    if not token or not _TOKEN_RE.match(token):
        _token_fail_limiter.hit(ip)
        return None
    transfer = request.env["secure.transfer"].sudo().search(
        [("token", "=", token)], limit=1)
    if not transfer or not transfer.token \
            or not hmac.compare_digest(transfer.token, token):
        _token_fail_limiter.hit(ip)
        return None
    return transfer


# ── Security headers ──────────────────────────────────────────────────────────

def _apply_security_headers(response, s3_host=None, img_host=None):
    """Add the CSP + anti-framing headers to a rendered response.

    `s3_host` (a space-separated origin list) is appended to connect-src on
    the upload page only: the browser PUTs go straight to S3 and would be
    blocked otherwise. Every other page keeps connect-src 'self'.
    `img_host` (an origin) is appended to img-src so a brand logo hosted on
    another domain (appointment_brand_logo_url) can load.
    """
    try:
        headers = response.headers
    except AttributeError:
        return response
    connect_src = "'self'"
    if s3_host:
        connect_src += " " + s3_host
    img_src = "'self' data:"
    if img_host:
        img_src += " " + img_host
    headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "img-src %s; "
        "font-src 'self'; "
        "connect-src %s; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self'" % (img_src, connect_src)
    )
    headers["X-Frame-Options"] = "DENY"
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _s3_connect_origins(env):
    """Origins to whitelist in connect-src on the upload page.

    Derived from config parameters only (no credentials needed, so the page
    still renders when the S3 key is not deployed yet). Covers both path-style
    and virtual-host-style presigned URLs.
    """
    endpoint = (s3.param(env, "s3_endpoint_url", "") or "").strip()
    if not endpoint:
        return ""
    parsed = urlparse(endpoint if "://" in endpoint else "https://" + endpoint)
    if not parsed.netloc:
        return ""
    scheme = parsed.scheme or "https"
    origins = ["%s://%s" % (scheme, parsed.netloc)]
    path_style = (s3.param(env, "s3_path_style", "1") or "1").strip().lower()
    bucket = (s3.param(env, "s3_bucket", "") or "").strip()
    if path_style not in ("1", "true", "yes") and bucket:
        origins.insert(0, "%s://%s.%s" % (scheme, bucket, parsed.netloc))
    return " ".join(origins)


# ── Locale ────────────────────────────────────────────────────────────────────

# The product ships fr_CA (source) and en_CA. Anything en* maps to en_CA when
# installed, everything else falls back to fr_CA (bf_appointment pattern).
_DEFAULT_LANG = "fr_CA"


def _resolve_locale(env=None):
    """Accept-Language → installed lang code (fr_CA default)."""
    env = env if env is not None else request.env
    try:
        header = request.httprequest.headers.get("Accept-Language", "")
    except Exception:
        return _DEFAULT_LANG
    first = (header.split(",")[0].split(";")[0] or "").strip().lower()
    lang = "en_CA" if first.startswith("en") else _DEFAULT_LANG
    if lang != _DEFAULT_LANG:
        installed = env["res.lang"].sudo().search(
            [("code", "=", lang), ("active", "=", True)], limit=1)
        if not installed:
            lang = _DEFAULT_LANG
    return lang


def _apply_locale():
    """Resolve the visitor locale and push it into the request context."""
    lang = _resolve_locale()
    if request.env.context.get("lang") != lang:
        request.update_context(lang=lang)
    return lang


# ── Client-side extension mirror ──────────────────────────────────────────────

# The authoritative deny-list check lives in secure.transfer.file
# (_register_file). The upload page mirrors it client-side for instant
# feedback; import the model constant so the two never drift, with a verbatim
# fallback (bf_survey_upload list) as a safety net.
_FALLBACK_DENY_EXTENSIONS = frozenset(
    {
        # Browser-renderable / XSS vectors
        "html", "htm", "xhtml", "svg", "svgz", "mhtml", "mht",
        "js", "mjs", "wasm",
        # Server-side execution (defense in depth — should never reach a handler)
        "php", "php3", "php4", "php5", "php7", "phps", "phtml", "pht",
        "asp", "aspx", "ashx", "cer",
        "jsp", "jspx", "jsv", "jspf",
        "cgi", "pl", "py", "rb", "lua",
        "swf",
        "class", "jar", "war", "ear",
        # Native executables and scripts
        "exe", "bat", "cmd", "com", "ps1", "psm1", "sh", "bash", "zsh",
        "msi", "dll", "scr", "vbs", "vbe", "jse", "wsf", "wsh", "hta",
        "lnk", "reg", "chm",
        # Web server config that could be honored if dropped in served paths
        "htaccess", "htpasswd",
    }
)


def _deny_extensions():
    try:
        from ..models.secure_transfer_file import DENY_EXTENSIONS
        return sorted(DENY_EXTENSIONS)
    except ImportError:
        return sorted(_FALLBACK_DENY_EXTENSIONS)


# ── UI strings (shipped to st_upload.js through #st-config) ───────────────────

# Deliberately not _() calls: the upload page picks the whole set by locale so
# the JS never depends on the server gettext catalogs.
_UI_STRINGS = {
    "fr_CA": {
        "units": ["o", "Ko", "Mo", "Go", "To"],
        "add_error_ext_missing": "« %(name)s » : le fichier doit avoir une extension.",
        "add_error_ext_denied": "« %(name)s » : le format .%(ext)s n'est pas autorisé pour des raisons de sécurité.",
        "add_error_too_large": "« %(name)s » dépasse la taille maximale (%(max)s).",
        "add_error_total": "Taille totale maximale dépassée (%(max)s).",
        "add_error_count": "Nombre maximal de fichiers atteint (%(max)s).",
        "email_required": "Indiquez votre adresse courriel pour envoyer.",
        "email_invalid": "Adresse courriel invalide.",
        "message_required": "Saisissez un message à envoyer.",
        "recipients_invalid": "Adresse de destinataire invalide : %(email)s",
        "recipients_too_many": "Maximum %(max)s destinataires.",
        "message_too_long": "Le message dépasse %(max)s caractères.",
        "status_blocked": "En attente de votre courriel…",
        "status_waiting": "En attente…",
        "status_uploading": "Téléversement…",
        "status_done": "Téléversé",
        "status_error": "Échec",
        "retrying": "Nouvelle tentative %(n)s de %(max)s…",
        "error_generic": "Une erreur est survenue. Veuillez réessayer.",
        "error_network": "Erreur réseau. Vérifiez votre connexion.",
        "uploads_in_progress": "Attendez la fin des téléversements avant d'envoyer.",
        "no_files": "Ajoutez au moins un fichier.",
        "remove": "Retirer",
        "resume": "Reprendre",
        "resume_title": "Transfert interrompu détecté",
        "resume_hint": "Re-sélectionnez « %(name)s » pour reprendre le téléversement.",
        "resume_mismatch": "Le fichier sélectionné ne correspond pas (nom ou taille différents).",
        "resume_gone": "Le transfert interrompu n'est plus disponible. Recommencez.",
        "expiry_one_day": "1 jour",
        "expiry_days": "%(n)s jours",
        "copy": "Copier le lien",
        "copied": "Lien copié !",
        "finalizing": "Vérification des fichiers…",
        "send": "Obtenir le lien",
        "send_message": "Envoyer le message",
    },
    "en_CA": {
        "units": ["B", "KB", "MB", "GB", "TB"],
        "add_error_ext_missing": "“%(name)s”: the file must have an extension.",
        "add_error_ext_denied": "“%(name)s”: the .%(ext)s format is not allowed for security reasons.",
        "add_error_too_large": "“%(name)s” exceeds the maximum size (%(max)s).",
        "add_error_total": "Maximum total size exceeded (%(max)s).",
        "add_error_count": "Maximum number of files reached (%(max)s).",
        "email_required": "Enter your email address to send.",
        "email_invalid": "Invalid email address.",
        "message_required": "Enter a message to send.",
        "recipients_invalid": "Invalid recipient address: %(email)s",
        "recipients_too_many": "Maximum %(max)s recipients.",
        "message_too_long": "The message exceeds %(max)s characters.",
        "status_blocked": "Waiting for your email…",
        "status_waiting": "Waiting…",
        "status_uploading": "Uploading…",
        "status_done": "Uploaded",
        "status_error": "Failed",
        "retrying": "Retry %(n)s of %(max)s…",
        "error_generic": "Something went wrong. Please try again.",
        "error_network": "Network error. Check your connection.",
        "uploads_in_progress": "Wait for the uploads to finish before sending.",
        "no_files": "Add at least one file.",
        "remove": "Remove",
        "resume": "Resume",
        "resume_title": "Interrupted transfer detected",
        "resume_hint": "Re-select “%(name)s” to resume the upload.",
        "resume_mismatch": "The selected file does not match (different name or size).",
        "resume_gone": "The interrupted transfer is no longer available. Start over.",
        "expiry_one_day": "1 day",
        "expiry_days": "%(n)s days",
        "copy": "Copy link",
        "copied": "Link copied!",
        "finalizing": "Verifying files…",
        "send": "Get the link",
        "send_message": "Send the message",
    },
}


def _st_config(env, limits, locale):
    """Build the JSON block consumed by st_upload.js. No server constant is
    hardcoded in the JS: everything it needs travels through here."""
    def _int_param(key, default):
        try:
            return int(s3.param(env, key, str(default)))
        except (TypeError, ValueError):
            return default

    return {
        "locale": locale,
        "api": {
            "create": "/secrets/api/create",
            "transfer_base": "/secrets/api/",
        },
        "limits": limits,
        "multipart": {
            "threshold_bytes": _int_param("multipart_threshold_mb", 64) * 1024 * 1024,
            "sign_batch_max": max(1, _int_param("mpu_sign_batch_max", 20)),
            "concurrency": 3,
        },
        "deny_extensions": _deny_extensions(),
        "max_recipients": 10,
        "max_message_chars": 2000,
        "honeypot_field": HONEYPOT_FIELD,
        "strings": _UI_STRINGS.get(locale, _UI_STRINGS[_DEFAULT_LANG]),
    }


def _notify_abuse_managers(transfer, reason, ip):
    """Open a To-Do activity on the transfer for every manager: suspending a
    reported transfer is a human decision, made from the backend."""
    env = request.env
    group = env.ref("bf_securetransfer.group_securetransfer_manager",
                    raise_if_not_found=False)
    users = group.sudo().users.filtered("active") if group else env["res.users"].sudo().browse()
    if not users:
        admin = env.ref("base.user_admin", raise_if_not_found=False)
        users = admin.sudo() if admin else users
    if not users:
        return
    model_id = env["ir.model"].sudo()._get_id("secure.transfer")
    activity_type = env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
    # html_escape returns Markup, so the later concatenations escape the
    # user-supplied reason exactly once.
    body = html_escape(_(
        "Signalement d'abus reçu pour le transfert %(name)s (IP : %(ip)s).",
        name=transfer.name, ip=ip))
    if reason:
        body += Markup("<br/>") + _("Motif :") + " " + reason
    for user in users:
        env["mail.activity"].sudo().create({
            "res_model_id": model_id,
            "res_id": transfer.id,
            "activity_type_id": activity_type.id if activity_type else False,
            "user_id": user.id,
            "summary": _("Signalement d'abus — %s", transfer.name),
            "note": Markup("<p>%s</p>") % body,
            "date_deadline": fields.Date.context_today(transfer),
        })


class SecureTransferController(Controller):

    # ── Upload page ───────────────────────────────────────────────────────────
    @route("/secrets", type="http", auth="public", methods=["GET"], sitemap=False)
    def st_upload_page(self, **kw):
        locale = _apply_locale()
        env = request.env
        brand = env["secure.transfer.brand"].sudo()._from_request()
        visuals = brand._visuals()
        if not _upload_enabled(env):
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": _("Le service de transfert est temporairement indisponible."),
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        limits = brand._effective_limits()
        config = _st_config(env, limits, locale)
        # Markup so QWeb t-out emits raw JSON inside the #st-config script tag
        # (t-esc would HTML-encode the quotes and break JSON.parse). The payload
        # is entirely server-built — no user-controlled content.
        config_json = Markup(
            json.dumps(config, ensure_ascii=False).replace("</", "<\\/"))
        response = request.render("bf_securetransfer.page_upload", {
            "brand": brand,
            "visuals": visuals,
            "limits": limits,
            "locale": locale,
            "st_config_json": config_json,
            "drop_mode": False,
            "drop_recipient_label": "",
        })
        return _apply_security_headers(response, s3_host=_s3_connect_origins(env), img_host=visuals.get("logo_host"))

    # ── Slug-addressed public page (/to/<slug>) ──────────────────────────────
    @route("/to/<string:slug>", type="http", auth="public", methods=["GET"],
           sitemap=False)
    def st_drop_page(self, slug, **kw):
        """A slug-addressed public page for one brand. When the brand carries a
        fixed_recipient it is a drop page: the recipient field is hidden and the
        server forces the destination on create and finalize. Otherwise it is an
        ordinary upload page — free sender, free recipients — just reached by
        slug instead of by Host."""
        locale = _apply_locale()
        env = request.env
        brand = env["secure.transfer.brand"].sudo()._resolve_for_slug(slug)
        if not brand:
            return request.not_found()
        visuals = brand._visuals()
        if not _upload_enabled(env):
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": _("Le service de transfert est temporairement indisponible."),
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        limits = brand._effective_limits()
        config = _st_config(env, limits, locale)
        config["drop_slug"] = brand.slug
        config_json = Markup(
            json.dumps(config, ensure_ascii=False).replace("</", "<\\/"))
        drop_mode = bool(brand.fixed_recipient)
        response = request.render("bf_securetransfer.page_upload", {
            "brand": brand,
            "visuals": visuals,
            "limits": limits,
            "locale": locale,
            "st_config_json": config_json,
            "drop_mode": drop_mode,
            "drop_recipient_label":
                brand._drop_recipient_label() if drop_mode else "",
        })
        return _apply_security_headers(response, s3_host=_s3_connect_origins(env), img_host=visuals.get("logo_host"))

    # ── Download page ─────────────────────────────────────────────────────────
    @route("/s/<string:token>", type="http", auth="public", methods=["GET"],
           sitemap=False)
    def st_download_page(self, token, **kw):
        locale = _apply_locale()
        transfer = _resolve_transfer_by_token(token)
        # Drafts (and harvested drafts) never had a live link: uniform 404.
        if transfer is None or transfer.state in ("draft", "cancelled"):
            return request.not_found()
        brand = transfer.brand_id
        visuals = brand._visuals()
        ip, ua = _client_ip(), _user_agent()
        available, reason = transfer._is_available()
        if not available:
            transfer._log("expired_hit", ip=ip, ua=ua, note=reason)
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": False,
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        expiry_display = format_date(
            request.env, transfer.expiry_date, lang_code=transfer.locale,
        ) if transfer.expiry_date else ""
        if transfer.has_password \
                and not request.session.get("st_unlock_%d" % transfer.id):
            response = request.render("bf_securetransfer.page_download", {
                "brand": brand, "visuals": visuals, "transfer": transfer,
                "files": transfer.file_ids.browse(), "token": token,
                "locked": True, "pw_error": kw.get("pw_error"),
                "reported": kw.get("reported"), "locale": locale,
                "expiry_display": expiry_display, "otp_stage": False,
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        # Recipient OTP gate (per-transfer force OR tenant setting): after the
        # password, before the message body and files are ever rendered.
        if transfer._recipient_otp_required() \
                and not request.session.get("st_otp_ok_%d" % transfer.id):
            response = request.render("bf_securetransfer.page_download", {
                "brand": brand, "visuals": visuals, "transfer": transfer,
                "files": transfer.file_ids.browse(), "token": token,
                "locked": False, "pw_error": False,
                "reported": kw.get("reported"), "locale": locale,
                "expiry_display": expiry_display,
                "otp_stage": request.session.get("st_otp_sent_%d" % transfer.id)
                and "verify" or "request",
                "otp_error": kw.get("otp_error"),
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        transfer._log("view", ip=ip, ua=ua)
        files = transfer.file_ids.filtered(
            lambda f: f.state == "verified" and f.scanned in ("none", "clean"))
        response = request.render("bf_securetransfer.page_download", {
            "brand": brand, "visuals": visuals, "transfer": transfer,
            "files": files, "token": token, "locked": False,
            "pw_error": False, "reported": kw.get("reported"),
            "locale": locale, "expiry_display": expiry_display,
            "otp_stage": False,
        })
        return _apply_security_headers(response, img_host=visuals.get("logo_host"))

    # ── Recipient OTP gate (tenant setting) ───────────────────────────────────
    @route("/s/<string:token>/otp-request", type="http", auth="public",
           methods=["POST"], csrf=False, sitemap=False)
    def st_otp_request(self, token, **post):
        _apply_locale()
        transfer = _resolve_transfer_by_token(token)
        if transfer is None or transfer.state in ("draft", "cancelled"):
            return request.not_found()
        if not transfer._recipient_otp_required() or not transfer._is_available()[0]:
            return request.redirect("/s/%s" % token, code=303)
        ip, ua = _client_ip(), _user_agent()
        if not _otp_fail_limiter.check("%s:%s" % (ip, transfer.id), _OTP_FAIL_MAX):
            return request.redirect("/s/%s?otp_error=2" % token, code=303)
        # A blank email is a "resend" from the verify stage — reuse the address
        # already confirmed as a recipient in this session.
        email = (post.get("email") or "").strip()
        if not email:
            email = (request.session.get("st_otp_chal_%d" % transfer.id) or {}).get("email", "")
        otp_hash, expiry = transfer.send_recipient_otp(email, ip=ip, ua=ua)
        if not otp_hash:
            _otp_fail_limiter.hit("%s:%s" % (ip, transfer.id))
            return request.redirect("/s/%s?otp_error=1" % token, code=303)
        request.session["st_otp_chal_%d" % transfer.id] = {
            "hash": otp_hash,
            "expiry": fields.Datetime.to_string(expiry),
            "email": email,
        }
        request.session["st_otp_sent_%d" % transfer.id] = True
        return request.redirect("/s/%s" % token, code=303)

    @route("/s/<string:token>/otp-verify", type="http", auth="public",
           methods=["POST"], csrf=False, sitemap=False)
    def st_otp_verify(self, token, **post):
        _apply_locale()
        transfer = _resolve_transfer_by_token(token)
        if transfer is None or transfer.state in ("draft", "cancelled"):
            return request.not_found()
        ip, ua = _client_ip(), _user_agent()
        key = "%s:%s" % (ip, transfer.id)
        if not _otp_fail_limiter.check(key, _OTP_FAIL_MAX):
            return request.redirect("/s/%s?otp_error=2" % token, code=303)
        chal = request.session.get("st_otp_chal_%d" % transfer.id) or {}
        code = (post.get("code") or "").strip()
        expiry = chal.get("expiry")
        expired = (not expiry) or fields.Datetime.from_string(expiry) < fields.Datetime.now()
        Model = transfer.env["secure.transfer"].sudo()
        if chal.get("hash") and not expired \
                and hmac.compare_digest(chal["hash"], Model._otp_hash(code)):
            request.session["st_otp_ok_%d" % transfer.id] = True
            request.session.pop("st_otp_chal_%d" % transfer.id, None)
            request.session.pop("st_otp_sent_%d" % transfer.id, None)
            transfer._log("otp_ok", actor=chal.get("email"), ip=ip, ua=ua,
                          note=_("Destinataire confirmé par code"))
            return request.redirect("/s/%s" % token, code=303)
        _otp_fail_limiter.hit(key)
        transfer._log("otp_fail", actor=chal.get("email"), ip=ip, ua=ua)
        return request.redirect("/s/%s?otp_error=1" % token, code=303)

    # ── Password gate ─────────────────────────────────────────────────────────
    # csrf=False is safe here: the route is only reachable with the 128-bit
    # link token, the password attempt is rate-limited per (IP, transfer), and
    # a successful unlock only sets a session flag scoped to this transfer.
    @route("/s/<string:token>/unlock", type="http", auth="public",
           methods=["POST"], csrf=False, sitemap=False)
    def st_unlock(self, token, **post):
        _apply_locale()
        transfer = _resolve_transfer_by_token(token)
        if transfer is None or transfer.state in ("draft", "cancelled"):
            return request.not_found()
        available = transfer._is_available()[0]
        if not available or not transfer.has_password:
            # Nothing to unlock: let the GET page explain the state.
            return request.redirect("/s/%s" % token, code=303)
        ip, ua = _client_ip(), _user_agent()
        key = "%s:%s" % (ip, transfer.id)
        if not _password_fail_limiter.check(key, _PASSWORD_FAIL_MAX):
            _logger.warning(
                "bf_securetransfer: password rate limit hit for %s on %s",
                ip, transfer.name)
            return request.redirect("/s/%s?pw_error=2" % token, code=303)
        password = post.get("password") or ""
        if transfer._check_password(password):
            request.session["st_unlock_%d" % transfer.id] = True
            transfer._log("password_ok", ip=ip, ua=ua)
            return request.redirect("/s/%s" % token, code=303)
        _password_fail_limiter.hit(key)
        transfer._log("password_fail", ip=ip, ua=ua)
        return request.redirect("/s/%s?pw_error=1" % token, code=303)

    # ── Download (302 to presigned GET) ───────────────────────────────────────
    @route("/s/<string:token>/dl/<int:file_id>", type="http", auth="public",
           methods=["GET"], sitemap=False)
    def st_download_file(self, token, file_id, **kw):
        locale = _apply_locale()
        transfer = _resolve_transfer_by_token(token)
        if transfer is None or transfer.state in ("draft", "cancelled"):
            return request.not_found()
        brand = transfer.brand_id
        visuals = brand._visuals()
        ip, ua = _client_ip(), _user_agent()
        available, reason = transfer._is_available()
        if not available:
            transfer._log("expired_hit", ip=ip, ua=ua, note=reason)
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": False,
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        if transfer.has_password \
                and not request.session.get("st_unlock_%d" % transfer.id):
            return request.redirect("/s/%s" % token, code=303)
        # Recipient OTP gate: no download without a verified session.
        if transfer._recipient_otp_required() \
                and not request.session.get("st_otp_ok_%d" % transfer.id):
            return request.redirect("/s/%s" % token, code=303)
        rec_file = transfer.file_ids.filtered(
            lambda f: f.id == file_id and f.state == "verified"
            and f.scanned in ("none", "clean"))[:1]
        if not rec_file:
            return request.not_found()
        # Integrity re-check before every download: the ETag pinned at
        # finalize must still match the object. Blocks the "re-PUT malware
        # with a still-valid presign" attack.
        try:
            head = s3.head_object(request.env, rec_file.s3_key)
        except Exception:
            _logger.exception(
                "bf_securetransfer: S3 HEAD failed for %s", transfer.name)
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": _("Le téléchargement est temporairement indisponible. "
                             "Réessayez plus tard."),
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        if not head or not rec_file.etag or head.get("etag") != rec_file.etag:
            transfer._log("integrity_mismatch", file=rec_file, ip=ip, ua=ua,
                          note=rec_file.filename)
            _logger.error(
                "bf_securetransfer: integrity mismatch on %s / file #%s "
                "(stored etag %s, live %s)", transfer.name, rec_file.id,
                rec_file.etag, head and head.get("etag"))
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": _("Ce fichier n'est plus disponible : son intégrité "
                             "n'a pas pu être vérifiée."),
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        try:
            url = rec_file.presign_download()
        except Exception:
            _logger.exception(
                "bf_securetransfer: presign GET failed for %s", transfer.name)
            response = request.render("bf_securetransfer.page_unavailable", {
                "brand": brand, "visuals": visuals, "locale": locale,
                "message": _("Le téléchargement est temporairement indisponible. "
                             "Réessayez plus tard."),
            })
            return _apply_security_headers(response, img_host=visuals.get("logo_host"))
        # _register_download logs the download event itself (choke-point).
        transfer._register_download(rec_file, ip, ua)
        return request.redirect(url, code=302, local=False)

    # ── Abuse report ──────────────────────────────────────────────────────────
    # csrf=False is safe here: the route requires the 128-bit link token, is
    # rate-limited per IP, and its only effect is a log entry + an internal
    # activity — nothing an attacker gains by forging it cross-origin.
    @route("/s/<string:token>/report", type="http", auth="public",
           methods=["POST"], csrf=False, sitemap=False)
    def st_report(self, token, **post):
        _apply_locale()
        transfer = _resolve_transfer_by_token(token)
        if transfer is None or transfer.state in ("draft", "cancelled"):
            return request.not_found()
        ip, ua = _client_ip(), _user_agent()
        # Over-quota reports are silently dropped but still acknowledged, so
        # the limiter cannot be probed from the outside.
        if _report_limiter.consume(ip, _REPORT_MAX):
            reason = (post.get("reason") or "").strip()[:500]
            transfer._log("abuse_report", ip=ip, ua=ua, note=reason or None)
            # Auto-suspend immediately: the link goes dark and stays dark until
            # an admin reactivates (false report) or purges (confirmed abuse).
            transfer._suspend_for_abuse(ip=ip, ua=ua)
            try:
                _notify_abuse_managers(transfer, reason, ip)
            except Exception:
                _logger.exception(
                    "bf_securetransfer: abuse activity creation failed for %s",
                    transfer.name)
            try:
                transfer._send_abuse_notice(reason=reason, ip=ip)
            except Exception:
                _logger.exception(
                    "bf_securetransfer: abuse notice email failed for %s",
                    transfer.name)
        else:
            _logger.info(
                "bf_securetransfer: abuse report rate limit hit for IP %s", ip)
        return request.redirect("/s/%s?reported=1" % token, code=303)
