"""
Script pour ajouter un utilisateur supplémentaire à l'extraction existante,
sans refaire tout l'extract.

Usage: python3 add-user-extract.py <username>
Exemple: python3 add-user-extract.py chauveau.sebastien
"""
import sys
import pandas as pd

# Réutiliser toute la logique de l'extract principal
from importlib.machinery import SourceFileLoader
extract = SourceFileLoader("extract", "activity-extract-enhanced.py").load_module()

OUTPUT_FILE = "gitlab_all_users_2025_enriched.xlsx"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 add-user-extract.py <username>")
        sys.exit(1)

    username = sys.argv[1]
    print(f"\n👤 Ajout de: {username}")

    user_id = extract.get_user_id(username)
    if not user_id:
        sys.exit(1)

    print(f"  → USER_ID: {user_id}")

    mrs = extract.get_user_merge_requests(user_id)
    mr_df = extract.normalize_merge_requests(mrs, username)
    print(f"  → MR: {len(mr_df)}")

    commit_df = pd.DataFrame()
    if not mr_df.empty:
        project_ids = mr_df["project_id"].dropna().unique().tolist()
        author_name = mr_df["author_name"].dropna().unique()
        author_name = author_name[0] if len(author_name) > 0 else None

        commit_frames = []
        for project_id in project_ids:
            commits = extract.get_project_commits(project_id, author_name)
            df = extract.normalize_commits(project_id, commits, username)
            if not df.empty:
                commit_frames.append(df)

        commit_df = pd.concat(commit_frames, ignore_index=True) if commit_frames else pd.DataFrame()

    print(f"  → Commits: {len(commit_df)}")

    # Nettoyer
    if not mr_df.empty:
        mr_df = extract.remove_timezone(mr_df)
        mr_df = extract.clean_illegal_characters(mr_df)
    if not commit_df.empty:
        commit_df = extract.remove_timezone(commit_df)
        commit_df = extract.clean_illegal_characters(commit_df)

    # Lire le fichier existant et merger
    existing_mr = pd.read_excel(OUTPUT_FILE, sheet_name="merge_requests")
    existing_commits = pd.read_excel(OUTPUT_FILE, sheet_name="commits")

    # Supprimer les anciennes données de cet utilisateur (si relance)
    existing_mr = existing_mr[existing_mr["username"] != username]
    existing_commits = existing_commits[existing_commits["username"] != username]

    final_mr = pd.concat([existing_mr, mr_df], ignore_index=True)
    final_commits = pd.concat([existing_commits, commit_df], ignore_index=True)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        final_mr.to_excel(writer, sheet_name="merge_requests", index=False)
        final_commits.to_excel(writer, sheet_name="commits", index=False)

    # Sauvegarder le cache
    extract.save_file_cache(extract.file_cache)

    print(f"\n✅ {username} ajouté à {OUTPUT_FILE}")
    print(f"   → MR total: {len(final_mr)}")
    print(f"   → Commits total: {len(final_commits)}")


if __name__ == "__main__":
    main()
