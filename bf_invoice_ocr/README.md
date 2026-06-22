# bf_invoice_ocr — Invoice OCR Scanner

Module Odoo 18 (CE) qui analyse les factures fournisseurs (vendor bills) au
format PDF et pré-remplit automatiquement les champs de la facture. L'extraction
passe par la passerelle **`bf_llm`**, ce qui rend le module agnostique au
fournisseur : Anthropic en direct, OpenAI (avec rastérisation du PDF), ou un
serveur local compatible OpenAI.

## Fonctionnalités

- **Bouton « Scanner OCR »** sur chaque facture fournisseur en brouillon
- **Cron horaire** pour le traitement en lot des nouvelles factures
- **Matching fournisseur intelligent** en 8 étapes (VAT, nom, courriel, téléphone, historique)
- **Matching produit** par code, références fournisseur, et description
- **Onglet OCR** affichant le statut, la confiance et les données brutes

## Architecture

```
account.move (bf_invoice_ocr)
        │
        │ env["bf.llm"].for_feature("ocr").extract(pdf_bytes, OCR_PROMPT)
        ▼
bf.llm — passerelle LLM agnostique au fournisseur
        │
        ▼
Fournisseur configuré (Anthropic / OpenAI / serveur local)
        │  retourne du JSON structuré
        ▼
Odoo applique les résultats (partner, ref, dates, lignes, taxes)
```

## Configuration

1. Installer `bf_llm` et y configurer au moins un fournisseur LLM par défaut :
   **Paramètres › Technique › LLM Providers**. La clé d'API est chiffrée au repos
   (Fernet) — voir le README de `bf_llm`.
2. Optionnel : définir la taxe d'achat par défaut appliquée aux lignes créées par
   l'OCR (voir « Taxe par défaut » ci-dessous).

## Champs ajoutés sur `account.move`

| Champ | Type | Description |
|-------|------|-------------|
| `ocr_state` | Selection | none / pending / done / error |
| `ocr_scanned_date` | Datetime | Date du dernier scan |
| `ocr_confidence` | Float | Score de confiance 0-100 |
| `ocr_raw_response` | Text | Réponse JSON brute du modèle |
| `ocr_error_message` | Char | Message d'erreur le cas échéant |

## Données extraites par l'OCR

- Nom, courriel, site web, téléphone, numéro de taxe (TPS/TVQ/NEQ/GST/HST) du fournisseur
- Numéro de facture, dates (facture et échéance), devise
- Lignes détaillées (description, code produit, quantité, prix unitaire, montant)
- Sous-total, taxes, total
- Score de confiance (0-100)

Le gabarit de prompt (`OCR_PROMPT`) est fourni par `bf_llm` et conserve les règles
canadiennes (TPS/TVQ, NEQ) ainsi que les garde-fous anti-injection (le contenu de
la facture est traité comme une **donnée non fiable**, jamais comme une instruction).

## Matching fournisseur (8 étapes)

1. **Numéro de taxe (VAT/NEQ)** — recherche dans `vat` et `company_registry`
2. **Nom exact** — `ilike` avec `supplier_rank > 0`
3. **Domaine courriel/web** — extrait le domaine, cherche dans `email` et `website` (ignore les fournisseurs génériques : gmail, hotmail, outlook, yahoo)
4. **Téléphone** — 7 derniers chiffres dans `phone` / `mobile`
5. **Nom nettoyé** — retire les suffixes légaux (Inc, Ltd, Ltée, Corp, SENC, PBC…)
6. **Mots significatifs** — normalisation des accents, exclusion des mots bruit (Services, Solutions, Groupe, Canada…), match sur les 2 premiers mots distinctifs
7. **Historique OCR** — cherche dans les factures précédemment scannées avec le même nom fournisseur
8. **Fallback** — `is_company=True` sans filtre `supplier_rank`

Si aucun match : `partner_id` reste vide (saisie manuelle).

## Matching produit (3 étapes)

1. **Code produit** — `default_code` (ilike) ou `barcode` (exact) depuis le champ `product_code` extrait par l'OCR
2. **Références fournisseur** — `product.supplierinfo` du fournisseur trouvé, par `product_code` puis `product_name`
3. **Description** — recherche par mots distinctifs (5+ caractères, `purchase_ok=True`), uniquement si match unique (évite les faux positifs)

Si un produit est trouvé : ses taxes fournisseur (`supplier_taxes_id`) sont
utilisées. Sinon : la taxe d'achat par défaut (voir ci-dessous).

## Taxe par défaut

La taxe appliquée aux lignes créées par l'OCR (lorsque le produit n'impose pas la
sienne) est résolue dans cet ordre :

1. Le paramètre système `bf_invoice_ocr.default_tax_id` (id explicite d'`account.tax`),
   s'il est défini ;
2. La taxe d'achat configurée sur la société (`account_purchase_tax_id`) ;
3. À défaut, la première taxe de type `purchase` de la société.

Si aucune taxe n'est trouvée, les lignes sont créées sans taxe (à compléter
manuellement). Aucun id de taxe n'est codé en dur dans le module.

## Installation

```bash
# Installer / mettre à jour via votre procédure habituelle de déploiement Odoo, p. ex. :
odoo -d <database> -i bf_invoice_ocr --stop-after-init
```

Dépendances Odoo : `account`, `bf_llm`.

## Licence

LGPL-3
