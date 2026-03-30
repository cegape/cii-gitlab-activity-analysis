# CII GitLab Activity Analysis

Reconstruction de l'activité développeur à partir de GitLab pour le reporting **CII (Crédit Impôt Innovation)** et l'**immobilisation des coûts de développement**.

## Pipeline

```
GitLab API → activity-extract-enhanced.py → classify.py → (revue manuelle) → format.py
                                                                             → participation.py
```

## Configuration

Créer un fichier `.env` :

```
GITLAB_URL=https://gitlab.com/api/v4     # optionnel
GITLAB_TOKEN=glpat-xxx
GITLAB_USERNAMES=user1,user2,user3
YEAR=2025                                 # optionnel
```

## Étape 1 — Extraction

Extrait les MR, commits et fichiers modifiés de chaque utilisateur depuis GitLab.

```
python3 activity-extract-enhanced.py
```

- Output : `gitlab_all_users_2025_enriched.xlsx`
- Colonnes : titre, description, fichiers modifiés, stats (additions/deletions), projet GitLab
- Cache : `.changed_files_cache.json` — reprend automatiquement en cas d'interruption
- Rate limit : respecte la limite GitLab de 2000 req/min avec marge de sécurité

Pour ajouter un utilisateur sans refaire toute l'extraction :

```
python3 add-user-extract.py <username>
```

## Étape 2 — Classification

Double classification de chaque événement :
- **Axe CII** : éligible innovation ou hors CII
- **Axe comptable** : immobilisable ou charges

```
python3 classify.py
```

- Output : `gitlab_classified.xlsx` (onglets "events" + "légende")
- Classification basée sur : titre, description, fichiers modifiés, projet GitLab
- Colonnes éditables manuellement : `cii_code`, `comptable`, `project`, `weight`

### Codes CII (éligibles)

| Code | Description |
|---|---|
| ARCHITECTURE | Architecture hexagonale, modularisation, refonte de socle |
| MONTEE DE STACK | Montée de version Java/Grails/Spring Boot, migration frameworks |
| OPTIMISATION | Performance, cache, volumétrie |
| MULTI-TENANT | Passage SaaS multi-tenant |
| CONVERGENCE GALPE INDELINE | Convergence Galpe vers Indeline, flux CNRS |

### Codes hors CII

MAINTENANCE, FONCTIONNEL, TESTS, INFRA, AUTRE

### Catégories comptables

| Catégorie | Immobilisable ? |
|---|---|
| DEVELOPPEMENT | Oui |
| MAINTENANCE EVOLUTIVE | Oui |
| MAINTENANCE CORRECTIVE | Non (charges) |
| EXPLOITATION | Non (charges) |
| SUPPORT | Non (charges) |

## Étape 3 — Tableaux de sortie

```
python3 format.py
```

- Output : `tableaux_CII_mensuels_realistes.xlsx`
- Onglets : Annuel CII, Annuel IMMO, Légende, Ressources, Détail journalier, 12 feuilles CII mensuelles, 12 feuilles IMMO mensuelles

## Participation

Classement des développeurs par indice de participation, ventilé CII et immobilisation.

```
python3 participation.py
```

- Output : `participation.xlsx`

## Méthodologie

### Calcul du temps passé

Le calcul repose sur l'activité GitLab réelle (commits + merge requests) :

1. **1 jour d'activité = 1 jour.** Si un développeur a au moins un événement GitLab sur une date, cette date compte pour 1 jour travaillé.

2. **Ventilation par catégorie au prorata.** Si un développeur a N événements dans la journée, chaque événement reçoit 1/N de la journée. Les fractions sont ensuite sommées par catégorie (CII, hors CII, comptable, projet).

   Exemple : un développeur a 4 événements le 15 janvier (1 ARCHITECTURE, 1 OPTIMISATION, 2 FONCTIONNEL). La journée de 1.0 jour est répartie : ARCHITECTURE = 0.25, OPTIMISATION = 0.25, FONCTIONNEL = 0.50.

3. **Plafond de 1,0 jour par personne et par date.** Quel que soit le nombre d'événements, une journée ne peut pas dépasser 1 jour.

### Principes

- Mois inactifs exclus
- Approche conservatrice : seules les activités clairement identifiables sont classées CII
- Classification basée sur le titre, la description, les fichiers modifiés et le projet GitLab

## Avertissement

Outil d'aide au reporting CII et à l'immobilisation. Les données doivent être croisées avec la comptabilité et les RH avant déclaration.
