# Apollo Scraper

Automated scraper for [Apollo.io](https://app.apollo.io) that logs into multiple accounts,
extracts **search data**, **credit usage / renewal**, and **upload (list) data**, writes the
results to CSV, and (optionally) uploads them to AWS S3.

> **Status:** baseline commit of the recovered codebase. Structure and docs are being
> organized in follow-up commits (see [Roadmap](#roadmap)).

## Primary entry point

| File | Purpose |
|------|---------|
| `apollo_scraper_with_sessions.py` | **Main script.** Session-based multi-account scraper (search + credits + upload). |
| `config.py` | All tunable settings; loads secrets from `.env`. |
| `apollo_tables_scraper_daily.bat` | Convenience launcher (activates the venv and runs the main script). |

Other `apollo_*.py` files are earlier/variant scrapers kept for reference — they will be
sorted into an `archive/` folder during reorganization.

## Prerequisites

- Windows + Python 3.13
- Google Chrome installed
- An `ApolloUsers.csv` with account credentials (see below) — **not** committed

## Setup

```powershell
# 1. Create the virtual environment (named `crawler`, as the launcher expects)
py -3.13 -m venv crawler
crawler\Scripts\python.exe -m pip install -r requirements.txt

# 2. Create your local secrets file
copy .env.example .env
#    then edit .env and fill in the real AWS (and later MySQL) values
```

## Running

```powershell
crawler\Scripts\python.exe apollo_scraper_with_sessions.py
# or just double-click apollo_tables_scraper_daily.bat
```

The script auto-detects its own folder as the base path, so it runs from anywhere.

## Configuration

Edit `config.py` for behaviour (accounts to target, sleep intervals, timeouts, AWS toggle).
**Secrets live only in `.env`** (AWS keys, and later MySQL credentials) — never in code.

## Data & secrets (git-ignored)

These are excluded from version control by `.gitignore`:

| File / pattern | Why excluded |
|----------------|--------------|
| `.env` | AWS / DB credentials |
| `ApolloUsers.csv` | account emails **and passwords** |
| `cookies.json` | live Apollo session cookies |
| `*.csv` | scraped data (destined for the database) |
| `*.log`, `crawler/`, `__pycache__/` | logs, virtualenv, build caches |

## Roadmap

- **Phase 1 — Organization:** archive unused variants, add structure & docs, safe optimizations.
- **Phase 2 — Database:** replace the CSV/S3 hand-off with a direct MySQL integration
  (tables mirroring the downstream dashboard schema).
