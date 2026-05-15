/** @odoo-module **/

import { Component, onMounted, onWillDestroy, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const INBOX_DOMAIN = [
    ["is_handled", "=", false],
    "|",
    ["imap_in_inbox", "=", true],
    ["source", "in", ["chatter", "gateway"]],
];

export class BfEmailSystray extends Component {
    static template = "bf_email_systray.Systray";
    static props = [];

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.state = useState({ count: 0 });
        this._pollInterval = null;

        onMounted(async () => {
            try {
                await this._refresh();
                this._pollInterval = setInterval(() => this._refresh(), 120_000);
            } catch (e) {
                console.error("bf_email_systray: mount error", e);
            }
        });

        onWillDestroy(() => {
            if (this._pollInterval) {
                clearInterval(this._pollInterval);
            }
        });
    }

    async _refresh() {
        try {
            const count = await this.orm.searchCount("bf.email", INBOX_DOMAIN);
            this.state.count = count || 0;
        } catch (e) {
            console.error("bf_email_systray: count failed", e);
        }
    }

    get hasCount() {
        return this.state.count > 0;
    }

    get countLabel() {
        return this.state.count > 99 ? "99+" : String(this.state.count);
    }

    onOpen() {
        this.actionService.doAction("bf_email_management.bf_email_action");
    }
}

export const systrayItem = { Component: BfEmailSystray };

registry.category("systray").add("BfEmailSystray", systrayItem, { sequence: 4 });
