import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ProjectDocument(models.Model):
    _inherit = 'project.document'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            self._award_document_xp(rec, 'create')
        return records

    def write(self, vals):
        res = super().write(vals)
        # Only award XP for meaningful content changes
        content_fields = {'name', 'content', 'state', 'attachment_ids', 'version_ids'}
        if content_fields & set(vals.keys()):
            for rec in self:
                self._award_document_xp(rec, 'write')
        return res

    def _award_document_xp(self, doc, trigger):
        """Award XP for document creation/update."""
        if not self.env['ir.config_parameter'].sudo().get_param(
                'bf_gamification.gamification_enabled', 'True') == 'True':
            return

        # Use a savepoint so that any SQL error during XP awarding
        # does not corrupt the main transaction (which would cause
        # InFailedSqlTransaction errors during subsequent flushes).
        cr = self.env.cr
        try:
            cr.execute("SAVEPOINT award_document_xp")
            Profile = self.env['bf.gamification.profile']
            profile = Profile._get_or_create_profile(doc.create_uid)
            Rule = self.env['bf.gamification.xp.rule']

            rule = Rule.search([
                ('source', '=', 'document'),
                ('trigger', '=', trigger),
                ('active', '=', True),
            ], limit=1)
            if rule:
                desc = 'Document créé : %s' if trigger == 'create' else 'Document révisé : %s'
                profile._award_xp(
                    rule.xp_amount, 'document',
                    desc % doc.name,
                    reference=doc,
                )
            cr.execute("RELEASE SAVEPOINT award_document_xp")
        except Exception:
            cr.execute("ROLLBACK TO SAVEPOINT award_document_xp")
            self.env.clear()
            _logger.warning("Fox Quest: erreur XP document", exc_info=True)
