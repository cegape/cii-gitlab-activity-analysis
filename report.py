"""
Rapport personnel d'activité : quotidien, mensuel et annuel.

Usage:
  python3 report.py <username>    — rapport pour un utilisateur
  python3 report.py me            — rapport pour l'utilisateur courant (git config user.name)

Source: gitlab_classified.xlsx (produit par classify.py)
"""
import os
import sys
import subprocess
import pandas as pd
from constants import CII_CODES, NON_CII_CODES, IMMO_CODES, CHARGES_CODES, PROJECT_CODES, MONTHS


SOURCE_FILE = "gitlab_classified.xlsx"


def get_git_username():
    """Récupère le username GitLab depuis git config."""
    # Essayer d'abord gitlab.user (si configuré)
    result = subprocess.run(["git", "config", "gitlab.user"], capture_output=True, text=True)
    if result.stdout.strip():
        return result.stdout.strip()
    # Sinon le user.name
    result = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return result.stdout.strip()


def find_user(events, query):
    """Trouve le person_key correspondant à la requête. Retourne None si non trouvé."""
    if query == "me":
        git_name = get_git_username().lower()
        match = events[events["display_name"].str.lower() == git_name]
        if match.empty:
            match = events[events["person_key"].str.lower() == git_name]
        if match.empty:
            match = events[events["person_key"].str.contains(git_name, case=False, na=False)]
        if match.empty:
            match = events[events["display_name"].str.contains(git_name, case=False, na=False)]
        if match.empty:
            return None
        return match.iloc[0]["person_key"]

    exact = events[events["person_key"] == query.lower()]
    if not exact.empty:
        return exact.iloc[0]["person_key"]

    partial = events[events["person_key"].str.contains(query.lower(), na=False)]
    if not partial.empty:
        return partial.iloc[0]["person_key"]

    return None


