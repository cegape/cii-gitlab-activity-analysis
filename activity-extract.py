import requests
import pandas as pd

# =========================
# CONFIGURATION
# =========================

GITLAB_URL = "https://gitlab.com/api/v4"   # adapte si GitLab interne
PRIVATE_TOKEN = "YOUR TOKEN"


USERNAMES = [
"user1",
"user2"
]

YEAR = 2025
START_DATE = f"{YEAR}-01-01T00:00:00Z"
END_DATE = f"{YEAR}-12-31T23:59:59Z"

HEADERS = {
    "PRIVATE-TOKEN": PRIVATE_TOKEN
}


# =========================
# PAGINATION
# =========================

def get_paginated(url, params=None):
    results = []
    page = 1

    while True:
        query = params.copy() if params else {}
        query["per_page"] = 100
        query["page"] = page

        response = requests.get(url, headers=HEADERS, params=query)

        if response.status_code != 200:
            print(f"Erreur API {response.status_code} sur {url}")
            break

        data = response.json()

        if not data:
            break

        results.extend(data)
        page += 1

    return results


# =========================
# USER → ID
# =========================

def get_user_id(username):
    url = f"{GITLAB_URL}/users"
    params = {"username": username}

    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()

    if data:
        return data[0]["id"]
    else:
        print(f"❌ User non trouvé: {username}")
        return None


# =========================
# MERGE REQUESTS
# =========================

def get_user_merge_requests(user_id):
    url = f"{GITLAB_URL}/merge_requests"
    params = {
        "author_id": user_id,
        "scope": "all",
        "created_after": START_DATE,
        "created_before": END_DATE,
    }
    return get_paginated(url, params)


# =========================
# COMMITS
# =========================

def get_project_commits(project_id, author_name=None):
    url = f"{GITLAB_URL}/projects/{project_id}/repository/commits"
    params = {
        "since": START_DATE,
        "until": END_DATE,
        "all": True,
    }

    if author_name:
        params["author"] = author_name

    return get_paginated(url, params)


# =========================
# NORMALISATION
# =========================

def normalize_merge_requests(mrs, username):
    rows = []

    for mr in mrs:
        rows.append({
            "username": username,
            "mr_id": mr.get("id"),
            "project_id": mr.get("project_id"),
            "title": mr.get("title"),
            "created_at": mr.get("created_at"),
            "merged_at": mr.get("merged_at"),
            "author_name": (mr.get("author") or {}).get("name"),
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
        df["merged_at"] = pd.to_datetime(df["merged_at"], utc=True)

    return df


def normalize_commits(project_id, commits, username):
    rows = []

    for c in commits:
        rows.append({
            "username": username,
            "project_id": project_id,
            "commit_id": c.get("id"),
            "title": c.get("title"),
            "author_name": c.get("author_name"),
            "committed_date": c.get("committed_date"),
        })

    df = pd.DataFrame(rows)

    if not df.empty:
        df["committed_date"] = pd.to_datetime(df["committed_date"], utc=True)

    return df


# =========================
# FIX TIMEZONE
# =========================

def remove_timezone(df):
    for col in df.select_dtypes(include=["datetimetz"]).columns:
        df[col] = df[col].dt.tz_convert(None)
    return df


# =========================
# MAIN
# =========================

def main():
    all_mr = []
    all_commits = []

    for username in USERNAMES:
        print(f"\n👤 Traitement: {username}")

        user_id = get_user_id(username)
        if not user_id:
            continue

        print(f"  → USER_ID: {user_id}")

        mrs = get_user_merge_requests(user_id)
        mr_df = normalize_merge_requests(mrs, username)

        print(f"  → MR: {len(mr_df)}")

        if mr_df.empty:
            continue

        project_ids = mr_df["project_id"].dropna().unique().tolist()
        author_name = mr_df["author_name"].dropna().unique()
        author_name = author_name[0] if len(author_name) > 0 else None

        commit_frames = []

        for project_id in project_ids:
            commits = get_project_commits(project_id, author_name)
            df = normalize_commits(project_id, commits, username)

            if not df.empty:
                commit_frames.append(df)

        commit_df = pd.concat(commit_frames, ignore_index=True) if commit_frames else pd.DataFrame()

        all_mr.append(mr_df)
        all_commits.append(commit_df)

    # =========================
    # CONSOLIDATION
    # =========================

    final_mr = pd.concat(all_mr, ignore_index=True) if all_mr else pd.DataFrame()
    final_commits = pd.concat(all_commits, ignore_index=True) if all_commits else pd.DataFrame()

    # FIX timezone
    final_mr = remove_timezone(final_mr)
    final_commits = remove_timezone(final_commits)

    # =========================
    # EXPORT
    # =========================

    with pd.ExcelWriter("gitlab_all_users_2025.xlsx", engine="openpyxl") as writer:
        final_mr.to_excel(writer, sheet_name="merge_requests", index=False)
        final_commits.to_excel(writer, sheet_name="commits", index=False)

    print("\n✅ Export terminé : gitlab_all_users_2025.xlsx")


if __name__ == "__main__":
    main()