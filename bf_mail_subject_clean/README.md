# BF Nettoyage des sujets de courriel

Module Odoo 18 Community qui empêche l'empilement de préfixes `Re:` sur les sujets des messages envoyés via le chatter.

## Cas d'usage

Quand un échange courriel va et vient entre Odoo et un client externe (Outlook, Gmail, Apple Mail), chaque réponse ajoute un nouveau `Re:` au sujet. Après quelques allers-retours, on se retrouve avec `Re: Re: Re: Re: Sujet original` qui pollue l'inbox du destinataire et l'historique du chatter. Ce module ramène toujours à un seul `Re:`, sans modifier les courriels entrants.

## Fonctionnalités

- **Collapse automatique des préfixes empilés** — `Re: Re: Re: Hello` devient `Re: Hello`
- **Insensible à la casse** — `RE: Re: re: Hello` devient `Re: Hello`
- **Compatibilité avec les compteurs BlackBerry/Outlook** — `Re[2]: Hello` et `Re(3): Hello` deviennent `Re: Hello`
- **Tolérance d'espaces et de ponctuation** — `Re:Hello`, ` Re: Hello`, `Re : Hello` sont tous normalisés
- **Aucune perte d'information** — les sujets sans préfixe `Re:` ne sont jamais touchés
- **Application au compose et au post** — l'utilisateur voit immédiatement le sujet propre dans le wizard ; le `mail.message` stocké et le courriel sortant sont propres
- **Préservation des sujets entrants** — l'IMAP gateway et `message_parse` ne sont pas affectés ; on garde la chaîne `Re:` originale telle que reçue
- **Aucune dépendance externe** — uniquement la regex Python standard, pas de librairie supplémentaire

## Architecture technique

### Structure

```
bf_mail_subject_clean/
+-- __init__.py
+-- __manifest__.py
+-- README.md
+-- models/
    +-- __init__.py
    +-- common.py                    # helper normalize_reply_subject()
    +-- mail_compose_message.py      # override _compute_subject (UX wizard)
    +-- mail_thread.py               # override message_post (chatter inline + RPC + Python)
```

### Dépendances

| Module | Rôle |
|--------|------|
| `mail` | Seule dépendance — fournit `mail.thread.message_post` et le wizard `mail.compose.message` |

### Helper de normalisation

```python
_REPLY_PREFIX_RE = re.compile(
    r'^(?:\s*re(?:\s*[\[(]\d+[\])])?\s*:\s*)+',
    re.IGNORECASE,
)

def normalize_reply_subject(subject):
    if not subject or not isinstance(subject, str):
        return subject
    match = _REPLY_PREFIX_RE.match(subject)
    if not match:
        return subject
    return f'Re: {subject[match.end():]}'
```

La regex est conçue pour résister au catastrophic backtracking : le `:` requis à chaque itération empêche toute séquence pathologique d'exploser. Mesuré à <1 ms sur 20 000 caractères de pire cas.

### Points d'override

| Modèle | Méthode | Effet |
|--------|---------|-------|
| `mail.compose.message` | `_compute_subject` | Nettoie le sujet pré-rempli depuis le parent quand l'utilisateur ouvre le compose plein écran |
| `mail.thread` | `message_post` | Nettoie le `subject` kwarg avant de poster, ce qui couvre : chatter inline, RPC `message_post`, code Python métier, modules tiers qui appellent `message_post` |

L'override de `message_post` est appliqué sur le modèle abstrait `mail.thread` et est donc actif sur tous les modèles qui l'héritent (tâches, partenaires, factures, projets, tickets helpdesk, etc.).

### Sécurité

- Aucun nouveau modèle, aucune nouvelle table, aucun nouvel `ir.model.access.csv`
- Aucun appel `sudo()`, aucune élévation de privilèges
- Aucune ressource réseau, aucun secret, aucune ressource externe
- Manipulation de chaînes pure — aucune injection SQL ou XSS possible

### Cas couverts

| Entrée | Sortie |
|--------|--------|
| `Re: Re: Re: Hello` | `Re: Hello` |
| `RE: Re: re: Hello` | `Re: Hello` |
| `Re[2]: Hello` | `Re: Hello` |
| `Re(3): Hello` | `Re: Hello` |
| `Re:Hello` (sans espace) | `Re: Hello` |
| ` Re: Hello` (espace en tête) | `Re: Hello` |
| `Re: Hello` | `Re: Hello` (inchangé) |
| `Hello` | `Hello` (inchangé) |
| `Replied: but not really` | `Replied: but not really` (inchangé) |
| `Fw: Re: Hello` | `Fw: Re: Hello` (inchangé — le module ne touche pas `Fw:`/`Tr:`) |
| `""` ou `None` | tel quel |

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_mail_subject_clean --stop-after-init
```

Ou via l'interface : **Apps** → rafraîchir la liste → installer **BF Nettoyage des sujets de courriel**.

## Désinstallation

Pas de migration de données nécessaire — aucune donnée n'est créée par ce module. Désinstaller le module via l'interface ou en CLI :

```bash
docker compose exec odoo odoo -d <database> --stop-after-init -- shell -c "self.env['ir.module.module'].search([('name','=','bf_mail_subject_clean')]).button_immediate_uninstall()"
```

## Licence

LGPL-3

## Remerciements

Créé et maintenu par Blue Fox Inc. Des assistants de codage IA ont été utilisés comme outils de productivité durant le développement.
