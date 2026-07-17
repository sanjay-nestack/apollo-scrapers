# Contributing

## Branch model

- **`main`** — protected, always-working. No direct pushes. Updated only via a reviewed
  Pull Request that passes CI.
- **`dev`** — integration branch. Do your work here (or on short-lived `feature/*` branches
  branched off `dev`).

### Workflow

```bash
git checkout dev
git pull
# ...make changes...
git commit -m "..."
git push origin dev          # -> CI runs automatically
```

When `dev` is ready, open a PR **dev → main**. CI runs again; merge it yourself once the
checks are green.

## CI checks (GitHub Actions: .github/workflows/ci.yml)

Runs on every push to `dev` and every PR to `main`:

| Check | Gate | What it does |
|-------|------|--------------|
| Compile all Python | **blocking** | `compileall` — no file may have a syntax error |
| Install dependencies | **blocking** | `pip install -r requirements.txt` must resolve |
| Ruff lint | advisory | reports style/quality issues; does not fail the build (yet) |
| Secret scan (gitleaks) | **blocking** | fails if any credential is found in the tree or history |

> Note: the scraper itself cannot be exercised in CI (it needs a real Chrome browser, a live
> Apollo login, account credentials, and cookies). CI is static checks only. Verify scraping
> behaviour with a **local run** before opening the PR.

## Rules

- **Never commit secrets.** Credentials live only in `.env` (git-ignored). Use `.env.example`
  to document new variables.
- Never commit `ApolloUsers.csv`, `cookies.json`, scraped `*.csv`, logs, or the `crawler/`
  venv — all already git-ignored.
- Keep the active pipeline at the repo root; put unmaintained/experimental code in `archive/`.

## Local setup

See [README.md](README.md#setup).
