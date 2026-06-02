# Règles de stratégie — profil ÉQUILIBRÉ

Ces règles encadrent les signaux générés à chaque run. Objectif : peu d'ordres,
bien justifiés, en protégeant le capital. **Ce ne sont pas des conseils financiers** :
chaque décision et chaque ordre restent à la charge de l'utilisateur.

## 0. Filtre de bruit (données imprécises)
Les cours viennent de recherche web et peuvent être **légèrement décalés** ou
porter sur une autre place de cotation. En conséquence :
- Ignorer les variations intraday **< ±1,5 %** : c'est dans la marge de bruit.
- Toujours vérifier que le cours correspond bien à la **place / devise** de la
  ligne (`yahoo_symbol`), pas à un ADR ou une autre Bourse.
- En cas de doute sérieux sur un cours, classer la ligne en `HOLD` et le signaler.

## 1. Porte de conviction (anti-sur-trading)
N'émettre un ordre **actionnable** (ACHETER / RENFORCER / ALLÉGER / VENDRE) que si
**au moins 2 facteurs concordants** s'alignent, par exemple :
- tendance + actualité,
- franchissement de seuil de risque + dégradation de tendance,
- catalyseur d'actu fort + niveau technique.
Sinon → `HOLD` (conserver), sans notification.

## 2. Prise de profit
- Position en hausse de **≥ +20 %** vs PRU **et** signe d'essoufflement (cours qui
  cale près d'un plus-haut, ou spike d'actu déjà digéré) → envisager d'**ALLÉGER
  de 20 à 33 %** pour sécuriser.
- Spike vertical sur news ponctuelle (rachat, résultat) sans fondamentaux durables
  → alléger plus franchement.

## 3. Gestion du risque / pertes
- Position en baisse **au-delà de −10 %** vs PRU **et** tendance qui se dégrade ou
  catalyseur négatif → envisager de **RÉDUIRE** et proposer un **stop mental**.
- À **−15 %**, réévaluation forcée : couper ou renforcer doit être un choix
  explicite et argumenté, jamais subi.

## 4. Renforcement
- Ne renforcer qu'un **gagnant en tendance haussière**, sur un **repli**, avec une
  actualité **positive ou neutre**.
- Interdit si la ligne dépasse déjà le **plafond de pondération** (cf. §5).

## 5. Diversification & liquidités
- Signaler (drapeau risque) si une **seule ligne > 25 %** du portefeuille.
- Garder un **tampon de liquidités** : ne pas être investi à 100 % quand les
  signaux sont faibles.

## 6. Format de chaque décision
Pour chaque ligne, produire : `ACTION` + taille (qté ou % / montant indicatif) +
niveau de prix indicatif + **une phrase** de justification + niveau de confiance
(faible / moyen / élevé).

## 7. Cadence & marchés
- Runs prévus ~9h / ~13h / ~17h (heure de Paris). Marchés européens ouverts
  ~9h00–17h30.
- Pas de scalping à la seconde : ces règles visent des décisions à l'échelle de la
  **journée / du swing**, cohérentes avec la précision des données.
