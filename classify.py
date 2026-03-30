import unicodedata
import pandas as pd
from constants import (
    CII_CODES, NON_CII_CODES, ALL_CODES,
    IMMO_CODES, CHARGES_CODES, ALL_COMPTABLE_CODES, COMPTABLE_DETAILS,
    PROJECT_CODES, MONTHS,
    CII_DETAILS, NON_CII_DETAILS, PROJECT_DETAILS,
)

SOURCE_FILE = "gitlab_all_users_2025_enriched.xlsx"
OUTPUT_FILE = "gitlab_classified.xlsx"

# Mapping projet GitLab → projet CII
GITLAB_PROJECT_MAP = {
    "INDELINE": "EVOLUTIONS INDELINE",
    "Galpe": "CONVERGENCE GALPE INDELINE",
    "infrastructure": "INFRA SAAS",
    "infrastructure-scaleway": "INFRA SAAS",
    "infrastructure-images": "INFRA SAAS",
    "ci-tasks": "INFRA SAAS",
    "kube_simplified": "INFRA SAAS",
    "preliq-functional-tests": "SAAS PRELIQ",
    "newWinPaie": "SAAS PRELIQ",
    "ogrh": "SAAS PRELIQ",
    "vamps-fs": "SAAS PRELIQ",
    "database-templates": "SAAS PRELIQ",
    "batchRepriseDonnees": "SAAS PRELIQ",
}


def normalize_text(value: str) -> str:
    value = str(value or "")
    value = value.lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return value


def normalize_person_key(username: str, author_name: str) -> str:
    username = str(username or "").strip().lower()
    author_name = normalize_text(author_name).replace(" ", "")
    return username or author_name


def complexity_weight(title: str, event_type: str, total_changes: float = 0) -> float:
    t = normalize_text(title)
    weight = 0.20 if event_type == "commit" else 0.45

    complex_terms = {
        "arch": 0.35, "architecture": 0.35, "hexagonal": 0.35,
        "refonte": 0.25, "socle": 0.25, "modulaire": 0.25,
        "java": 0.20, "jdk": 0.20, "jvm": 0.20, "grails": 0.20, "spring boot": 0.25,
        "multi-tenant": 0.30, "multitenant": 0.30, "tenant": 0.25, "saas": 0.20,
        "galpe": 0.20, "convergence": 0.20,
        "optimi": 0.20, "perf": 0.20, "cache": 0.15, "volum": 0.15,
    }

    for term, bonus in complex_terms.items():
        if term in t:
            weight += bonus

    weight += min(len(t) / 120.0, 0.15)

    # Bonus basé sur le volume de changements (commits uniquement)
    if event_type == "commit" and total_changes > 0:
        if total_changes > 500:
            weight += 0.20
        elif total_changes > 200:
            weight += 0.15
        elif total_changes > 100:
            weight += 0.10

    return min(weight, 1.0)


# =========================
# CLASSIFICATION CII (conservatrice)
# =========================

