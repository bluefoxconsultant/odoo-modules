# Audit TI - Loi 25

Module Odoo 18 pour la gestion des audits de conformit&eacute; TI dans le cadre de la **Loi 25** (Loi sur la protection des renseignements personnels au Qu&eacute;bec).

## Fonctionnalit&eacute;s

- **14 &eacute;l&eacute;ments d'audit** : grille d'&eacute;valuation structur&eacute;e couvrant les exigences Loi 25
- **Matrice client &times; fournisseur** : &eacute;valuation par fournisseur pour chaque &eacute;l&eacute;ment, avec statuts (ad&eacute;quat, partiel, d&eacute;clar&eacute;, &agrave; valider, inad&eacute;quat, N/A)
- **Tableau de bord OWL** : KPI en temps r&eacute;el, progression par client (barres empil&eacute;es : ad&eacute;quat, partiel, inad&eacute;quat, &agrave; valider/d&eacute;clar&eacute;/N.A.) avec badge 100% pour les clients compl&egrave;tement &eacute;valu&eacute;s, progression par fournisseur, distribution des statuts, points de vigilance ouverts
- **Workflow de livraison** : &eacute;tat En cours / Livr&eacute; avec suivi (date, utilisateur), filtrage automatique dans le dashboard et la liste
- **Points de vigilance** : suivi des risques par priorit&eacute; (haute, moyenne, basse) avec assignation
- **Rapport PDF** : rapport d'avancement professionnel avec couverture des &eacute;l&eacute;ments, matrice fournisseurs, points de vigilance, barre de progression
- **Impression en lot** : action serveur pour g&eacute;n&eacute;rer les rapports PDF de plusieurs clients depuis la liste
- **Alias fournisseurs** : correspondance automatique des noms fournisseurs (variantes, abbr&eacute;viations)
- **Chatter** : historique complet des changements d'&eacute;tat et notes sur chaque client

## Mod&egrave;les

| Mod&egrave;le | Description |
|---|---|
| `audit.element` | Les 14 &eacute;l&eacute;ments d'audit Loi 25 |
| `audit.supplier` | Fournisseurs TI &eacute;valu&eacute;s |
| `audit.supplier.alias` | Alias / variantes de noms fournisseurs |
| `audit.client` | Clients audit&eacute;s (avec &eacute;tat En cours/Livr&eacute;) |
| `audit.client.supplier` | Relation client-fournisseur avec r&ocirc;les |
| `audit.assessment` | &Eacute;valuations (client &times; fournisseur &times; &eacute;l&eacute;ment) |
| `audit.watchpoint` | Points de vigilance |
| `audit.dashboard` | Tableau de bord OWL (vue `_auto=False`) |

## D&eacute;pendances

- `base`, `mail`, `project`

## Installation

```bash
odoo -i audit_ti -d <database> --stop-after-init
```

## License

MIT

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

---

*Developed with AI assistance (Claude, Anthropic).*
