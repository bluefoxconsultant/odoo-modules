# Blue Fox — Helpdesk

Fork-style extension of OCA `helpdesk_mgmt` with native Blue Fox integrations.

## Phase 1 features

| # | Feature | Where |
|---|---|---|
| 1 | **Hour bank integration**: per-team `hour.bank.client` link, live balance + low-balance ribbon on tickets | team form › "Hour bank & alerts" tab |
| 2 | **Waiting states**: `waiting_state` on tickets — `Attente — Client.e` / `Attente — Externe`, independent from stage | ticket form/list/search |
| 3 | **Per-team public support form** at `/support/<slug>` — branded BF, replaces `bf_helpdesk_website_form` band-aid | team form › "Public form" tab |
| 4 | **ntfy critical hook**: per-team opt-in, fires POST to webhook relay on Very High (or High) priority tickets | team form › "Hour bank & alerts" tab |

## Configuration

### ntfy webhook URL
Set the system parameter once per deployment:
```
bf_helpdesk.ntfy_webhook_url = http://push-webhook-relay:8090/hook/helpdesk-critical
```
Then enable `ntfy_critical_enabled` per-team in the team form.

### Public form
1. Open a helpdesk team
2. Set `slug` (e.g. `my-support-team`)
3. Tick `public_form_enabled`
4. Visit `/support/<slug>` — page is anonymous-friendly

## Migration notes

If you have a legacy `bf_helpdesk_website_form` band-aid module installed:

1. Install `bf_helpdesk` — opt-in fields run automatically via `post_init_hook`
2. Uninstall the legacy band-aid module (folded in here)
3. If you have a `base.automation` rule that fires on `priority='3'` for helpdesk
   tickets, disable it once team-level `ntfy_critical_enabled` is set, to avoid
   double notifications.

## Roadmap

Future versions may add:

- Persona panel on ticket form
- IA triage (categorize / suggest stage+assignee / draft response)
- Knowledge matrix link
- Convert ticket → meeting record
- CSAT survey on close
- Dashboard tile
- Native IMAP gateway hardening
