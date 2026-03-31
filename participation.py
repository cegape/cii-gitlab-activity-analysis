"""
Évalue la participation de chaque développeur : activité brute GitLab.

Usage: python3 participation.py
Source: gitlab_all_users_2025_enriched.xlsx
"""
import os
import pandas as pd
from dotenv import load_dotenv
from constants import MONTHS

load_dotenv()

SOURCE_FILE = "gitlab_all_users_2025_enriched.xlsx"
OUTPUT_FILE = "participation.xlsx"


def main():
    mr = pd.read_excel(SOURCE_FILE, sheet_name="merge_requests")
    commits = pd.read_excel(SOURCE_FILE, sheet_name="commits")

    mr["event_date"] = pd.to_datetime(mr["merged_at"], errors="coerce").fillna(
        pd.to_datetime(mr["created_at"], errors="coerce")
    )
    commits["event_date"] = pd.to_datetime(commits["committed_date"], errors="coerce")

    # Filtrer 2025
    year = int(os.getenv("YEAR", "2025"))
    mr = mr[mr["event_date"].dt.year == year]
    commits = commits[commits["event_date"].dt.year == year]

    usernames = mr["username"].dropna().unique().tolist()
    for u in commits["username"].dropna().unique():
        if u not in usernames:
            usernames.append(u)

    # Mapper author_name → username
    name_map = mr[["username", "author_name"]].dropna().drop_duplicates().set_index("author_name")["username"].to_dict()

    def resolve_name(name):
        return name_map.get(name.strip(), name.strip())

    # Compter les reviews
    all_reviewers = mr["reviewers"].dropna().str.split(",").explode().str.strip()
    all_reviewers = all_reviewers[all_reviewers != ""].map(resolve_name)
    review_counts = all_reviewers.value_counts().to_dict()

    # Compter les commentaires faits sur les MR des autres
    comment_counts = {}
    if "commenters" in mr.columns:
        comment_rows = mr[["username", "commenters"]].dropna(subset=["commenters"])
        all_comments = comment_rows.assign(commenter=comment_rows["commenters"].str.split(",")).explode("commenter")
        all_comments["commenter"] = all_comments["commenter"].str.strip().map(resolve_name)
        all_comments = all_comments[all_comments["commenter"] != all_comments["username"]]
        comment_counts = all_comments["commenter"].value_counts().to_dict()

    rows = []
    for username in sorted(usernames):
        u_mr = mr[mr["username"] == username]
        u_commits = commits[commits["username"] == username]

        nb_mr = len(u_mr)
        nb_commits = len(u_commits)
        nb_events = nb_mr + nb_commits
        nb_reviews = review_counts.get(username, 0)
        nb_comments = comment_counts.get(username, 0)

        # Stats de lignes
        additions = u_commits["additions"].sum() if "additions" in u_commits.columns else 0
        deletions = u_commits["deletions"].sum() if "deletions" in u_commits.columns else 0
        total_changes = u_commits["total_changes"].sum() if "total_changes" in u_commits.columns else 0

        # Projets distincts
        projects_mr = set(u_mr["project_name"].dropna().unique())
        projects_commits = set(u_commits["project_name"].dropna().unique())
        nb_projects = len(projects_mr | projects_commits)

        # Jours et mois actifs
        dates_mr = set(u_mr["event_date"].dt.date.dropna())
        dates_commits = set(u_commits["event_date"].dt.date.dropna())
        all_dates = dates_mr | dates_commits
        jours_actifs = len(all_dates)

        months_mr = set(u_mr["event_date"].dt.month.dropna())
        months_commits = set(u_commits["event_date"].dt.month.dropna())
        mois_actifs = len(months_mr | months_commits)

        # Jours théoriques (218 jours ouvrés proratisés)
        jours_theoriques = round(218 * mois_actifs / 12, 1) if mois_actifs > 0 else 0

        # Indice de participation
        indice = round(jours_actifs / jours_theoriques * 100, 1) if jours_theoriques > 0 else 0

        # Moyennes
        commits_par_jour = round(nb_commits / jours_actifs, 1) if jours_actifs > 0 else 0
        lignes_par_commit = round(total_changes / nb_commits, 0) if nb_commits > 0 else 0

        # Fichiers modifiés distincts
        nb_fichiers = 0
        if "changed_files" in u_commits.columns:
            all_files = set()
            for files in u_commits["changed_files"].dropna():
                all_files.update(f.strip() for f in str(files).split(",") if f.strip())
            for files in u_mr.get("changed_files", pd.Series(dtype=str)).dropna():
                all_files.update(f.strip() for f in str(files).split(",") if f.strip())
            nb_fichiers = len(all_files)

        rows.append({
            "Développeur": username,
            "Événements": nb_events,
            "MR": nb_mr,
            "Reviews": nb_reviews,
            "Commentaires": nb_comments,
            "Commits": nb_commits,
            "Additions": int(additions),
            "Suppressions": int(deletions),
            "Lignes modifiées": int(total_changes),
            "Fichiers touchés": nb_fichiers,
            "Projets": nb_projects,
            "Jours actifs": jours_actifs,
            "Mois actifs": mois_actifs,
            "MR/mois": round(nb_mr / mois_actifs, 1) if mois_actifs > 0 else 0,
            "Commits/jour": commits_par_jour,
            "Lignes/commit": int(lignes_par_commit),
        })

    df = pd.DataFrame(rows)

    # Notes sur 10 avec distribution gaussienne (approximation sans scipy)
    import math

    def inv_norm(p):
        """Approximation de l'inverse de la CDF normale (Abramowitz & Stegun)."""
        if p <= 0:
            return -3.0
        if p >= 1:
            return 3.0
        if p < 0.5:
            return -inv_norm(1 - p)
        t = math.sqrt(-2 * math.log(1 - p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)

    def note_gauss(series):
        """Convertit une série en note sur 10 via distribution gaussienne.
        Médiane = 5, les écarts suivent la courbe de Gauss."""
        if series.max() == 0 or len(series) < 2:
            return pd.Series([0.0] * len(series), index=series.index)
        ranked = series.rank(method="average")
        percentiles = (ranked - 0.5) / len(ranked)
        percentiles = percentiles.clip(0.02, 0.98)
        z_scores = percentiles.apply(inv_norm)
        # z entre ~-2.5 et ~2.5 → ramené sur 0-10
        notes = ((z_scores + 2.5) / 5 * 10).clip(0, 10).round(1)
        return notes

    # Normaliser par mois actif avant de noter
    df["Note MR"] = note_gauss(df["MR"] / df["Mois actifs"])
    df["Note Reviews"] = note_gauss((df["Reviews"] + df["Commentaires"]) / df["Mois actifs"])
    df["Note Commits"] = note_gauss(df["Commits"] / df["Mois actifs"])
    df["Note Lignes"] = note_gauss((df["Additions"] + df["Suppressions"] + df["Lignes modifiées"]) / df["Mois actifs"])
    df["Note Fichiers"] = note_gauss(df["Fichiers touchés"] / df["Mois actifs"])
    df["Note Projets"] = note_gauss(df["Projets"] / df["Mois actifs"])

    df["Score total"] = (df["Note MR"] + df["Note Reviews"] + df["Note Commits"] + df["Note Lignes"] + df["Note Fichiers"] + df["Note Projets"]).round(1)
    df["Rang"] = df["Score total"].rank(ascending=False, method="min").astype(int)

    # Ligne totale
    total = {}
    for col in df.columns:
        if col == "Développeur":
            total[col] = "TOTAL"
        elif col in ("Rang", "MR/mois", "Commits/jour", "Lignes/commit",
                      "Note MR", "Note Reviews", "Note Commits", "Note Lignes",
                      "Note Fichiers", "Note Projets", "Score total"):
            total[col] = ""
        else:
            total[col] = df[col].sum()
    df = pd.concat([df.sort_values("Rang"), pd.DataFrame([total])], ignore_index=True)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Participation", index=False)

    print(f"✅ {OUTPUT_FILE} généré")
    print()
    print(f"{'Rang':<5} {'Développeur':<25} {'MR':<5} {'Rev':<5} {'N.MR':<6} {'N.Rev':<6} {'N.Com':<6} {'N.Lig':<6} {'N.Fic':<6} {'N.Prj':<6} {'Score':<6}")
    print("-" * 86)
    for _, r in df.iterrows():
        rang = r.get("Rang", "")
        print(f"{rang:<5} {r['Développeur']:<25} {r['MR']:<5} {r['Reviews']:<5} {r['Note MR']:<6} {r['Note Reviews']:<6} {r['Note Commits']:<6} {r['Note Lignes']:<6} {r['Note Fichiers']:<6} {r['Note Projets']:<6} {r['Score total']:<6}")


if __name__ == "__main__":
    main()
