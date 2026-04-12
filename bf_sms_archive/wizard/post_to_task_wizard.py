import logging

import markupsafe

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SmsPostToTaskWizard(models.TransientModel):
    _name = "sms.archive.post.to.task.wizard"
    _description = "Poster un SMS sur une tâche"

    message_id = fields.Many2one(
        comodel_name="sms.archive.message",
        string="Message",
        required=True,
    )
    message_preview = fields.Text(
        related="message_id.body",
        string="Aperçu",
        readonly=True,
    )
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Projet",
        required=True,
    )
    task_id = fields.Many2one(
        comodel_name="project.task",
        string="Tâche",
        required=True,
        domain="[('project_id', '=', project_id)]",
    )
    link_thread = fields.Boolean(
        string="Lier aussi la conversation à cette tâche",
        default=True,
    )

    def action_post(self):
        """Post the SMS message to the selected task's chatter."""
        self.ensure_one()
        msg = self.message_id
        task = self.task_id
        thread = msg.thread_id

        direction = "Reçu" if msg.direction == "in" else "Envoyé"
        contact = markupsafe.escape(thread.contact_name or thread.phone_normalized)
        body_escaped = markupsafe.escape(msg.body or '')
        body_html = (
            f"<p><strong>SMS {direction}</strong> — {contact} "
            f"({msg.date_sent})</p>"
            f"<p>{body_escaped}</p>"
        )
        task.message_post(
            body=body_html,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
            body_is_html=True,
        )

        if self.link_thread and task.id not in thread.task_ids.ids:
            thread.write({"task_ids": [(4, task.id, 0)]})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "SMS posté",
                "message": f"Message posté sur « {task.name} » ({self.project_id.name})",
                "type": "success",
            },
        }
