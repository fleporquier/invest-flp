# Contexte du repo

Système d'**analyse trading quotidienne** du portefeuille Trade Republic de
l'utilisateur. Semi-automatique : l'agent analyse et **propose** des ordres,
l'utilisateur les passe **manuellement** dans Trade Republic.

## Si tu es lancé par un déclencheur planifié
Exécute `PLAYBOOK.md` de bout en bout, puis termine.

## Fichiers clés
- `portfolio/positions.json` — positions de référence (édité par l'utilisateur après chaque ordre).
- `strategy/rules.md` — règles de décision (profil équilibré).
- `PLAYBOOK.md` — procédure exécutée à chaque run.
- `reports/` — rapports datés (un par run).

## Contraintes d'environnement importantes
- Réseau en **liste blanche** : `curl`/WebFetch vers les API finance sont **bloqués**.
- **WebSearch fonctionne** : c'est l'unique canal pour cours + actualités.
- Cours possiblement **décalés** / mauvaise place de cotation → filtre de bruit ±1,5 %
  et vérification systématique de la devise/place (cf. `strategy/rules.md`).

## Garde-fous
- Ne jamais passer d'ordre réel ; seulement proposer.
- Ne pas modifier `positions.json` automatiquement.
- Pas de conseil financier garanti ; la décision revient à l'utilisateur.
