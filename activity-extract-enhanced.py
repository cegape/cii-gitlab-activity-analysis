import requests
import pandas as pd
import os
import re
import time
import json
from dotenv import load_dotenv

# =========================
# LOAD ENV
# =========================

load_dotenv()

# =========================
# CONFIGURATION
# =========================

GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com/api/v4")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")

USERNAMES = os.getenv("GITLAB_USERNAMES", "").split(",")
USERNAMES = [u.strip() for u in USERNAMES if u.strip()]

YEAR = int(os.getenv("YEAR", "2025"))
START_DATE = f"{YEAR}-01-01T00:00:00Z"
END_DATE = f"{YEAR}-12-31T23:59:59Z"

HEADERS = {
    "PRIVATE-TOKEN": PRIVATE_TOKEN
}

# =========================
# RATE LIMITER
# =========================

class RateLimiter:
    """Respecte la limite GitLab de 2000 req/min avec marge de sécurité."""

    def __init__(self, max_per_minute=1800):
        self.max_per_minute = max_per_minute
        self.requests = []
        self.total = 0

    def wait_if_needed(self):
        now = time.time()
        # Nettoyer les requêtes de plus d'une minute
        self.requests = [t for t in self.requests if now - t < 60]
        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0]) + 0.5
            print(f"    ⏳ Rate limit approché, pause {wait_time:.0f}s...")
            time.sleep(wait_time)
        self.requests.append(time.time())
        self.total += 1

    def api_get(self, url, params=None):
        self.wait_if_needed()
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError):
            print(f"    ⚠️ Erreur réseau sur {url}, retry après 5s...")
            time.sleep(5)
            try:
                self.wait_if_needed()
                response = requests.get(url, headers=HEADERS, params=params, timeout=30)
            except Exception:
                print(f"    ❌ Échec retry sur {url}, skip")
                return _empty_response()

        # Retry sur 429
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"    ⏳ Rate limited (429), pause {retry_after}s...")
            time.sleep(retry_after)
            self.wait_if_needed()
            response = requests.get(url, headers=HEADERS, params=params, timeout=30)

        return response


class _empty_response:
    """Réponse vide pour les cas d'erreur."""
    status_code = 0
    def json(self):
        return []


rate_limiter = RateLimiter()

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

        response = rate_limiter.api_get(url, params=query)

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

    response = rate_limiter.api_get(url, params=params)

    if response.status_code != 200:
        print(f"❌ Erreur API ({response.status_code}) lors de la récupération de l'utilisateur {username}")
        return None

    data = response.json()

    if isinstance(data, list) and len(data) > 0:
        return data[0].get("id")

    if isinstance(data, dict):
        print(f"❌ Réponse inattendue pour {username}: {data}")

    print(f"❌ User non trouvé: {username}")
    return None

# =========================
# PROJECT INFO CACHE
# =========================

project_cache = {}

def get_project_info(project_id):
    if project_id in project_cache:
        return project_cache[project_id]

    url = f"{GITLAB_URL}/projects/{project_id}"
    response = rate_limiter.api_get(url)

    if response.status_code == 200:
        data = response.json()
        project_cache[project_id] = {
            "project_name": data.get("name"),
            "project_path": data.get("path_with_namespace"),
            "visibility": data.get("visibility"),
        }
    else:
        project_cache[project_id] = {
            "project_name": None,
            "project_path": None,
            "visibility": None,
        }

    return project_cache[project_id]

# =========================
# CACHE FICHIERS MODIFIÉS (reprise sur interruption)
# =========================

CACHE_FILE = ".changed_files_cache.json"

def load_file_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_file_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

file_cache = load_file_cache()
file_cache_dirty = 0

def cache_save_periodic():
    """Sauvegarde le cache tous les 100 nouveaux appels."""
    global file_cache_dirty
    file_cache_dirty += 1
    if file_cache_dirty >= 100:
        save_file_cache(file_cache)
        file_cache_dirty = 0

# =========================
# FILE PATHS
# =========================

