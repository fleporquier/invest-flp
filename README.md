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

## Mise en place de la routine planifiée

La planification passe par les **Routines** (claude.ai/code/routines, ou `/schedule`).

1. Tiens à jour tes positions dans `portfolio/positions.json` **sur la branche
   `claude/daily-trading-analysis-SyOa4`** (c'est là que la routine lit et écrit).
2. Crée une **routine** : repo `fleporquier/invest-flp`, environnement **Default**
   (Trusted suffit — WebSearch fonctionne, pas besoin d'accès « Full »).
3. **Prompt** de la routine (auto-suffisant ; il bascule sur la bonne branche car la
   routine clone `main` par défaut) :
   > `D'abord : git fetch origin claude/daily-trading-analysis-SyOa4 && git checkout
   > claude/daily-trading-analysis-SyOa4. Ensuite exécute PLAYBOOK.md de bout en bout :
   > lis positions.json et strategy/rules.md, récupère cours + actu via WebSearch
   > (profil équilibré), écris un rapport daté dans reports/, signale les ordres à
   > passer, puis commit et push sur cette branche. Termine après le rapport.`
4. **Déclencheur Schedule**, **lundi→vendredi**, à **09:00 / 13:00 / 17:00 (heure de
   Paris)**. Les heures sont saisies en heure locale et **converties automatiquement**
   (gère l'heure d'été) — aucune conversion UTC à faire.
   - Compact : 1 cron `0 9,13,17 * * 1-5` via `/schedule update` (vérifie qu'il
     résout bien en heure de Paris ; sinon préférer 3 presets « Weekdays »).
   - Robuste : 3 presets « Weekdays » à 09:00, 13:00, 17:00.
5. Intervalle minimum d'une routine : **1 h**. Consomme le quota d'abonnement + un
   plafond quotidien de runs.

Doc : https://code.claude.com/docs/en/routines

## Limites connues
- **Réseau en liste blanche** : seules les recherches via WebSearch ramènent les
  cours/actu (les API finance directes sont bloquées).
- Cours possiblement **décalés** ou sur une autre place → filtre de bruit ±1,5 % et
  vérification systématique de la devise/place de cotation.
- Cadence adaptée à des décisions **journée/swing**, pas au scalping haute fréquence.
