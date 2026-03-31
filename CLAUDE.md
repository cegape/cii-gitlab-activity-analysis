# CLAUDE.md

## Projet

Outil de reporting CII (Crédit Impôt Innovation) et d'immobilisation des coûts de développement, basé sur l'activité GitLab.

## Pipeline

```
activity-extract-enhanced.py → classify.py → format.py
                                           → participation.py
                                           → report.py <username|me>
```

## Configuration

Fichier `.env` à la racine :
- `GITLAB_TOKEN` : token d'accès GitLab
- `GITLAB_USERNAMES` : liste ordonnée des usernames (l'ordre est respecté dans les tableaux de sortie)
- `GITLAB_URL` : URL de l'API GitLab (défaut : gitlab.com)
- `YEAR` : année d'extraction (défaut : 2025)

## Conventions de code

- Python 3.11+
- Pas de boucles imbriquées de plus de 1 niveau — extraire dans des fonctions
- Les constantes partagées sont dans `constants.py`
- Les fichiers Excel générés (*.xlsx) sont dans le `.gitignore`

## Scripts

- `activity-extract-enhanced.py` : extraction GitLab avec cache (`.changed_files_cache.json`)
- `add-user-extract.py <username>` : ajout incrémental d'un utilisateur
- `classify.py` : double classification CII + comptable (immobilisation)
- `format.py` : tableaux Excel mensuels et annuels
- `participation.py` : scoring de participation gaussien
- `report.py <username|me>` : rapport personnel

## Classification

- **CII** (conservatrice) : ARCHITECTURE, MONTEE DE STACK, OPTIMISATION, MULTI-TENANT, CONVERGENCE GALPE INDELINE
- **Comptable** : DEVELOPPEMENT, MAINTENANCE EVOLUTIVE (immobilisables) / MAINTENANCE CORRECTIVE, EXPLOITATION, SUPPORT (charges)
- Basée sur : titre + description + fichiers modifiés + projet GitLab
- 1 jour d'activité = 1 jour, réparti au prorata du nombre d'événements
