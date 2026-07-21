# Sécurité — `bf_sign`

## Versions supportées

La version courante (`18.0.3.13.2`) reçoit les correctifs de sécurité. Les versions antérieures n'en reçoivent pas : mettez à niveau avant de signaler.

## Signaler une vulnérabilité

Merci de signaler toute vulnérabilité de manière responsable à
**security@bluefoxconsultant.com**, sans divulgation publique préalable.

## Périmètre

Le module expose des **routes publiques non authentifiées** protégées par un
**jeton d'accès par signataire** :

- `GET /sign/<id>/<token>` — page de signature
- `GET /sign/<id>/<token>/document` — aperçu du PDF original
- `POST /sign/<id>/<token>/submit` — soumission de la signature
- `POST /sign/<id>/<token>/refuse` — refus de signer
- `GET /sign/<id>/<token>/done` — confirmation
- `GET /sign/<id>/<token>/download` — téléchargement du document signé

## Contrôles en place

- **Jetons d'accès** UUID v4 par signataire, comparés en **temps constant**
  (`hmac.compare_digest`) — pas d'énumération par mesure de temps.
- **Limitation anti-force brute** par IP sur les échecs de jeton (fenêtre
  glissante). *Limite connue : l'état est en mémoire et donc **par worker** ; un
  déploiement multi-worker multiplie le plafond effectif. Pour un durcissement
  fort, placer une limitation en amont (proxy/WAF).*
- **Validation des entrées** : images de signature restreintes au PNG, taille
  plafonnée, intégrité vérifiée (Pillow) **avant** acceptation ; document
  restreint au PDF non chiffré, lisible, taille plafonnée. Plafonds
  configurables.
- **Journal append-only chaîné** : chaque entrée est liée à la précédente par une
  empreinte SHA-256 ; `write()`/`unlink()` sont bloqués au niveau ORM (en plus de
  l'ACL lecture seule). Toute insertion, suppression ou modification d'une entrée
  rompt la chaîne et est détectable.
- **Inaltérabilité des preuves** : une demande signée ne peut être supprimée.
- **Finalisation idempotente** : verrou de ligne empêchant une double
  finalisation lors de signatures concurrentes.
- **Vérification d'intégrité** disponible à la demande (chaîne du journal +
  empreinte du document scellé + jeton RFC 3161).

## Ancrage de confiance & non-garanties

- La chaîne de hash du journal est une empreinte SHA-256 **sans secret** : elle
  détecte une altération mais, à elle seule, **ne protège pas** contre un acteur
  disposant d'un accès en écriture à la base (qui pourrait recalculer la chaîne).
  L'**ancrage hors de la plateforme** repose sur l'**horodatage RFC 3161**
  (autorité d'horodatage indépendante) — recommandé pour les documents à enjeu.
- La vérification du jeton RFC 3161 au palier 1 contrôle la **concordance de
  l'empreinte** (messageImprint) et le **statut « granted »** ; elle **ne vérifie
  pas** cryptographiquement la signature CMS du jeton contre la chaîne d'AC de la
  TSA (non implémenté à ce jour).
- Le module produit une **signature électronique simple (SES)**, **pas** une
  signature avancée (AES) ni qualifiée (QES).
- L'horodatage RFC 3161 est **optionnel** et désactivé par défaut.

## Clé de chiffrement du sceau (Fernet)

Le certificat de scellement (et sa clé privée) est stocké **chiffré par Fernet**
dans `ir.config_parameter`. La clé Fernet est lue, par ordre de priorité :
`BF_SIGN_FERNET_KEY` (env) → `bf_sign_fernet_key` (`odoo.conf`) → clé partagée
`bf_security_awareness` (env/conf) → paramètre système `bf_sign.fernet_key` (base
de données).

- **Recommandé (durci)** : garder la clé dans l'environnement ou `odoo.conf`. Une
  copie de la base de données ne suffit alors **pas** à déchiffrer le certificat.
- **Option libre-service (Paramètres → Signature électronique)** : un
  administrateur (`base.group_system`) peut générer/coller la clé depuis l'UI ;
  elle est alors stockée en base. **Compromis** : la clé réside dès lors **dans la
  base**, à côté des secrets qu'elle protège — une copie de la base expose les
  deux. La clé n'est jamais renvoyée au navigateur (le champ de saisie est en
  écriture seule, l'état n'affiche que la provenance). env/conf gardent la
  priorité : on peut migrer la clé vers `odoo.conf` à tout moment pour durcir.
- Changer une clé déjà active alors qu'un certificat existe est **refusé** (cela
  rendrait le certificat illisible) ; supprimer d'abord le certificat.

## Bonnes pratiques de déploiement

- Servir l'instance en **HTTPS** uniquement et configurer `web.base.url`
  correctement (les liens de signature en dépendent).
- Activer une **TSA fiable** pour les documents à enjeu (voir `README.md`).
- Restreindre les groupes `Signature / Utilisateur` et `Signature /
  Gestionnaire` aux personnes habilitées.
