"""Force-update mail.template records whose XML data blocks are noupdate="1".

Odoo only loads <data noupdate="1"> blocks on fresh install. Subsequent
``-u bf_meeting`` runs will skip them, so changes to the templates' subject,
body_html, email_from or partner_to never propagate. This helper patches the
live records directly from the current XML source.

Usage (inside the Odoo container hosting the target database)::

    odoo shell -d <database> --no-http < force_update_mail_templates.py
"""
import xml.etree.ElementTree as ET

FILES = [
    ('/mnt/extra-addons/bf_meeting/data/meeting_agenda_mail_template.xml',
     'bf_meeting.meeting_agenda_mail_template'),
    ('/mnt/extra-addons/bf_meeting/data/meeting_report_mail_template.xml',
     'bf_meeting.meeting_report_mail_template'),
]

UPDATABLE = ('subject', 'email_from', 'partner_to', 'body_html')

for path, xmlid in FILES:
    tree = ET.parse(path)
    record = tree.find('.//record')
    tmpl = env.ref(xmlid, raise_if_not_found=False)
    if not tmpl:
        print(f"[skip] {xmlid} not found")
        continue
    vals = {}
    for fld in record.findall('field'):
        name = fld.get('name')
        if name in UPDATABLE and fld.text is not None:
            vals[name] = fld.text
    tmpl.write(vals)
    print(f"[ok] {xmlid} updated: {list(vals.keys())}")

env.cr.commit()
