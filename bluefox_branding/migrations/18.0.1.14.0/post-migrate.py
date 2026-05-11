"""Re-apply branded layouts to calendar event templates.

Aligns calendar invite/update/reminder templates on the compact header used
by the branded layouts.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    from odoo.addons.bluefox_branding.hooks import post_init_hook
    post_init_hook(env)