def get_mr_changed_files(project_id, mr_iid):
    """Récupère les chemins de fichiers modifiés par une MR."""
    cache_key = f"mr:{project_id}:{mr_iid}"
    if cache_key in file_cache:
        return file_cache[cache_key]

    url = f"{GITLAB_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes"
    response = rate_limiter.api_get(url)

    if response.status_code != 200:
        file_cache[cache_key] = ""
        cache_save_periodic()
        return ""

    data = response.json()
    changes = data.get("changes", [])
    paths = sorted(set(c.get("new_path", c.get("old_path", "")) for c in changes))
    result = ",".join(paths)
    file_cache[cache_key] = result
    cache_save_periodic()
    return result


def get_commit_changed_files(project_id, commit_sha):
    """Récupère les chemins de fichiers modifiés par un commit."""
    cache_key = f"commit:{project_id}:{commit_sha}"
    if cache_key in file_cache:
        return file_cache[cache_key]

    url = f"{GITLAB_URL}/projects/{project_id}/repository/commits/{commit_sha}/diff"
    response = rate_limiter.api_get(url)

    if response.status_code != 200:
        file_cache[cache_key] = ""
        cache_save_periodic()
        return ""

    data = response.json()
    paths = sorted(set(d.get("new_path", d.get("old_path", "")) for d in data))
    result = ",".join(paths)
    file_cache[cache_key] = result
    cache_save_periodic()
    return result

def get_mr_comments(project_id, mr_iid):
    """Récupère les commentaires (notes) d'une MR, retourne une liste de {author, body}."""
    cache_key = f"comments:{project_id}:{mr_iid}"
    if cache_key in file_cache:
        return file_cache[cache_key]

    url = f"{GITLAB_URL}/projects/{project_id}/merge_requests/{mr_iid}/notes"
    notes = get_paginated(url, {"sort": "asc"})

    # Ne garder que les commentaires humains (pas les notes système)
    comments = []
    for n in notes:
        if n.get("system", False):
            continue
        comments.append({
            "author": (n.get("author") or {}).get("name", ""),
            "body": (n.get("body") or "")[:500],
        })

    file_cache[cache_key] = comments
    cache_save_periodic()
    return comments

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
        "with_stats": True,
    }

    if author_name:
        params["author"] = author_name

    return get_paginated(url, params)

# =========================
# NORMALISATION
# =========================

def normalize_merge_requests(mrs, username):
    rows = []

    for i, mr in enumerate(mrs):
        project_id = mr.get("project_id")
        project_info = get_project_info(project_id)
        mr_iid = mr.get("iid")

        # Récupérer les fichiers modifiés
        changed_files = get_mr_changed_files(project_id, mr_iid) if project_id and mr_iid else ""

        # Récupérer les commentaires
        comments = get_mr_comments(project_id, mr_iid) if project_id and mr_iid else []
        nb_comments = len(comments)
        commenters = ",".join(sorted(set(c["author"] for c in comments if c["author"])))

        rows.append({
            "username": username,
            "mr_id": mr.get("id"),
            "project_id": project_id,
            "project_name": project_info["project_name"],
            "project_path": project_info["project_path"],
            "title": mr.get("title"),
            "description": mr.get("description"),
            "state": mr.get("state"),
            "created_at": mr.get("created_at"),
            "merged_at": mr.get("merged_at"),
            "closed_at": mr.get("closed_at"),
            "labels": ",".join(mr.get("labels", [])),
            "author_name": (mr.get("author") or {}).get("name"),
            "assignee": (mr.get("assignee") or {}).get("name") if mr.get("assignee") else None,
            "reviewers": ",".join([r.get("name") for r in mr.get("reviewers", [])]),
            "nb_comments": nb_comments,
            "commenters": commenters,
            "changed_files": changed_files,
            "web_url": mr.get("web_url"),
        })

        if (i + 1) % 50 == 0:
            cached = sum(1 for k in file_cache if k.startswith("mr:") or k.startswith("comments:"))
            print(f"    MR: {i + 1}/{len(mrs)} (cache: {len(file_cache)} entrées)")

    df = pd.DataFrame(rows)

    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
        df["merged_at"] = pd.to_datetime(df["merged_at"], utc=True)
        df["closed_at"] = pd.to_datetime(df["closed_at"], utc=True)

    return df


