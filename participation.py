"""
Évalue la participation de chaque développeur avec un indice de participation
et un classement, ventilé par axe CII et immobilisation.

Usage: python3 participation.py
Source: gitlab_classified.xlsx (produit par classify.py)
"""
import os
import pandas as pd
from dotenv import load_dotenv
from constants import CII_CODES, IMMO_CODES, PROJECT_CODES, MONTHS

load_dotenv()

SOURCE_FILE = "gitlab_classified.xlsx"
OUTPUT_FILE = "participation.xlsx"


def get_ordered_users(events: pd.DataFrame) -> list[str]:
    """Retourne les users dans l'ordre du .env."""
    env_usernames = os.getenv("GITLAB_USERNAMES", "").split(",")
    env_usernames = [u.strip().lower() for u in env_usernames if u.strip()]

    key_to_name = (
        events[["person_key", "display_name"]]
        .drop_duplicates("person_key")
        .set_index("person_key")["display_name"]
        .to_dict()
    )

    ordered = []
    for username in env_usernames:
        display = key_to_name.get(username)
        if display and display not in ordered:
            ordered.append(display)

    for name in sorted(events["display_name"].dropna().unique()):
        if name not in ordered:
            ordered.append(name)

    return ordered


def main():
    events = pd.read_excel(SOURCE_FILE, sheet_name="events")
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce")

    users = get_ordered_users(events)
    reverse_month = {v: k for k, v in MONTHS}

    rows = []
    for user in users:
        g = events[events["display_name"] == user]
        if g.empty:
            continue

        total_events = len(g)
        total_mr = (g["event_type"] == "mr").sum()
        total_commits = (g["event_type"] == "commit").sum()
        total_weight = g["weight"].sum()

        # Jours actifs (dates distinctes)
        active_days = g["date"].nunique()

        # Mois actifs
        month_nums = g["month_num"].dropna().unique()
        active_months = len(month_nums)

        # CII
        cii_events = g[g["is_cii"] == True]
        cii_weight = cii_events["weight"].sum()
        cii_pct = (cii_weight / total_weight * 100) if total_weight > 0 else 0

        # Immobilisation
        immo_events = g[g["is_immo"] == True] if "is_immo" in g.columns else pd.DataFrame()
        immo_weight = immo_events["weight"].sum() if not immo_events.empty else 0
        immo_pct = (immo_weight / total_weight * 100) if total_weight > 0 else 0

        # Ventilation CII par code
        cii_breakdown = {}
        for code in CII_CODES:
            w = g[g["cii_code"] == code]["weight"].sum()
            cii_breakdown[f"CII: {code}"] = round(w, 2)

        # Ventilation par projet
        proj_breakdown = {}
        for proj in PROJECT_CODES:
            w = g[g["project"] == proj]["weight"].sum()
            proj_breakdown[f"Projet: {proj}"] = round(w, 2)

        # Indice de participation = poids total normalisé sur 218 jours
        # (convention CII : 218 jours ouvrés par an, proratisé aux mois actifs)
        jours_theoriques = 218 * active_months / 12
        indice = (total_weight / jours_theoriques * 100) if jours_theoriques > 0 else 0

        row = {
            "Développeur": user,
            "Événements": total_events,
            "MR": total_mr,
            "Commits": total_commits,
            "Jours actifs": active_days,
            "Mois actifs": active_months,
            "Poids total": round(total_weight, 1),
            "Jours théoriques": round(jours_theoriques, 1),
            "Indice participation (%)": round(indice, 1),
            "Poids CII": round(cii_weight, 1),
            "% CII": round(cii_pct, 1),
            "Poids immobilisable": round(immo_weight, 1),
            "% immobilisable": round(immo_pct, 1),
        }
        row.update(cii_breakdown)
        row.update(proj_breakdown)
        rows.append(row)

    df = pd.DataFrame(rows)

    # Classements
    df["Rang (participation)"] = df["Indice participation (%)"].rank(ascending=False, method="min").astype(int)
    df["Rang (CII)"] = df["Poids CII"].rank(ascending=False, method="min").astype(int)
    df["Rang (immo)"] = df["Poids immobilisable"].rank(ascending=False, method="min").astype(int)

    # Trier par indice de participation décroissant
    df = df.sort_values("Rang (participation)")

    # Ligne totale
    total = {col: df[col].sum() if df[col].dtype in ["float64", "int64", "int32"] else "" for col in df.columns}
    total["Développeur"] = "TOTAL"
    total["Rang (participation)"] = ""
    total["Rang (CII)"] = ""
    total["Rang (immo)"] = ""
    total["Indice participation (%)"] = ""
    total["% CII"] = round(df["Poids CII"].sum() / df["Poids total"].sum() * 100, 1) if df["Poids total"].sum() > 0 else 0
    total["% immobilisable"] = round(df["Poids immobilisable"].sum() / df["Poids total"].sum() * 100, 1) if df["Poids total"].sum() > 0 else 0
    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Participation", index=False)

    print(f"✅ {OUTPUT_FILE} généré")
    print()
    print(f"{'Rang':<5} {'Développeur':<25} {'Indice %':<10} {'CII %':<8} {'Immo %':<8} {'Événements':<12}")
    print("-" * 68)
    for _, r in df.iterrows():
        if r["Développeur"] == "TOTAL":
            print("-" * 68)
        rang = r.get("Rang (participation)", "")
        print(f"{rang:<5} {r['Développeur']:<25} {r['Indice participation (%)']:<10} {r['% CII']:<8} {r['% immobilisable']:<8} {r['Événements']:<12}")


if __name__ == "__main__":
    main()
