/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

// ---------------------------------------------------------------------------
// 1. Namespace setup — triggered by "*" prefix in the command palette
// ---------------------------------------------------------------------------
registry.category("command_setup").add("*", {
    debounceDelay: 300,
    emptyMessage: _t("Aucun résultat trouvé"),
    name: _t("enregistrements"),
    placeholder: _t("Rechercher partout..."),
});

// ---------------------------------------------------------------------------
// 2. Categories — grouping within the "*" namespace
// ---------------------------------------------------------------------------
const catReg = registry.category("command_categories");
catReg.add("search_contacts", { namespace: "*", name: _t("Contacts") }, { sequence: 10 });
catReg.add("search_projects", { namespace: "*", name: _t("Projets") }, { sequence: 20 });
catReg.add("search_hosting", { namespace: "*", name: _t("Hébergement") }, { sequence: 30 });
catReg.add("search_documents", { namespace: "*", name: _t("Documents") }, { sequence: 40 });
catReg.add("search_other", { namespace: "*", name: _t("Autres") }, { sequence: 50 });

// ---------------------------------------------------------------------------
// 3. Provider — async search via bf.universal.search.search_all()
// ---------------------------------------------------------------------------
registry.category("command_provider").add("bf_universal_search", {
    namespace: "*",
    async provide(env, options) {
        const query = options.searchValue;
        if (!query || query.length < 2) {
            return [];
        }

        let groups;
        try {
            groups = await env.services.orm.call(
                "bf.universal.search",
                "search_all",
                [query],
            );
        } catch (e) {
            console.error("bf_universal_search: RPC error", e);
            return [];
        }

        const commands = [];
        for (const group of groups) {
            for (const result of group.results) {
                const resultName = result.detail
                    ? `${result.name}  —  ${result.detail}`
                    : result.name;

                commands.push({
                    name: resultName,
                    category: group.category,
                    action() {
                        env.services.action.doAction({
                            type: "ir.actions.act_window",
                            res_model: group.model,
                            res_id: result.id,
                            views: [[false, "form"]],
                        });
                    },
                });
            }
        }
        return commands;
    },
});
