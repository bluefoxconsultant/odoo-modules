"""Regression tests for the 18.0.1.6.2 fixes.

Each test here corresponds to a defect that reached production. The docstrings
say what breaks when the test fails, because that is the part a future reader
needs — the assertion itself is easy to re-derive, the reason it exists is not.

S3 is patched throughout on ``odoo.addons.bf_securetransfer.models.s3``: the
suite runs without boto3 and without any reachable endpoint.

NB on style: several tests use plain ``try/except`` instead of
``assertRaises``. That is deliberate. Odoo's ``assertRaises`` wraps its block
in a savepoint with ``flush=False`` and rolls it back, which also discards
records the test created — it will make a passing counter look like a failing
one.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

S3_MOD = "odoo.addons.bf_securetransfer.models.s3"


@tagged("post_install", "-at_install")
class TestRegressions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env.ref("bf_securetransfer.brand_default")
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("bf_securetransfer.quota_daily_transfers_per_ip", "500")
        icp.set_param("bf_securetransfer.quota_daily_transfers_per_sender", "500")
        icp.set_param("bf_securetransfer.quota_daily_bytes_per_ip_mb", "1000000")

    def _create(self, **overrides):
        vals = {
            "sender_name": "Test Sender",
            "sender_email": "sender@example.com",
            "recipient_emails": "dest@example.com",
            "message": "Bonjour",
            "retention_days": 7,
        }
        vals.update(overrides)
        return self.env["secure.transfer"].api_create(
            self.brand, vals, "203.0.113.10", "test-suite/1.0", "fr_CA",
        )

    def _head_for(self, transfer):
        sizes = {f.s3_key: int(f.size) for f in transfer.file_ids}

        def _head(env, key):
            if key in sizes:
                return {"size": sizes[key], "etag": "etag-" + key[-8:]}
            return None
        return _head

    def _finalize(self, transfer):
        with patch(S3_MOD + ".head_object", side_effect=self._head_for(transfer)), \
                patch("odoo.addons.mail.models.mail_mail.MailMail.send",
                      lambda self, *a, **k: True):
            transfer.action_finalize()
        return transfer

    # ---------------------------------------------------------------- burn
    def _burning(self, count=2):
        t = self._create()
        t.burn_after_download = True
        for i in range(count):
            t._register_file("doc%d.pdf" % i, 4096)
        return self._finalize(t)

    def test_burn_waits_for_every_file(self):
        """A browser fetches one file per request. Burning on the first
        download stranded every remaining attachment behind a dead link — the
        recipient got file 1 of N and nothing else."""
        t = self._burning(2)
        first, second = t.file_ids[0], t.file_ids[1]
        t._register_download(first, "203.0.113.99", "dl-agent")
        self.assertEqual(t.state, "active")
        self.assertEqual(t._is_available(), (True, ""))
        t._register_download(second, "203.0.113.99", "dl-agent")
        self.assertEqual(t.state, "expired")

    def test_burn_single_file_still_immediate(self):
        """Guard against over-correcting: a one-file transfer must still burn
        on its only download."""
        t = self._burning(1)
        t._register_download(t.file_ids, "203.0.113.99", "dl-agent")
        self.assertEqual(t.state, "expired")

    def test_burn_ignores_undownloadable_files(self):
        """A file that was never offered (scanner hit, upload error) must not
        hold the burn open forever."""
        t = self._burning(2)
        t.file_ids[1].scanned = "infected"
        t._register_download(t.file_ids[0], "203.0.113.99", "dl-agent")
        self.assertEqual(t.state, "expired")

    def test_burn_repeat_download_does_not_burn_early(self):
        """Re-fetching the same file (an interrupted download, retried) is not
        evidence that the other file was collected."""
        t = self._burning(2)
        first = t.file_ids[0]
        t._register_download(first, "203.0.113.99", "dl-agent")
        t._register_download(first, "203.0.113.99", "dl-agent")
        self.assertEqual(t.state, "active")
        self.assertEqual(first.download_count, 2)

    # ---------------------------------------------------------------- OTP gate vs e-mail
    def _sent_bodies(self, transfer):
        return self.env["mail.mail"].sudo().search(
            [("email_to", "in", transfer._recipient_list())]).mapped("body_html")

    def test_instance_wide_otp_holds_the_message_out_of_the_email(self):
        """The instance-wide recipient-OTP setting must pick the same template
        the per-transfer flag does. Testing only the per-transfer flag left the
        message body AND the filename listing sitting in the recipient's inbox
        — the gate held the files while the notification gave away the
        contents."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("bf_securetransfer.require_recipient_otp", "1")
        self.addCleanup(
            icp.set_param, "bf_securetransfer.require_recipient_otp", "0")
        t = self._create(message="Le NIP du dossier est 4417")
        t._register_file("contrat-secret.pdf", 4096)
        self._finalize(t)
        self.assertTrue(t._recipient_otp_required())
        bodies = "".join(self._sent_bodies(t))
        self.assertTrue(bodies, "no notification was queued")
        self.assertNotIn("4417", bodies)
        self.assertNotIn("contrat-secret.pdf", bodies)

    def test_without_otp_the_link_email_still_carries_the_message(self):
        """Guard against over-correcting: with no gate configured, the ordinary
        link template is still the one used."""
        t = self._create(message="Bonjour, voici les documents")
        t._register_file("rapport.pdf", 4096)
        self._finalize(t)
        self.assertFalse(t._recipient_otp_required())
        self.assertIn("rapport.pdf", "".join(self._sent_bodies(t)))

    # ---------------------------------------------------------------- abuse notice
    def test_abuse_notice_is_one_mail_per_recipient(self):
        """A single mail carrying the whole recipient list in To: showed every
        recipient to every other — a disclosure any anonymous link holder could
        trigger by clicking "report abuse", on a transfer that may span
        several organisations."""
        t = self._create(recipient_emails="a@x.test, b@y.test, c@z.test")
        t._register_file("doc.pdf", 4096)
        self._finalize(t)
        Mail = self.env["mail.mail"].sudo()
        t._suspend_for_abuse(ip="203.0.113.1")
        with patch("odoo.addons.mail.models.mail_mail.MailMail.send",
                   lambda self, *a, **k: True):
            t._send_abuse_notice(reason="malware", ip="203.0.113.1")
        notices = Mail.search([("subject", "like", "Transfert suspendu%")])
        self.assertEqual(len(notices), 3)
        self.assertEqual(sorted(notices.mapped("email_to")),
                         ["a@x.test", "b@y.test", "c@z.test"])
        for mail in notices:
            self.assertNotIn(",", mail.email_to or "")

    # ---------------------------------------------------------------- sender quota
    def test_sender_quota_does_not_count_the_transfer_being_finalized(self):
        """At finalize the transfer is already in the DB, so counting it
        against its own quota made a budget of 5 really allow 4 — and the
        refusal landed AFTER the upload, with no way to recover."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("bf_securetransfer.quota_daily_transfers_per_sender", "2")
        self.addCleanup(
            icp.set_param,
            "bf_securetransfer.quota_daily_transfers_per_sender", "500")
        first = self._create()
        first._register_file("doc.pdf", 4096)
        self._finalize(first)
        self.assertEqual(first.state, "active")
        second = self._create()
        second._register_file("doc.pdf", 4096)
        self._finalize(second)
        self.assertEqual(second.state, "active")

    def test_sender_quota_still_refuses_past_the_budget(self):
        """The exclusion must not disarm the quota."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("bf_securetransfer.quota_daily_transfers_per_sender", "2")
        self.addCleanup(
            icp.set_param,
            "bf_securetransfer.quota_daily_transfers_per_sender", "500")
        for _i in range(2):
            t = self._create()
            t._register_file("doc.pdf", 4096)
            self._finalize(t)
        try:
            self._create()
            self.fail("the third transfer of a budget of 2 must be refused")
        except UserError:
            pass

    # ---------------------------------------------------------------- filenames
    def test_non_latin_filename_keeps_its_extension(self):
        """secure_filename drops non-ASCII then strips "._", so "документ.pdf"
        collapsed to "pdf" — no dot left — and a legitimate file was refused
        for "having no extension", a message its owner could only read as
        wrong."""
        t = self._create()
        for name in ("документ.pdf", "报告.pdf", "Rapport-Été.pdf"):
            f = t._register_file(name, 4096)
            self.assertEqual(f.extension, "pdf", "refused/mis-parsed: %s" % name)
            self.assertEqual(f.filename, name, "display name must keep Unicode")

    def test_non_latin_filename_still_hits_the_deny_list(self):
        """Reading the extension from the raw name closes a hole rather than
        opening one: the deny-list now sees the true suffix instead of an
        empty string."""
        t = self._create()
        try:
            t._register_file("рисунок.php", 4096)
            self.fail("a .php upload must be refused")
        except UserError as exc:
            self.assertIn("php", str(exc))

    def test_filename_without_extension_still_refused(self):
        t = self._create()
        try:
            t._register_file("facture", 4096)
            self.fail("an extensionless file must be refused")
        except UserError:
            pass

    # ---------------------------------------------------------------- OTP attempt budget
    def test_resend_does_not_refill_the_attempt_budget(self):
        """"Resend a code" used to reset sender_otp_fails, so seven wrong
        guesses plus one resend restored the full budget and the 8-attempt
        ceiling bounded nothing."""
        self.env["ir.config_parameter"].sudo().set_param(
            "bf_securetransfer.require_sender_otp", "1")
        self.addCleanup(
            self.env["ir.config_parameter"].sudo().set_param,
            "bf_securetransfer.require_sender_otp", "0")
        t = self._create()
        t._register_file("a.pdf", 4096)
        with patch(S3_MOD + ".head_object", side_effect=self._head_for(t)), \
                patch.object(type(t), "_otp_email", lambda *a, **k: None):
            res = t.action_finalize()
            self.assertEqual(res.get("otp_required"), "sender")
            for _i in range(3):
                try:
                    t.confirm_sender_otp("000000")
                    self.fail("a wrong code must be refused")
                except UserError as exc:
                    self.assertIn("invalide", str(exc).lower())
            self.assertEqual(t.sudo().sender_otp_fails, 3)
            t._send_sender_otp(reset_fails=False)
            self.assertEqual(t.sudo().sender_otp_fails, 3)
            t._send_sender_otp()
            self.assertEqual(t.sudo().sender_otp_fails, 0)

    # ---------------------------------------------------------------- RPC surface
    def test_mpu_sign_refuses_a_bare_string(self):
        """`mpu_sign` has no leading underscore, so it is RPC surface. A bare
        string iterates character by character: "123" was read as parts 1, 2
        and 3, handing out presigned upload URLs nobody asked for."""
        t = self._create()
        f = t._register_file("big.bin", 4096)
        f.write({"upload_mode": "multipart", "s3_upload_id": "u-1",
                 "parts_total": 5, "part_size": 8 * 1024 * 1024})
        for bad in ("123", 3):
            try:
                f.mpu_sign(bad)
                self.fail("mpu_sign(%r) must be refused" % (bad,))
            except UserError:
                pass

    # ---------------------------------------------------------------- host routing
    def test_wildcard_host_does_not_resolve(self):
        """A Host header is attacker-controlled and "=ilike" treats it as a
        LIKE pattern. Anything carrying a metacharacter must resolve to
        nothing, or "Host: %" hands over the first branded tenant — its skin,
        its limits and its email_from."""
        Brand = self.env["secure.transfer.brand"]
        Brand.create({
            "name": "Other", "is_default": False,
            "domain": "envoi.client.test",
        })
        self.assertFalse(Brand._resolve_for_host("%"))
        self.assertFalse(Brand._resolve_for_host("%.client.test"))
        self.assertFalse(Brand._resolve_for_host("envoi.client.tes_"))
        self.assertEqual(
            Brand._resolve_for_host("envoi.client.test").domain,
            "envoi.client.test")

    # ---------------------------------------------------------------- UI strings
    def test_ui_strings_have_no_duplicate_keys(self):
        """A duplicated literal key silently overrides the first definition.
        It happened: the field LABEL replaced the validation ERROR, so a sender
        who forgot their message was told "Message *"."""
        import ast
        import inspect
        from odoo.addons.bf_securetransfer.controllers import main as ctrl
        tree = ast.parse(inspect.getsource(ctrl))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Assign)
                    and getattr(node.targets[0], "id", "") == "_UI_STRINGS"):
                continue
            for lang_dict in node.value.values:
                keys = [k.value for k in lang_dict.keys
                        if isinstance(k, ast.Constant)]
                dupes = {k for k in keys if keys.count(k) > 1}
                self.assertFalse(dupes, "duplicate _UI_STRINGS keys: %s" % dupes)

    def test_ui_strings_key_parity_between_locales(self):
        """A key missing from en_CA makes the JS fall back to a French string
        in the middle of an English page."""
        from odoo.addons.bf_securetransfer.controllers.main import _UI_STRINGS
        fr = set(_UI_STRINGS["fr_CA"])
        en = set(_UI_STRINGS["en_CA"])
        self.assertEqual(fr, en, "locale key sets differ: %s" % (fr ^ en))
