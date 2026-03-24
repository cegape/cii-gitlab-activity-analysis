# CII GitLab Activity Analysis

Reconstruction of developer activity from GitLab data for **CII (Crédit Impôt Innovation)** reporting.

## 🧩 Pipeline

GitLab API → activity-extract.py → gitlab_all_users_2025.xlsx → format5.py → Excel outputs

## ⚙️ Step 1 — Extraction

Configure in activity-extract.py:
- GitLab token
- users
- year

Run:
python3 activity-extract.py

Output:
gitlab_all_users_2025.xlsx

## ⚙️ Step 2 — Transformation

Run:
python3 format5.py

Output:
tableaux_CII_mensuels_realistes.xlsx

## 📊 Output

- Annuel
- Légende
- Ressources
- Monthly sheets

## 🧠 Methodology

- Based on real GitLab activity
- Inactive months excluded
- Normalization: 218 × (active months / 12)

## ⚠️ Disclaimer

For CII support only. Must be reviewed with accounting/HR data.
