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
bf_helpdesk.ntfy_webhook_url = http://your-webhook-relay:8090/hook/your-key
```
Then enable `ntfy_critical_enabled` per-team in the team form.

### Public form
1. Open a helpdesk team
2. Set `slug` (e.g. `my-support-team`)
3. Tick `public_form_enabled`
4. Visit `/support/<slug>` — page is anonymous-friendly

## Migration notes

If you have a legacy band-aid module that opted in helpdesk fields for the website
form builder, you can uninstall it after installing `bf_helpdesk` (the opt-in is
folded in via `post_init_hook`). If you have a `base.automation` rule that fires
on helpdesk priority changes, disable it once team-level `ntfy_critical_enabled`
is set, to avoid double notifications.

## Roadmap

- Persona panel (`bf_persona`) on ticket form — **shipped in 18.0.2.0.0**
- Triage IA via Claude
- Knowledge matrix link → `knowledge.item`
- Convert ticket → `meeting.record`

## Phase 3 (planned)

- CSAT survey on close (`bf_survey_upload`)
- Dashboard tile (`bf_dashboard`)
- Branded portal templates fr_CA/en_CA
- Native IMAP gateway gotcha handling (`bf_mail_import` lib)