def classify_cii(title: str, description: str = "", changed_files: str = "") -> str:
    t = normalize_text(title) + " " + normalize_text(description)
    files = normalize_text(changed_files)

    # Pour les merge commits, utiliser la description (contient souvent le vrai titre de la MR)
    is_merge = normalize_text(title).startswith("merge branch") or normalize_text(title).startswith("merge remote")

    # ARCHITECTURE — archi hexagonale, modularisation, refonte structurante
    if any(k in t for k in ["hexagonal", "modulaire", "modularisation"]):
        return "ARCHITECTURE"
    if "archi" in t and any(k in t for k in ["module", "refonte", "socle", "structur"]):
        return "ARCHITECTURE"
    # Signal par fichiers : répertoires d'architecture hexagonale (domain/ trop générique, exclu)
    if any(k in files for k in ["hexagonal", "/port/", "/adapter/"]):
        return "ARCHITECTURE"

    # MONTEE DE STACK — montée de version technologique clairement identifiable
    # Uniquement dans le titre (pas description) pour éviter les faux positifs
    tt = normalize_text(title)
    if any(k in tt for k in ["montee de version", "montée de version", "upgrade stack"]):
        return "MONTEE DE STACK"
    if "grails" in tt and any(k in tt for k in ["montee", "montée", "version", "migration"]):
        return "MONTEE DE STACK"
    if any(k in tt for k in ["java 21", "java 17", "jdk 21", "jdk 17"]):
        return "MONTEE DE STACK"
    if "spring boot" in tt and any(k in tt for k in ["migr", "introduction", "poc"]):
        return "MONTEE DE STACK"
    if "stack tech" in tt and not any(k in tt for k in ["fix", "correction", "bug"]):
        return "MONTEE DE STACK"
    if "migration" in tt and any(k in tt for k in ["spring", "swagger", "security", "nexus"]):
        return "MONTEE DE STACK"

    # OPTIMISATION — travaux de performance clairement identifiables
    # "optimisation" seul suffit, mais "optimi" doit être qualifié pour éviter "optimisation imports"
    if any(k in t for k in ["optimisation", "optimization"]):
        # Exclure "optimisation imports" (imports Java, pas perf)
        if "import" in t and not any(k in t for k in ["perf", "volum", "cache", "massif", "lenteur"]):
            pass  # pas CII
        else:
            return "OPTIMISATION"
    if "perf" in t and any(k in t for k in ["lenteur", "amelior", "amélio"]):
        return "OPTIMISATION"
    if "cache" in t and any(k in t for k in ["optimis", "perf", "amelior"]):
        return "OPTIMISATION"

    # MULTI-TENANT — passage SaaS multi-tenant
    if any(k in t for k in ["multi-tenant", "multitenant", "multi tenant"]):
        return "MULTI-TENANT"
    if "tenant" in t and any(k in t for k in ["isolat", "routage", "saas", "config", "log", "migration"]):
        return "MULTI-TENANT"
    if "saas" in t and any(k in t for k in ["adr", "rendre", "passer", "migration", "v2"]):
        return "MULTI-TENANT"
    # Signal par fichiers : config multi-tenant
    if any(k in files for k in ["tenant", "multitenant"]):
        return "MULTI-TENANT"

    # CONVERGENCE GALPE INDELINE
    if "galpe" in t:
        return "CONVERGENCE GALPE INDELINE"
    if "convergence" in t and "indeline" in t:
        return "CONVERGENCE GALPE INDELINE"
    if "flux cnrs" in t or "module cnrs" in t:
        return "CONVERGENCE GALPE INDELINE"
    # Signal par fichiers
    if any(k in files for k in ["galpe", "cnrs"]):
        return "CONVERGENCE GALPE INDELINE"

    # --- Hors CII ---

    # MAINTENANCE — bugfix, corrections
    if any(k in t for k in ["bug", "fix", "hotfix", "correctif", "correction"]):
        return "MAINTENANCE"

    # TESTS
    if any(k in t for k in ["test", "recette", "non-regression", "cucumber", "selenium"]):
        return "TESTS"

    # INFRA — exploitation, CI/CD, deploy
    if any(k in t for k in ["deploy", "docker", "k8s", "kube", "runner", "ci skip",
                             "scaleway", "bastion", "ssh key", "probe"]):
        return "INFRA"

    # FONCTIONNEL — mots-clés métier standards
    if any(k in t for k in ["ajout", "creation", "suppression", "modification",
                             "edition", "affichage", "ecran", "modal", "bouton",
                             "api", "endpoint", "service", "import", "export"]):
        return "FONCTIONNEL"

    # --- Classification par fichiers modifiés pour les événements non classés ---
    if files:
        # Tests
        if any(k in files for k in ["/test/", "test.groovy", "test.java", "spec.groovy",
                                      "steps.groovy", "steps.java", "/functional-tests/"]):
            return "TESTS"
        # Infra
        if any(k in files for k in ["dockerfile", "docker-compose", ".gitlab-ci",
                                      "kubernetes", "k8s", "helm"]):
            return "INFRA"
        # Si des fichiers source sont modifiés, c'est du fonctionnel
        if any(k in files for k in [".groovy", ".java", ".gsp", ".jsx", ".vue", ".ts"]):
            return "FONCTIONNEL"
        # Config, SQL, scripts
        if any(k in files for k in [".sql", ".yml", ".yaml", ".xml", ".properties", ".json"]):
            return "FONCTIONNEL"

    # Merge commits sans signal → AUTRE
    if is_merge:
        return "AUTRE"

    return "AUTRE"


