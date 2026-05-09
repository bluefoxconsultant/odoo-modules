from odoo.tests import TransactionCase, tagged


@tagged("bf_helpdesk", "bf_helpdesk_layout")
class TestTicketLayout(TransactionCase):
    """_track_template must swap mail.mail_notification_light → bluefox_branding.bf_mail_layout."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Ticket = cls.env["helpdesk.ticket"]
        cls.alias = cls.env["mail.alias"].create({
            "alias_name": "layout-test",
            "alias_model_id": cls.env.ref("helpdesk_mgmt.model_helpdesk_ticket").id,
        })
        cls.team = cls.env["helpdesk.ticket.team"].create({
            "name": "Layout Test Team",
            "alias_id": cls.alias.id,
        })
        # Build a stage that has a mail template (any stage with mail_template_id)
        cls.template = cls.env.ref("helpdesk_mgmt.closed_ticket_template")
        cls.stage = cls.env["helpdesk.ticket.stage"].create({
            "name": "Closed-with-template",
            "closed": True,
            "mail_template_id": cls.template.id,
        })

    def test_track_template_uses_bf_layout(self):
        ticket = self.Ticket.create({
            "name": "layout test",
            "description": "<p>x</p>",
            "team_id": self.team.id,
        })
        ticket.stage_id = self.stage
        res = ticket._track_template({"stage_id": True})
        self.assertIn("stage_id", res,
                      "Closing stage must produce a tracking template entry")
        _template, ctx = res["stage_id"]
        self.assertEqual(
            ctx.get("email_layout_xmlid"),
            "bluefox_branding.bf_mail_layout",
            "BF helpdesk must override the OCA mail.mail_notification_light layout",
        )
