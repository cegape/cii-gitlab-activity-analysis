import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

# =========================
# CONFIG
# =========================

SOURCE_FILE = "gitlab_all_users_2025.xlsx"
OUTPUT_FILE = "tableaux_CII_mensuels_realistes.xlsx"

# 🔥 NOUVEAUX CODES
CII_CODES = [
    "ARCHI",
    "ÉVOLUTIONS",
    "DATA",
    "RÈGLES DE GESTION",
    "UI/UX",
    "API REST",
    "PERF ET VOLUMETRIE",
    "INTERFACES NON API",
    "REFACTO",
    "QA"
]

# mapping ancien → nouveau
CODE_MAP = {
    "CII-01": "ARCHI",
    "CII-02": "ÉVOLUTIONS",
    "CII-03": "DATA",
    "CII-04": "RÈGLES DE GESTION",
    "CII-05": "UI/UX",
    "CII-06": "API REST",
    "CII-07": "PERF ET VOLUMETRIE",
    "CII-08": "INTERFACES NON API",
    "CII-09": "REFACTO",
    "CII-10": "QA"
}

# =========================
# LIBELLES + DETAILS AUDIT
# =========================

CII_LABELS = {
    "ARCHI": "Conception et évolution d’architectures fonctionnelles complexes",
    "ÉVOLUTIONS": "Développement de fonctionnalités métiers innovantes",
    "DATA": "Modélisation et évolution de structures de données complexes",
    "RÈGLES DE GESTION": "Implémentation de règles de gestion avancées",
    "UI/UX": "Conception d’interfaces utilisateurs dynamiques",
    "API REST": "Développement de services et API",
    "PERF ET VOLUMETRIE": "Optimisation des performances",
    "INTERFACES NON API": "Intégration de flux externes",
    "REFACTO": "Refactorisation et fiabilisation",
    "QA": "Tests et validation"
}

CII_DETAILS = {
    "ARCHI": (
        "Travaux de conception technique et fonctionnelle visant à structurer ou faire évoluer "
        "l’architecture globale des logiciels, notamment l’organisation des composants, la "
        "répartition des responsabilités, les flux entre modules et la prise en compte de "
        "contraintes métier transverses."
    ),
    "ÉVOLUTIONS": (
        "Développement d’évolutions fonctionnelles apportant de nouveaux comportements applicatifs "
        "ou enrichissant les fonctionnalités existantes, afin de répondre à des besoins métier "
        "spécifiques dans les domaines SIRH, paie ou gestion du risque chômage."
    ),
    "DATA": (
        "Conception, adaptation et fiabilisation des structures de données, référentiels et modèles "
        "métier, incluant l’évolution de schémas, la gestion de nomenclatures et la prise en compte "
        "de nouvelles informations fonctionnelles ou réglementaires."
    ),
    "RÈGLES DE GESTION": (
        "Implémentation de logiques métier complexes telles que validations, contrôles, workflows, "
        "conditions de traitement, règles réglementaires ou calculs métier nécessitant une "
        "formalisation précise dans l’application."
    ),
    "UI/UX": (
        "Développement et amélioration d’interfaces utilisateurs dynamiques, incluant écrans de "
        "saisie, modales, tableaux interactifs et parcours utilisateur, afin de rendre exploitables "
        "des fonctionnalités métier complexes."
    ),
    "API REST": (
        "Conception ou évolution de services applicatifs exposés par API, permettant l’échange "
        "structuré de données et l’orchestration de traitements entre composants logiciels ou avec "
        "des systèmes tiers."
    ),
    "PERF ET VOLUMETRIE": (
        "Travaux d’optimisation visant à améliorer les temps de réponse, la capacité de traitement "
        "et le comportement des applications en contexte de volumétrie importante ou de traitements "
        "techniques intensifs."
    ),
    "INTERFACES NON API": (
        "Mise en place ou évolution d’interfaces techniques hors API REST, telles que imports, "
        "exports, traitements batch, échanges de fichiers ou mécanismes d’intégration avec des "
        "référentiels et flux externes."
    ),
    "REFACTO": (
        "Travaux de restructuration et d’amélioration du code existant afin d’en accroître la "
        "maintenabilité, la robustesse, la lisibilité et la fiabilité, sans se limiter à de simples "
        "corrections ponctuelles."
    ),
    "QA": (
        "Activités de validation technique et de maîtrise de la qualité logicielle, incluant tests, "
        "vérifications de conformité, sécurisation des évolutions, revue de comportements attendus "
        "et contrôle de non-régression."
    )
}


MONTHS = [
    (1,"Janv"),(2,"Févr"),(3,"Mars"),(4,"Avr"),
    (5,"Mai"),(6,"Juin"),(7,"Juil"),(8,"Août"),
    (9,"Sept"),(10,"Oct"),(11,"Nov"),(12,"Déc")
]

MIN_ACTIVITY_PER_MONTH = 1.0
FULL_YEAR_DAYS = 218

# =========================
# LOAD
# =========================

df = pd.read_excel(SOURCE_FILE, sheet_name="merge_requests")
df.columns = df.columns.astype(str)
df = df.loc[:, ~df.columns.duplicated()]

