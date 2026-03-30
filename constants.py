CII_CODES = [
    "ARCHITECTURE",
    "MONTEE DE STACK",
    "OPTIMISATION",
    "MULTI-TENANT",
    "CONVERGENCE GALPE INDELINE",
]

NON_CII_CODES = [
    "MAINTENANCE",
    "FONCTIONNEL",
    "TESTS",
    "INFRA",
    "AUTRE",
]

ALL_CODES = CII_CODES + NON_CII_CODES

# =========================
# CATÉGORIES COMPTABLES (immobilisation)
# =========================

IMMO_CODES = [
    "DEVELOPPEMENT",
    "MAINTENANCE EVOLUTIVE",
]

CHARGES_CODES = [
    "MAINTENANCE CORRECTIVE",
    "EXPLOITATION",
    "SUPPORT",
]

ALL_COMPTABLE_CODES = IMMO_CODES + CHARGES_CODES

COMPTABLE_DETAILS = {
    "DEVELOPPEMENT": "Nouvelles fonctionnalités, évolutions, MVP — immobilisable.",
    "MAINTENANCE EVOLUTIVE": "Refacto structurante, montée de stack, optimisation — immobilisable.",
    "MAINTENANCE CORRECTIVE": "Bugfix, hotfix, corrections — charges.",
    "EXPLOITATION": "Infra, CI/CD, déploiement, monitoring — charges.",
    "SUPPORT": "Merge commits, revue de code, divers — charges.",
}

# =========================
# PROJETS
# =========================

PROJECT_CODES = [
    "JAVA MODERNISATION",
    "SAAS PRELIQ",
    "INFRA SAAS",
    "EVOLUTIONS INDELINE",
    "CONVERGENCE GALPE INDELINE",
]

MONTHS = [
    (1, "Janv"), (2, "Févr"), (3, "Mars"), (4, "Avr"),
    (5, "Mai"), (6, "Juin"), (7, "Juil"), (8, "Août"),
    (9, "Sept"), (10, "Oct"), (11, "Nov"), (12, "Déc"),
]

CII_DETAILS = {
    "ARCHITECTURE": "Architecture hexagonale, modularisation, refonte de socle, design technique structurant.",
    "MONTEE DE STACK": "Montée de version Java/Grails/Spring Boot, migration de frameworks, modernisation du socle technique.",
    "OPTIMISATION": "Travaux de performance, cache, volumétrie, optimisation des traitements.",
    "MULTI-TENANT": "Conception et architecture du passage SaaS multi-tenant (isolation données, routage tenants).",
    "CONVERGENCE GALPE INDELINE": "Convergence Galpe vers Indeline, flux et intégrations associées.",
}

NON_CII_DETAILS = {
    "MAINTENANCE": "Bugfix, corrections, hotfix, maintenance corrective courante.",
    "FONCTIONNEL": "Évolutions fonctionnelles standards, ajouts de fonctionnalités métier.",
    "TESTS": "Tests fonctionnels, QA, recette, non-régression.",
    "INFRA": "Exploitation, CI/CD, déploiement, infrastructure, configuration.",
    "AUTRE": "Merge commits, divers, non catégorisable.",
}

PROJECT_DETAILS = {
    "JAVA MODERNISATION": "Montée de version Java, compatibilité runtime, dépendances, modernisation du socle.",
    "SAAS PRELIQ": "Industrialisation et évolutions de Preliq en mode SaaS.",
    "INFRA SAAS": "Infra dev, hébergement, CI/CD, déploiement, exploitation SaaS.",
    "EVOLUTIONS INDELINE": "Évolutions fonctionnelles et techniques d'Indeline.",
    "CONVERGENCE GALPE INDELINE": "Convergence Galpe/Indeline, flux et intégrations associées.",
}

DISPLAY_COLUMNS = CII_CODES + ["TOTAL CII"] + NON_CII_CODES + ["TOTAL HORS CII"] + PROJECT_CODES + ["TOTAL"]
COMPTABLE_DISPLAY = IMMO_CODES + ["TOTAL IMMO"] + CHARGES_CODES + ["TOTAL CHARGES"] + PROJECT_CODES + ["TOTAL"]