def classify_comptable(cii_code: str, title: str, description: str = "") -> str:
    """Classification comptable : immobilisable vs charges."""
    t = normalize_text(title) + " " + normalize_text(description)

    # Les travaux CII sont toujours immobilisables
    if cii_code in CII_CODES:
        # Architecture, montée de stack, optimisation = maintenance évolutive
        if cii_code in ("MONTEE DE STACK", "OPTIMISATION"):
            return "MAINTENANCE EVOLUTIVE"
        # Architecture, multi-tenant, convergence = développement
        return "DEVELOPPEMENT"

    # Hors CII — classifier selon la nature
    if cii_code == "MAINTENANCE":
        # Refacto structurante = maintenance évolutive (immobilisable)
        if any(k in t for k in ["refacto", "refactoring", "rework", "restructur", "reorganis"]):
            return "MAINTENANCE EVOLUTIVE"
        # Le reste = maintenance corrective (charges)
        return "MAINTENANCE CORRECTIVE"

    if cii_code == "FONCTIONNEL":
        return "DEVELOPPEMENT"

    if cii_code == "TESTS":
        # Tests liés à du développement = immobilisable
        if any(k in t for k in ["nouveau", "nouvelle", "creation", "ajout", "scenario"]):
            return "DEVELOPPEMENT"
        return "MAINTENANCE EVOLUTIVE"

    if cii_code == "INFRA":
        return "EXPLOITATION"

    if cii_code == "AUTRE":
        # Merge commits, revue de code, divers
        if any(k in t for k in ["merge branch", "merge remote", "code review", "revue de code", "wip"]):
            return "SUPPORT"
        # Par défaut les AUTRE sans signal clair = support
        return "SUPPORT"

    return "SUPPORT"


def classify_project(title: str, description: str = "", project_name: str = "", changed_files: str = "") -> str:
    # D'abord, utiliser le projet GitLab si on a un mapping direct
    if project_name in GITLAB_PROJECT_MAP:
        base_project = GITLAB_PROJECT_MAP[project_name]
    else:
        base_project = "SAAS PRELIQ"

    # Affiner avec le contenu du titre/description/fichiers
    t = normalize_text(title) + " " + normalize_text(description)
    files = normalize_text(changed_files)
    if any(k in t for k in ["java 21", "java 17", "jdk", "jvm",
                             "grails 6", "grails 5", "spring boot"]):
        return "JAVA MODERNISATION"
    if any(k in t for k in ["galpe", "cnrs", "convergence"]):
        return "CONVERGENCE GALPE INDELINE"
    if any(k in files for k in ["galpe", "cnrs"]):
        return "CONVERGENCE GALPE INDELINE"

    return base_project


