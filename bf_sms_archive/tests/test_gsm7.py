# -*- coding: utf-8 -*-
"""Normalisation GSM-7 des SMS sortants (anti-fragmentation).

Un SMS tient dans 160 caractères en GSM-7, mais 70 seulement dès qu'un
caractère hors table force l'UCS-2. VOIP.ms n'assemblant pas les segments,
un message fragmenté arrive en plusieurs messages distincts chez le
destinataire. On vérifie ici que la normalisation ramène le message en
GSM-7 (emoji retirés, ponctuation typographique translittérée) et que
l'option d'aplatissement des accents circonflexe/tréma se comporte comme
attendu (défaut OFF : accents conservés).
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGsm7Normalize(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.M = cls.env["sms.archive.message"]

    def _norm(self, text, flatten=False):
        return self.M._normalize_gsm7(text, flatten_accents=flatten)

    def _segs(self, text):
        return len(self.M._split_segments(text))

    # ── Détection d'encodage ───────────────────────────────────────
    def test_is_gsm7(self):
        self.assertTrue(self.M._is_gsm7("Deja pret, c'est bon !"))
        self.assertTrue(self.M._is_gsm7("Été à Paris, il a gagné !"))  # É é à = GSM-7
        self.assertFalse(self.M._is_gsm7("Prêt ?"))   # ê (circonflexe) hors GSM-7
        self.assertFalse(self.M._is_gsm7("Noël"))     # ë (tréma) hors GSM-7
        self.assertFalse(self.M._is_gsm7("ça va"))    # ç MINUSCULE hors GSM-7 (piège !)
        self.assertFalse(self.M._is_gsm7("Salut ⚡"))  # emoji

    # ── Emoji retiré → message court redevient 1 SMS ───────────────
    def test_emoji_stripped_single_segment(self):
        src = "Bonjour Erik, sans probleme, je m'occupe de tout. " * 3  # ~150 car.
        src_emoji = src + "⚡"
        self.assertGreater(self._segs(src_emoji), 1)          # UCS-2 -> fragmente
        out = self._norm(src_emoji)
        self.assertNotIn("⚡", out)
        self.assertTrue(self.M._is_gsm7(out))
        self.assertEqual(self._segs(out), 1)                  # 1 seul SMS

    # ── Ponctuation typographique translittérée ────────────────────
    def test_typography(self):
        self.assertEqual(self._norm("c’est «bon»…"), 'c\'est "bon"...')
        self.assertEqual(self._norm("A — B"), "A - B")
        self.assertEqual(self._norm("un œuf"), "un oeuf")
        self.assertEqual(self._norm("A : B"), "A : B")   # nbsp -> espace

    # ── nbsp / doubles espaces laissées par un retrait tassées ─────
    def test_collapse_spaces_keeps_newlines(self):
        self.assertEqual(self._norm("Salut ⚡ toi"), "Salut toi")
        self.assertEqual(self._norm("Ligne1 ⚡\nLigne2"), "Ligne1\nLigne2")

    # ── Accents : OFF conserve, ON aplatit ; é/è/à/ç toujours gardés ─
    def test_flatten_accents_toggle(self):
        self.assertEqual(self._norm("même", flatten=False), "même")   # OFF: gardé
        self.assertEqual(self._norm("même", flatten=True), "meme")    # ON: aplati
        # accents GSM-7 préservés dans les deux cas
        for fl in (False, True):
            self.assertEqual(self._norm("café à côté", flatten=fl)[:5], "café ")

    # ── Texte déjà GSM-7 renvoyé tel quel (no-op) ──────────────────
    def test_gsm7_noop(self):
        src = "Déjà GSM-7, rien à changer ! (é è à)"
        self.assertTrue(self.M._is_gsm7(src))
        self.assertEqual(self._norm(src), src)

    # ── Idempotence + garantie GSM-7 en mode aplatissement ─────────
    def test_idempotent_and_gsm7_when_flattening(self):
        samples = ["Prêt ⚡ ?", "Coût élevé — «vôtre»…", "Île 😊 déjà"]
        for s in samples:
            once = self._norm(s, flatten=True)
            self.assertTrue(self.M._is_gsm7(once), f"pas GSM-7: {once!r}")
            self.assertEqual(self._norm(once, flatten=True), once)

    def test_default_flatten_off(self):
        """Le réglage runtime par défaut conserve les accents (choix par défaut)."""
        self.assertFalse(self.M._gsm7_flatten_accents_enabled())
