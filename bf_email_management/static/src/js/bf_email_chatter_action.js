/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const messageActionsRegistry = registry.category("mail.message/actions");

messageActionsRegistry.add("bf-download-eml", {
    condition: (component) => {
        const message = component.props.message;
        return Boolean(message?.id) && component.store?.self?.isInternalUser;
    },
    icon: "fa fa-download",
    title: _t("Télécharger en .eml"),
    onClick: async (component) => {
        const message = component.props.message;
        const result = await component.env.services.orm.call(
            "mail.message",
            "action_download_eml",
            [[message.id]]
        );
        if (result) {
            component.env.services.action.doAction(result);
        }
    },
    sequence: 80,
});
