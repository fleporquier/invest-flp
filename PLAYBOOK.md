# PLAYBOOK — Analyse trading automatique (à exécuter à chaque run planifié)

Tu es l'agent d'analyse du portefeuille. Exécute **exactement** ces étapes, puis
termine. Profil de risque : **équilibré** (voir `strategy/rules.md`).

> **Pré-requis branche** : la routine clone `main`, qui ne contient pas ce fichier.
> Le prompt de la routine commence donc par `git fetch origin
> claude/daily-trading-analysis-SyOa4 && git checkout
> claude/daily-trading-analysis-SyOa4` avant de lire ce PLAYBOOK. Tu travailles
> donc déjà sur cette branche.

## Étape 1 — Charger l'état
1. Lis `portfolio/positions.json` (positions, PRU, devise, place de cotation, cash).
2. Lis `strategy/rules.md` (règles et seuils à appliquer).

## Étape 2 — Collecter les données marché (via WebSearch)
> `curl`/WebFetch vers les API finance sont **bloqués** par la liste blanche réseau.
> **Seul WebSearch fonctionne** pour les cours/actu. Utilise-le.

Pour **chaque** ligne du portefeuille :
- Cours actuel **sur la bonne place / devise** (`yahoo_symbol`), et variation du jour.
- Actualité matérielle des **dernières 24 h** (résultats, guidance, news sectorielle,
  upgrade/downgrade analystes).
Puis contexte global : grands indices (CAC 40, EuroStoxx, Nasdaq) et tendance du
secteur concerné.

⚠️ Identifie chaque titre par son **ISIN**, pas seulement par son nom (plusieurs
versions d'un même ETF ont des cours très différents — ex. EXA1 ~18 € vs EXX1 ~26 €).
⚠️ Vérifie la cohérence cours/devise. Si un cours paraît douteux (mauvaise place,
ordre de grandeur incohérent), marque la ligne `HOLD` et explique le doute.
⚠️ **Ne jamais « corriger » `positions.json` à partir d'un prix web** : si le cours
web s'écarte fortement de `last_price`, c'est probablement un mauvais ticker/place —
**signale l'écart** (drapeau de risque) sans recalculer le portefeuille sur le prix
web, et garde `quantity` / `avg_buy_price` du fichier comme référence.

## Étape 3 — Analyser ligne par ligne
Applique `strategy/rules.md`. Pour chaque ligne, décide :
`HOLD` | `RENFORCER` | `ALLÉGER` | `VENDRE` | `POSER UN STOP`
avec : taille indicative, niveau de prix, **une phrase** de justification, et
confiance (faible/moyen/élevé). Respecte la **porte de conviction** (§1) et le
**filtre de bruit** (§0) : en l'absence de signal net → `HOLD`.

## Étape 4 — Vue portefeuille
Calcule l'allocation par ligne, le cash, et lève les **drapeaux de risque**
(concentration > 25 %, perte au-delà des seuils, etc.).

## Étape 5 — Écrire le rapport
Crée `reports/AAAA-MM-JJ-HHMM.md` (heure de Paris) avec :
- En-tête : date/heure, contexte marché en 2-3 lignes.
- Tableau par ligne : cours, var. jour, P&L vs PRU, **ACTION**, justification, confiance.
- Section **« ORDRES À PASSER »** : la liste claire des ordres actionnables (vide si
  aucun). Format par ordre : `ACTION — instrument — quantité/montant — prix indicatif`.
- Drapeaux de risque éventuels.

## Étape 5b — Snapshot JSON pour le dashboard public

Écris **aussi** `dashboard/portfolio.json` (crée le dossier si nécessaire). Ce
fichier alimente le dashboard GitHub Pages — il est **public**, donc **n'y mets
JAMAIS** de montants en euros, de quantités, de cash ou de valeurs absolues.

Schéma à respecter (champs autorisés uniquement) :

```json
{
  "generated_at": "AAAA-MM-JJTHH:MM:SS+02:00",
  "broker_count": 2,
  "positions": [
    {
      "ticker": "ASML",
      "name": "ASML Holding",
      "pnl_pct": 11.4,
      "signal": "HOLD",
      "confidence": "élevé",
      "rationale": "1 phrase, sans aucun montant"
    }
  ],
  "orders_to_consider": [
    {
      "action": "ALLÉGER",
      "instrument": "D-Wave Quantum (QBTS)",
      "details": "vendre environ la moitié de la ligne",
      "rationale": "1 phrase, en termes relatifs"
    }
  ],
  "risk_flags": ["Concentration sectorielle élevée."]
}
```

Règles :
- `signal` ∈ `HOLD` | `ACHETER` | `RENFORCER` | `ALLÉGER` | `VENDRE` | `POSER UN STOP`.
- `confidence` ∈ `faible` | `moyen` | `élevé`.
- `pnl_pct` est un nombre (positif/négatif), **percentage uniquement**.
- `details` / `rationale` : exprime les tailles en **fraction / pourcentage** ou
  en termes relatifs (« ~la moitié », « ~1/3 »), **jamais en euros ni en parts**.

## Étape 6 — Notifier (seulement si ordre actionnable)
- S'il y a **au moins un ordre** dans « ORDRES À PASSER » → envoie une **notification
  push** résumant le(s) ordre(s) (ex. « 2 ordres proposés : ALLÉGER ASML, RENFORCER X »).
- Si **uniquement des HOLD** → **pas de notification**, juste le rapport committé.

## Étape 7 — Committer
`git add reports/ dashboard/portfolio.json` puis commit (« rapport trading
AAAA-MM-JJ HHMM ») et `git push origin claude/daily-trading-analysis-SyOa4`
(branche déjà active, droits de push par défaut OK car préfixée `claude/`). Ne
modifie pas `positions.json` toi-même : c'est l'utilisateur qui le met à jour
après avoir passé ses ordres.

## Rappels
- Tu ne passes **jamais** d'ordre : tu proposes, l'utilisateur exécute dans TR.
- Pas de conseil financier garanti ; signaux argumentés, décision à l'utilisateur.
- Sois concis et concret. Pas de signal = un résultat valide (et fréquent).
