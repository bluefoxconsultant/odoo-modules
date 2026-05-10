"""Settings page for bf_email_management IMAP credentials.

Surfaces the four `bf_email.imap_*` `ir.config_parameter` rows in the
standard Settings page (Settings → Inbox unifiée) so new installs and ops
folks no longer need to edit Technical → Parameters → System Parameters by
hand. Includes a "Tester la connexion" button that opens an IMAP4_SSL session
with the saved credentials and reports the LIST result + INBOX count.
"""

import logging
import socket
import ssl

from odoo import _, api, exceptions, fields, models

from . import bf_email_imap

_logger = logging.getLogger(__name__)

_PARAM_KEYS = {
    "bf_email_imap_host": "bf_email.imap_host",
    "bf_email_imap_port": "bf_email.imap_port",
    "bf_email_imap_user": "bf_email.imap_user",
    "bf_email_imap_password": "bf_email.imap_password",
    "bf_email_imap_writeback_archive": "bf_email.imap_writeback_archive",
    "bf_email_imap_archive_folder": "bf_email.imap_archive_folder",
    "bf_email_imap_batch_size": "bf_email.imap_batch_size",
    "bf_email_auto_link_threshold_days": "bf_email.auto_link_threshold_days",
}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bf_email_imap_host = fields.Char(
        string="Serveur IMAP",
        config_parameter="bf_email.imap_host",
        help="Nom d'hôte du serveur IMAP (ex. imap.example.com).",
    )
    bf_email_imap_port = fields.Integer(
        string="Port IMAP",
        config_parameter="bf_email.imap_port",
        default=993,
        help="993 pour IMAP4_SSL (recommandé). Aucun support STARTTLS.",
    )
    bf_email_imap_user = fields.Char(
        string="Utilisateur IMAP",
        config_parameter="bf_email.imap_user",
        help="Adresse de connexion (ex. you@example.com).",
    )
    bf_email_imap_password = fields.Char(
        string="Mot de passe IMAP",
        config_parameter="bf_email.imap_password",
        help="Mot de passe d'application. Stocké en clair dans "
             "ir.config_parameter (groupe Settings restreint).",
    )
    bf_email_imap_writeback_archive = fields.Boolean(
        string="Archivage bilatéral",
        config_parameter="bf_email.imap_writeback_archive",
        default=True,
        help="Si activé, archiver une ligne dans Odoo COPY+EXPUNGE le "
             "courriel sur le serveur IMAP vers le dossier configuré.",
    )
    bf_email_imap_archive_folder = fields.Char(
        string="Dossier d'archives IMAP",
        config_parameter="bf_email.imap_archive_folder",
        default="Archives/{YYYY}",
        help="Gabarit de dossier IMAP cible. {YYYY} est remplacé par "
             "l'année du courriel.",
    )
    bf_email_imap_batch_size = fields.Integer(
        string="Taille de lot IMAP",
        config_parameter="bf_email.imap_batch_size",
        default=100,
        help="Nombre de UIDs traités par exécution du cron de synchronisation.",
    )
    bf_email_auto_link_threshold_days = fields.Integer(
        string="Auto-lien : fenêtre (jours)",
        config_parameter="bf_email.auto_link_threshold_days",
        default=14,
        help="Le cron auto-link lie une ligne IMAP orpheline à la seule "
             "tâche / ticket ouvert du contact si elle est postée dans cette "
             "fenêtre (jours).",
    )

    def action_bf_email_test_imap(self):
        """Open an IMAP4_SSL session with the saved credentials and report.

        Reports SELECT INBOX message count + the list of folders. Designed
        as a one-shot dry run — does not modify anything, does not advance
        the UID watermarks, does not ingest any message.
        """
        self.ensure_one()
        host = self.bf_email_imap_host or ""
        port = self.bf_email_imap_port or 993
        user = self.bf_email_imap_user or ""
        password = self.bf_email_imap_password or ""

        if not (host and user and password):
            raise exceptions.UserError(_(
                "Veuillez renseigner serveur, utilisateur et mot de passe "
                "avant de tester la connexion."
            ))

        try:
            conn = bf_email_imap.open_connection(host, port, user, password)
        except (socket.gaierror, OSError) as exc:
            raise exceptions.UserError(_(
                "Impossible de joindre %(host)s:%(port)s — %(err)s",
                host=host, port=port, err=exc,
            )) from exc
        except ssl.SSLError as exc:
            raise exceptions.UserError(_(
                "Erreur TLS : %(err)s", err=exc,
            )) from exc
        except Exception as exc:
            raise exceptions.UserError(_(
                "Échec de l'authentification IMAP : %(err)s", err=exc,
            )) from exc

        try:
            status, count_data = conn.select("INBOX", readonly=True)
            inbox_count = int(count_data[0]) if status == "OK" and count_data else 0

            list_status, folders_raw = conn.list()
            folders = []
            if list_status == "OK" and folders_raw:
                for raw in folders_raw:
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
                    # Standard IMAP LIST line: (\HasChildren) "/" "Folder"
                    parts = line.rsplit('"', 2)
                    if len(parts) >= 2:
                        folders.append(parts[-2])
                    else:
                        folders.append(line)
        finally:
            try:
                conn.logout()
            except Exception:  # pragma: no cover (defensive)
                pass

        folder_list = ", ".join(folders[:25])
        if len(folders) > 25:
            folder_list += _(" (… +%(more)s autres)", more=len(folders) - 25)

        message = _(
            "Connexion réussie à %(host)s:%(port)s en tant que "
            "%(user)s.\n\nINBOX : %(count)s messages.\n\n"
            "Dossiers détectés (%(total)s) : %(folders)s"
        ) % {
            "host": host,
            "port": port,
            "user": user,
            "count": inbox_count,
            "total": len(folders),
            "folders": folder_list or _("(aucun)"),
        }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Connexion IMAP OK"),
                "message": message,
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