df["username"] = df.get("author_name", df.get("username")).astype(str)

df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
df["merged_at"] = pd.to_datetime(df["merged_at"], errors="coerce")
df["date"] = df["merged_at"].fillna(df["created_at"])

df = df[df["date"].dt.year == 2025]

df["month"] = df["date"].dt.month
month_map = dict(MONTHS)
df["month_name"] = df["month"].map(month_map)

df["duration_days"] = (df["merged_at"] - df["created_at"]).dt.days
df["duration_days"] = df["duration_days"].fillna(1).clip(lower=1)
df = df[df["duration_days"] < 90]

# =========================
# CLASSIFICATION
# =========================

def classify(t):
    t = str(t).lower()
    if "ref" in t: return "CII-03"
    if "modal" in t or "ui" in t: return "CII-05"
    if "workflow" in t or "gestion" in t: return "CII-04"
    if "import" in t: return "CII-08"
    if "perf" in t: return "CII-07"
    if "fix" in t or "bug" in t: return "CII-09"
    if "api" in t: return "CII-06"
    if "test" in t: return "CII-10"
    return "CII-02"

df["cii_code"] = df["title"].apply(classify)

# 🔥 conversion vers nouveaux codes
df["cii_code"] = df["cii_code"].map(CODE_MAP)

# =========================
# MOIS ACTIFS
# =========================

monthly_activity = df.groupby(["username","month_name"])["duration_days"].sum().reset_index()

active_map = {}
for u,g in monthly_activity.groupby("username"):
    active = g[g["duration_days"] >= MIN_ACTIVITY_PER_MONTH]["month_name"].tolist()
    active_map[u] = active

# =========================
# NORMALISATION
# =========================

grouped = df.groupby(["username","cii_code","month_name"], as_index=False)["duration_days"].sum()

rows = []

for u,g in grouped.groupby("username"):
    active_months = active_map.get(u, [])
    if not active_months:
        continue

    g = g[g["month_name"].isin(active_months)]

    total_raw = g["duration_days"].sum()
    target = FULL_YEAR_DAYS * (len(active_months)/12)

    for _,r in g.iterrows():
        val = (r["duration_days"]/total_raw)*target if total_raw else 0
        rows.append({
            "username":u,
            "code":r["cii_code"],
            "month":r["month_name"],
            "jours":val
        })

res = pd.DataFrame(rows)
users = sorted(df["username"].unique())

# =========================
# PIVOT
# =========================

def build_month(m):
    temp = res[res["month"]==m]
    pivot = temp.pivot_table(index="username",columns="code",values="jours",aggfunc="sum")
    pivot = pivot.reindex(index=users,columns=CII_CODES,fill_value=0).round(1)

    pivot["TOTAL"] = pivot.sum(axis=1)
    pivot.loc["TOTAL"] = pivot.sum()

    return pivot

# =========================
# LEGEND
# =========================

legend_df = pd.DataFrame([
    {
        "Code": code,
        "Intitulé": CII_LABELS[code],
        "Détail": CII_DETAILS[code]
    }
    for code in CII_CODES
])


# =========================
# RESSOURCES
# =========================

reverse_month = {v:k for k,v in dict(MONTHS).items()}

resources_rows = []

for u in users:
    active = active_map.get(u, [])
    if not active:
        continue

    nums = sorted([reverse_month[m] for m in active])
    start = min(nums)
    end = max(nums)
    nb = len(nums)
    target = FULL_YEAR_DAYS * (nb/12)

    resources_rows.append({
        "Nom": u,
        "Mois début": start,
        "Mois fin": end,
        "Mois actifs": nb,
        "Jours cibles": round(target,1)
    })

resources_df = pd.DataFrame(resources_rows)

# =========================
# EXPORT (ORDRE CORRECT)
# =========================

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:

    # 1. Annuel
    pd.DataFrame(index=users+["TOTAL"],columns=CII_CODES+["TOTAL"]).to_excel(writer, sheet_name="Annuel")

    # 2. Légende
    legend_df.to_excel(writer, sheet_name="Légende", index=False)

    # 3. Ressources
    resources_df.to_excel(writer, sheet_name="Ressources", index=False)

    # 4. Mois
    for _,m in MONTHS:
        build_month(m).to_excel(writer, sheet_name=m)

# =========================
# FORMULES ANNUEL
# =========================

wb = load_workbook(OUTPUT_FILE)
ws = wb["Annuel"]
months = [m for _,m in MONTHS]

for r,u in enumerate(users+["TOTAL"], start=2):
    ws.cell(row=r,column=1,value=u)

    for c in range(2,len(CII_CODES)+2):
        col = get_column_letter(c)
        refs = [f"'{m}'!{col}{r}" for m in months]
        ws.cell(row=r,column=c,value="="+"+".join(refs))

    ws.cell(row=r,column=len(CII_CODES)+2,
        value=f"=SUM(B{r}:{get_column_letter(len(CII_CODES)+1)}{r})"
    )

wb.save(OUTPUT_FILE)

print("✅ VERSION FINALE PROPRE GÉNÉRÉE")