from odoo.addons.web.controllers.dataset import DataSet
from odoo.http import route


class DataSetSmsArchive(DataSet):
    """Override call_kw for sms.archive.import.wizard to allow large uploads."""

    @route(
        "/web/dataset/call_kw/sms.archive.import.wizard",
        type="json",
        auth="user",
        max_content_length=1024 * 1024 * 1024,  # 1 GB
    )
    def call_kw_sms_import(self, model, method, args, kwargs):
        return self._call_kw(model, method, args, kwargs)
