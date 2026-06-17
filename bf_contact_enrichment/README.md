# Enrichissement de contacts (`bf_contact_enrichment`)

Réduit la saisie manuelle des fiches `res.partner` en les enrichissant
automatiquement à partir de quatre sources, via le bridge Claude de Blue Fox.

## Fonctionnalités

1. **Carte d'affaires (OCR)** — *Contacts ▸ Enrichissement ▸ Numériser une carte*
   ou le bouton « Numériser une carte » sur une fiche. L'image (JPG/PNG/PDF) est
   envoyée au bridge (`/ocr/business-card`), Claude lit la carte et renvoie les
   coordonnées. Le module détecte un contact existant (courriel, nom, domaine)
   et propose de créer ou de mettre à jour ; la carte est jointe à la fiche.
2. **Signatures courriel** — deux boutons sur la fiche : « Enrichir maintenant
   (signatures) » applique directement (remplit les vides, un clic), tandis que
   « Enrichir (réviser) » ouvre un comparatif champ par champ. Les deux
   concatènent les derniers courriels entrants (`bf.email`, qui reflète l'IMAP,
   la passerelle et les chatters) du correspondant et les envoient à
   `/enrich/signature`. **En lot** : *Contacts ▸ (liste) ▸ Action ▸ Enrichir
   depuis les signatures courriel* met les contacts sélectionnés en file ; un
   cron les traite en arrière-plan par lots (seuil de confiance, jamais
   d'écrasement).
3. **Créer un contact depuis un courriel** — bouton « Créer / enrichir le
   contact » sur une fiche `bf.email` : retrouve ou crée l'expéditeur puis lance
   l'enrichissement par signature.
4. **Quick wins**
   - **Import vCard** (`.vcf`) — parseur intégré, sans dépendance externe.
   - **Détecteur de doublons** — par courriel et par nom normalisé ; ouvre le
     sous-ensemble pour fusion via l'action native des Contacts.
   - **Enrichissement par domaine** — bouton « Enrichir (site web) » :
     `/enrich/company` (WebFetch/WebSearch) remplit la société.
   - **Score de complétude** — champ calculé + filtre « Contacts incomplets ».

Aucun champ renseigné n'est écrasé par défaut (`_apply_contact_vals` ne remplit
que les vides, sauf option « Écraser »). Chaque enrichissement est journalisé
dans le chatter de la fiche.

## Dépendances

`base`, `contacts`, `mail`, `bf_email_management`, et le service bridge
TentaClaude (socket `bf_claude_chat.bridge_socket`).

## Confidentialité

Les prompts demandent à Claude de n'extraire que ce qui est réellement présent
(jamais de nom de famille deviné depuis l'adresse courriel) et d'ignorer
l'historique cité dans les courriels.
