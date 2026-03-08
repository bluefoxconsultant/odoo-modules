# BF Import courriel (.eml)

Module Odoo 18 Community permettant d'importer des fichiers `.eml` (RFC 2822) directement dans le chatter de n'importe quel enregistrement.

## Cas d'usage

Lorsque des courriels sont re&#231;us ou envoy&#233;s hors d'Odoo (client de messagerie externe, webmail, transfert entre coll&#232;gues), il n'existe aucun m&#233;canisme natif pour les rattacher &#224; un fil de discussion existant. Ce module comble ce manque en ajoutant un bouton d'import `.eml` dans le chatter.

## Fonctionnalit&#233;s

- **Bouton `.eml` dans le chatter** -- visible sur tout enregistrement h&#233;ritant de `mail.thread`
- **Import multi-fichiers** -- t&#233;l&#233;versement de plusieurs `.eml` en une seule op&#233;ration
- **Import direct** -- un seul clic pour importer (pas d'&#233;tape d'aper&#231;u)
- **D&#233;tection des doublons** -- v&#233;rification du `Message-ID` RFC 2822 avant insertion
- **R&#233;solution automatique de l'auteur** -- recherche du `res.partner` correspondant &#224; l'adresse courriel de l'exp&#233;diteur
- **Pr&#233;servation du threading** -- `parent_id` r&#233;solu via les en-t&#234;tes `In-Reply-To` / `References`
- **Z&#233;ro notification** -- l'import ne d&#233;clenche aucun courriel sortant ni auto-abonnement
- **Pi&#232;ces jointes inline uniquement** -- seules les pi&#232;ces jointes contenues dans le courriel sont import&#233;es (pas de duplication du `.eml` original)

## Architecture technique

### Structure

```
bf_mail_import/
+-- __init__.py
+-- __manifest__.py
+-- README.md
+-- security/
|   +-- ir.model.access.csv
+-- wizard/
|   +-- __init__.py
|   +-- mail_import_wizard.py
|   +-- mail_import_wizard_views.xml
+-- static/
    +-- src/
        +-- js/
        |   +-- chatter_import_patch.js
        +-- xml/
            +-- chatter_import_patch.xml
```

### D&#233;pendances

| Module | R&#244;le |
|--------|------|
| `mail` | Seule d&#233;pendance -- fournit `mail.thread`, `message_parse()`, `message_post()` |

Aucune d&#233;pendance externe, aucune librairie Python suppl&#233;mentaire.

### Parsing des courriels

Le module d&#233;l&#232;gue **100 % du parsing RFC 2822** &#224; la cha&#238;ne standard :

1. `email.message_from_bytes(raw, policy=email.policy.default)` -- produit un `EmailMessage` (API moderne Python 3, requise par Odoo 18)
2. `self.env['mail.thread'].message_parse(email_msg, save_original=False)` -- m&#233;thode publique `@api.model` d'Odoo

Le dict retourn&#233; par `message_parse` contient : `message_id`, `subject`, `email_from`, `to`, `cc`, `body`, `date`, `parent_id`, `partner_ids`, `attachments`, `references`, `in_reply_to`, etc.

### Wizard (`bf.mail.import.wizard`)

`TransientModel` &#224; 2 &#233;tats :

| &#201;tat | Action utilisateur | Comportement |
|------|-------------------|-------------|
| `draft` | S&#233;lection de fichiers `.eml` + clic Importer | Widget `many2many_binary` li&#233; &#224; `ir.attachment`, import direct |
| `done` | R&#233;sultat affich&#233; | R&#233;sum&#233; des imports, doublons, erreurs |

**Appel `message_post` :**

```python
target.with_context(
    mail_create_nosubscribe=True,      # pas d'auto-abonnement
    mail_create_nolog=True,            # pas de log de cr&#233;ation
    mail_notify_force_send=False,       # pas d'envoi imm&#233;diat
    mail_auto_subscribe_no_notify=True, # pas de notification aux abonn&#233;s
    tracking_disable=True,              # pas de tracking de champs
).message_post(
    body=Markup(body_html),
    message_type='email',              # affichage "courriel" dans le chatter
    subtype_xmlid='mail.mt_comment',
    message_id=rfc2822_message_id,     # via **kwargs -> colonne mail.message
    date=original_date,                # via **kwargs -> colonne mail.message
    ...
)
```

### Patch OWL (chatter)

Le bouton est inject&#233; via le pattern standard de patch Odoo 18 :

- **JS** : `patch(Chatter.prototype, {...})` ajoute la m&#233;thode `onClickImportEml()`
- **XML** : Template `t-inherit="mail.Chatter"` avec xpath apr&#232;s le bouton "Activit&#233;s"
- **Rafra&#238;chissement** : `this.load(this.state.thread, ["messages"])` apr&#232;s fermeture du wizard

### S&#233;curit&#233;

- Acc&#232;s CRUD au wizard pour tous les utilisateurs internes (`base.group_user`)
- Menu technique "Importer .eml" r&#233;serv&#233; aux administrateurs (`base.group_system`)
- Le contr&#244;le d'acc&#232;s r&#233;el est celui de l'enregistrement cible -- `message_post` v&#233;rifie les droits d'&#233;criture

### Gestion des cas limites

| Cas | Comportement |
|-----|-------------|
| Fichier corrompu / non-.eml | Erreur captur&#233;e, ajout&#233;e au r&#233;sum&#233;, les autres fichiers continuent |
| `Message-ID` d&#233;j&#224; pr&#233;sent dans `mail.message` | Fichier ignor&#233;, compteur "doublons" incr&#233;ment&#233; |
| Exp&#233;diteur sans `res.partner` | `email_from` affich&#233; tel quel dans le chatter (comportement natif Odoo) |
| `.eml` sans corps | Message post&#233; avec body vide, sujet et PJ pr&#233;serv&#233;s |
| Encodage non-UTF-8 | G&#233;r&#233; par `email.message_from_bytes()` + `message_parse()` |
| Enregistrement cible supprim&#233; | `UserError` avant tentative d'import |
| Mod&#232;le sans `mail.thread` | `UserError` dans `default_get()` |

## Installation

```bash
docker compose exec odoo odoo -d <database> -u bf_mail_import --stop-after-init
```

## Utilisation

1. Ouvrir n'importe quel enregistrement avec un chatter (projet, t&#226;che, partenaire, facture, ticket, etc.)
2. Cliquer le bouton **`.eml`** dans la barre du chatter (&#224; c&#244;t&#233; de "Activit&#233;s")
3. T&#233;l&#233;verser un ou plusieurs fichiers `.eml`
4. **Importer** -- les messages apparaissent dans le chatter avec la date et l'exp&#233;diteur originaux

## Licence

LGPL-3

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

## Remerciements

Ce module a &#233;t&#233; d&#233;velopp&#233; avec l'assistance de Claude (Anthropic) pour l'architecture, l'impl&#233;mentation et la documentation technique.
