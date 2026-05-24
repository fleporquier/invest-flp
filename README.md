# invest-flp — Analyse trading quotidienne (semi-automatique)

Analyse automatique d'un portefeuille **Trade Republic**, plusieurs fois par jour.
L'agent analyse cours + actualités et **propose** des ordres ; **tu les passes
toi-même** dans Trade Republic. Aucun ordre n'est exécuté automatiquement.

> ⚠️ **Pas un conseil financier garanti.** Les signaux sont des aides à la décision,
> argumentées mais faillibles. La décision et l'exécution restent à toi. Le trading
> comporte un risque de perte en capital.

## Comment ça marche

```
Session planifiée (3x/jour, cloud)
  → lit portfolio/positions.json
  → WebSearch : cours + actu de chaque ligne
  → applique strategy/rules.md (profil équilibré)
  → écrit reports/AAAA-MM-JJ-HHMM.md (committé)
  → notif push SI un ordre est proposé
  → tu passes l'ordre dans Trade Republic
```

## Structure

| Fichier | Rôle |
|---|---|
| `portfolio/positions.json` | Tes positions (PRU, qté, cash). **Tu l'édites après chaque ordre.** |
| `strategy/rules.md` | Règles de décision, profil équilibré. |
| `PLAYBOOK.md` | Procédure exécutée à chaque run. |
| `reports/` | Un rapport daté par run (historique). |
| `CLAUDE.md` | Contexte pour toute session. |

## Mise en place du déclencheur planifié

1. Renseigne tes vraies positions dans `portfolio/positions.json`.
2. Dans **Claude Code sur le web**, crée un **déclencheur planifié** (schedule) sur
   ce repo + cette branche, avec comme instruction :
   > `Exécute PLAYBOOK.md`
3. Cadence visée : **~9h, ~13h, ~17h (heure de Paris)**. Les plannings sont souvent
   exprimés en **UTC** :
   - Été (CEST, UTC+2) : 07:00 / 11:00 / 15:00 UTC
   - Hiver (CET, UTC+1) : 08:00 / 12:00 / 16:00 UTC

Doc des déclencheurs et environnements :
https://code.claude.com/docs/en/claude-code-on-the-web

## Limites connues
- **Réseau en liste blanche** : seules les recherches via WebSearch ramènent les
  cours/actu (les API finance directes sont bloquées).
- Cours possiblement **décalés** ou sur une autre place → filtre de bruit ±1,5 % et
  vérification systématique de la devise/place de cotation.
- Cadence adaptée à des décisions **journée/swing**, pas au scalping haute fréquence.