def load_events() -> pd.DataFrame:
    mr = pd.read_excel(SOURCE_FILE, sheet_name="merge_requests")
    commits = pd.read_excel(SOURCE_FILE, sheet_name="commits")

    mr["event_type"] = "mr"
    mr["event_date"] = pd.to_datetime(mr["merged_at"], errors="coerce").fillna(
        pd.to_datetime(mr["created_at"], errors="coerce")
    )
    mr["title"] = mr["title"].astype(str)
    mr["description"] = mr.get("description", pd.Series(dtype=str)).fillna("").astype(str)
    mr["project_name"] = mr.get("project_name", "").astype(str)
    mr["total_changes"] = 0
    mr["changed_files"] = mr.get("changed_files", pd.Series(dtype=str)).fillna("").astype(str)
    mr["person_key"] = [
        normalize_person_key(u, a) for u, a in zip(mr.get("username", ""), mr.get("author_name", ""))
    ]
    mr["display_name"] = mr.get("author_name", mr.get("username", "")).astype(str)
    mr = mr[["person_key", "display_name", "title", "description", "project_name",
             "total_changes", "changed_files", "event_date", "event_type"]]

    commits["event_type"] = "commit"
    commits["event_date"] = pd.to_datetime(commits["committed_date"], errors="coerce")
    commits["title"] = commits["title"].astype(str)
    commits["description"] = commits.get("message", pd.Series(dtype=str)).fillna("").astype(str)
    commits["project_name"] = commits.get("project_name", "").astype(str)
    commits["total_changes"] = commits.get("total_changes", 0).fillna(0)
    commits["changed_files"] = commits.get("changed_files", pd.Series(dtype=str)).fillna("").astype(str)
    commits["person_key"] = [
        normalize_person_key(u, a) for u, a in zip(commits.get("username", ""), commits.get("author_name", ""))
    ]
    commits["display_name"] = commits.get("author_name", commits.get("username", "")).astype(str)
    commits = commits[["person_key", "display_name", "title", "description", "project_name",
                        "total_changes", "changed_files", "event_date", "event_type"]]

    events = pd.concat([mr, commits], ignore_index=True)
    events = events.dropna(subset=["event_date"])
    events = events[events["event_date"].dt.year == 2025].copy()
    events["date"] = events["event_date"].dt.date
    events["month_num"] = events["event_date"].dt.month
    events["month_name"] = events["month_num"].map(dict(MONTHS))

    # Classification (titre + description + project_name + changed_files)
    events["cii_code"] = [
        classify_cii(t, d, f)
        for t, d, f in zip(events["title"], events["description"], events["changed_files"])
    ]
    events["is_cii"] = events["cii_code"].isin(CII_CODES)
    events["project"] = [
        classify_project(t, d, p, f)
        for t, d, p, f in zip(events["title"], events["description"], events["project_name"], events["changed_files"])
    ]
    events["weight"] = [
        complexity_weight(t, et, tc)
        for t, et, tc in zip(events["title"], events["event_type"], events["total_changes"])
    ]
    events["comptable"] = [
        classify_comptable(c, t, d)
        for c, t, d in zip(events["cii_code"], events["title"], events["description"])
    ]
    events["is_immo"] = events["comptable"].isin(IMMO_CODES)

    # Résolution du display_name (le plus fréquent par person_key)
    display = (
        events.groupby(["person_key", "display_name"]).size().reset_index(name="n")
        .sort_values(["person_key", "n", "display_name"], ascending=[True, False, True])
        .drop_duplicates("person_key")
        .set_index("person_key")["display_name"]
    )
    events["display_name"] = events["person_key"].map(display)

    return events


def build_legend() -> pd.DataFrame:
    rows = []
    for c in CII_CODES:
        rows.append({"Type": "CII", "Code": c, "Description": CII_DETAILS[c]})
    for c in NON_CII_CODES:
        rows.append({"Type": "HORS CII", "Code": c, "Description": NON_CII_DETAILS[c]})
    for c in ALL_COMPTABLE_CODES:
        immo = "Immobilisable" if c in IMMO_CODES else "Charges"
        rows.append({"Type": f"COMPTABLE ({immo})", "Code": c, "Description": COMPTABLE_DETAILS[c]})
    for p in PROJECT_CODES:
        rows.append({"Type": "PROJET", "Code": p, "Description": PROJECT_DETAILS[p]})
    return pd.DataFrame(rows)


def main():
    events = load_events()
    legend = build_legend()

    cii_events = events[events["is_cii"]]
    immo_events = events[events["is_immo"]]

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        events.to_excel(writer, sheet_name="events", index=False)
        legend.to_excel(writer, sheet_name="légende", index=False)

    print(f"✅ Fichier classifié généré : {OUTPUT_FILE}")
    print(f"   → {len(events)} événements total")
    print()
    print(f"   CII : {len(cii_events)} ({len(cii_events)*100//len(events)}%)")
    for code in CII_CODES:
        n = (events["cii_code"] == code).sum()
        if n > 0:
            print(f"     {code}: {n}")
    print()
    print(f"   Hors CII : {len(events) - len(cii_events)} ({(len(events) - len(cii_events))*100//len(events)}%)")
    for code in NON_CII_CODES:
        n = (events["cii_code"] == code).sum()
        if n > 0:
            print(f"     {code}: {n}")
    print()
    print(f"   Immobilisable : {len(immo_events)} ({len(immo_events)*100//len(events)}%)")
    for code in IMMO_CODES:
        n = (events["comptable"] == code).sum()
        if n > 0:
            print(f"     {code}: {n}")
    print()
    print(f"   Charges : {len(events) - len(immo_events)} ({(len(events) - len(immo_events))*100//len(events)}%)")
    for code in CHARGES_CODES:
        n = (events["comptable"] == code).sum()
        if n > 0:
            print(f"     {code}: {n}")


if __name__ == "__main__":
    main()
