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

- Basé sur l'activité GitLab réelle (commits + merge requests)
- Mois inactifs exclus
- Plafond de 1,0 jour par personne et par date
- Normalisation : 218 jours ouvrés × (mois actifs / 12)
- Approche conservatrice : seules les activités clairement identifiables sont classées CII

## Avertissement

Outil d'aide au reporting CII et à l'immobilisation. Les données doivent être croisées avec la comptabilité et les RH avant déclaration.