def normalize_commits(project_id, commits, username):
    rows = []

    project_info = get_project_info(project_id)

    for i, c in enumerate(commits):
        stats = c.get("stats") or {}
        commit_sha = c.get("id")

        # Récupérer les fichiers modifiés
        changed_files = get_commit_changed_files(project_id, commit_sha) if commit_sha else ""

        rows.append({
            "username": username,
            "project_id": project_id,
            "project_name": project_info["project_name"],
            "project_path": project_info["project_path"],
            "commit_id": commit_sha,
            "short_id": c.get("short_id"),
            "title": c.get("title"),
            "message": c.get("message"),
            "author_name": c.get("author_name"),
            "author_email": c.get("author_email"),
            "committed_date": c.get("committed_date"),
            "additions": stats.get("additions"),
            "deletions": stats.get("deletions"),
            "total_changes": stats.get("total"),
            "changed_files": changed_files,
            "web_url": c.get("web_url"),
        })

        if (i + 1) % 200 == 0:
            print(f"    Commit fichiers [{project_info['project_name']}]: {i + 1}/{len(commits)}")

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


ILLEGAL_CHARACTERS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)


def clean_illegal_characters(df):
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(
            lambda x: ILLEGAL_CHARACTERS_RE.sub("", x) if isinstance(x, str) else x
        )
    return df

# =========================
# MAIN
# =========================

def main():
    if not PRIVATE_TOKEN:
        raise ValueError("❌ GITLAB_TOKEN manquant dans le fichier .env")

    if not USERNAMES:
        raise ValueError("❌ GITLAB_USERNAMES manquant ou vide dans le fichier .env")

    all_mr = []
    all_commits = []

    total_users = len(USERNAMES)
    for idx, username in enumerate(USERNAMES, 1):
        print(f"\n[{idx}/{total_users}] 👤 Traitement: {username}")

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
        author_names = mr_df["author_name"].dropna().unique().tolist()

        commit_frames = []

        for project_id in project_ids:
            seen_ids = set()
            for author_name in author_names:
                commits = get_project_commits(project_id, author_name)
                # Dédupliquer les commits déjà vus avec un autre author_name
                new_commits = [c for c in commits if c.get("id") not in seen_ids]
                seen_ids.update(c.get("id") for c in commits)
                df = normalize_commits(project_id, new_commits, username)
                if not df.empty:
                    commit_frames.append(df)

        commit_df = pd.concat(commit_frames, ignore_index=True) if commit_frames else pd.DataFrame()

        all_mr.append(mr_df)
        all_commits.append(commit_df)

    final_mr = pd.concat(all_mr, ignore_index=True) if all_mr else pd.DataFrame()
    final_commits = pd.concat(all_commits, ignore_index=True) if all_commits else pd.DataFrame()

    final_mr = remove_timezone(final_mr)
    final_commits = remove_timezone(final_commits)

    final_mr = clean_illegal_characters(final_mr)
    final_commits = clean_illegal_characters(final_commits)

    with pd.ExcelWriter("gitlab_all_users_2025_enriched.xlsx", engine="openpyxl") as writer:
        final_mr.to_excel(writer, sheet_name="merge_requests", index=False)
        final_commits.to_excel(writer, sheet_name="commits", index=False)

    # Sauvegarder le cache final
    save_file_cache(file_cache)

    cached = len([k for k in file_cache if file_cache[k] != ""])
    print(f"\n✅ Export terminé : gitlab_all_users_2025_enriched.xlsx")
    print(f"   → {rate_limiter.total} appels API effectués")
    print(f"   → {len(file_cache)} entrées en cache ({CACHE_FILE})")


if __name__ == "__main__":
    main()