def extract_and_classify_user(username):
    """Extrait les données d'un utilisateur depuis GitLab et les classifie."""
    print(f"⏳ Extraction des données GitLab pour '{username}'...")
    result = subprocess.run(
        ["python3", "add-user-extract.py", username],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print(f"❌ Échec de l'extraction pour '{username}'")
        sys.exit(1)

    print("⏳ Classification...")
    subprocess.run(["python3", "classify.py"], capture_output=True)
    print("✅ Classification terminée")


def build_daily(user_events):
    """Vue quotidienne : 1 ligne par jour."""
    user_events = user_events.copy()
    user_events["date"] = pd.to_datetime(user_events["event_date"]).dt.date

    daily_rows = []
    for date, g in user_events.groupby("date"):
        nb_events = len(g)
        nb_mr = (g["event_type"] == "mr").sum()
        nb_commits = (g["event_type"] == "commit").sum()
        nb_cii = g["is_cii"].sum()
        nb_immo = g["is_immo"].sum() if "is_immo" in g.columns else 0

        cii_codes = g[g["is_cii"] == True]["cii_code"].value_counts().to_dict()
        cii_detail = ", ".join(f"{k}({v})" for k, v in cii_codes.items()) if cii_codes else ""

        daily_rows.append({
            "Date": date,
            "Événements": nb_events,
            "MR": nb_mr,
            "Commits": nb_commits,
            "CII": nb_cii,
            "Détail CII": cii_detail,
            "Immobilisable": nb_immo,
            "Hors CII": nb_events - nb_cii,
        })

    return pd.DataFrame(daily_rows).sort_values("Date")


def build_monthly(user_events):
    """Vue mensuelle : 1 ligne par mois."""
    user_events = user_events.copy()
    month_map = dict(MONTHS)

    monthly_rows = []
    for month_num, g in user_events.groupby("month_num"):
        nb_events = len(g)
        nb_days = g["date"].nunique()
        nb_cii = g["is_cii"].sum()
        nb_immo = g["is_immo"].sum() if "is_immo" in g.columns else 0

        cii_codes = g[g["is_cii"] == True]["cii_code"].value_counts().to_dict()
        cii_detail = ", ".join(f"{k}({v})" for k, v in cii_codes.items()) if cii_codes else ""

        monthly_rows.append({
            "Mois": month_map.get(month_num, str(month_num)),
            "Jours actifs": nb_days,
            "Événements": nb_events,
            "MR": (g["event_type"] == "mr").sum(),
            "Commits": (g["event_type"] == "commit").sum(),
            "CII": nb_cii,
            "% CII": round(nb_cii / nb_events * 100, 1) if nb_events else 0,
            "Détail CII": cii_detail,
            "Immobilisable": nb_immo,
            "% Immo": round(nb_immo / nb_events * 100, 1) if nb_events else 0,
        })

    return pd.DataFrame(monthly_rows)


def build_annual(user_events, display_name):
    """Vue annuelle : résumé."""
    nb_events = len(user_events)
    nb_days = user_events["date"].nunique()
    nb_months = user_events["month_num"].nunique()
    nb_cii = user_events["is_cii"].sum()
    nb_immo = user_events["is_immo"].sum() if "is_immo" in user_events.columns else 0

    rows = [
        {"Indicateur": "Développeur", "Valeur": display_name},
        {"Indicateur": "Événements totaux", "Valeur": nb_events},
        {"Indicateur": "MR", "Valeur": (user_events["event_type"] == "mr").sum()},
        {"Indicateur": "Commits", "Valeur": (user_events["event_type"] == "commit").sum()},
        {"Indicateur": "Jours actifs", "Valeur": nb_days},
        {"Indicateur": "Mois actifs", "Valeur": nb_months},
        {"Indicateur": "Jours théoriques", "Valeur": round(218 * nb_months / 12, 1)},
        {"Indicateur": "", "Valeur": ""},
        {"Indicateur": "Événements CII", "Valeur": nb_cii},
        {"Indicateur": "% CII", "Valeur": f"{round(nb_cii / nb_events * 100, 1)}%"},
        {"Indicateur": "Événements immobilisables", "Valeur": nb_immo},
        {"Indicateur": "% Immobilisable", "Valeur": f"{round(nb_immo / nb_events * 100, 1)}%"},
    ]

    # Détail par code CII
    for code in CII_CODES:
        n = (user_events["cii_code"] == code).sum()
        if n > 0:
            rows.append({"Indicateur": f"  {code}", "Valeur": n})

    rows.append({"Indicateur": "", "Valeur": ""})

    # Détail par projet
    for proj in PROJECT_CODES:
        n = (user_events["project"] == proj).sum()
        if n > 0:
            rows.append({"Indicateur": f"  Projet: {proj}", "Valeur": n})

    return pd.DataFrame(rows)


def build_detail(user_events):
    """Détail : chaque événement."""
    cols = ["event_date", "event_type", "title", "cii_code", "comptable", "project", "project_name"]
    cols = [c for c in cols if c in user_events.columns]
    return user_events[cols].sort_values("event_date")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 report.py <username>")
        print("       python3 report.py me")
        sys.exit(1)

    query = sys.argv[1]

    # Résoudre le username pour "me"
    username_to_extract = query
    if query == "me":
        username_to_extract = get_git_username()
        if not username_to_extract:
            print("❌ Impossible de détecter ton username.")
            print("   Configure-le avec : git config gitlab.user <ton-username-gitlab>")
            sys.exit(1)
        print(f"👤 Détecté : {username_to_extract}")

    # Charger les données classifiées
    if not os.path.exists(SOURCE_FILE):
        print(f"⚠️  {SOURCE_FILE} n'existe pas, extraction nécessaire.")
        extract_and_classify_user(username_to_extract)

    events = pd.read_excel(SOURCE_FILE, sheet_name="events")
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce")
    events["date"] = events["event_date"].dt.date

    person_key = find_user(events, query)

    # Si non trouvé, extraire depuis GitLab puis reclassifier
    if person_key is None:
        extract_and_classify_user(username_to_extract)
        events = pd.read_excel(SOURCE_FILE, sheet_name="events")
        events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce")
        events["date"] = events["event_date"].dt.date
        person_key = find_user(events, query)

    if person_key is None:
        print(f"❌ Utilisateur '{query}' introuvable même après extraction.")
        print(f"   Disponibles : {sorted(events['person_key'].unique().tolist())}")
        sys.exit(1)

    user_events = events[events["person_key"] == person_key]
    display_name = user_events["display_name"].iloc[0]

    output_file = f"report_{person_key}.xlsx"

    annual = build_annual(user_events, display_name)
    monthly = build_monthly(user_events)
    daily = build_daily(user_events)
    detail = build_detail(user_events)

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        annual.to_excel(writer, sheet_name="Annuel", index=False)
        monthly.to_excel(writer, sheet_name="Mensuel", index=False)
        daily.to_excel(writer, sheet_name="Quotidien", index=False)
        detail.to_excel(writer, sheet_name="Détail", index=False)

    print(f"✅ {output_file} généré pour {display_name}")
    print()
    nb = len(user_events)
    cii = user_events["is_cii"].sum()
    print(f"   {nb} événements | {user_events['date'].nunique()} jours actifs")
    print(f"   CII: {cii} ({cii * 100 // nb}%) | Immo: {user_events['is_immo'].sum()} ({user_events['is_immo'].sum() * 100 // nb}%)")


if __name__ == "__main__":
    main()
