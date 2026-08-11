# Fabrizio - Job Pipeline (v1)

Automated remote-job monitor for Fabrizio De Luca Marocchi. Runs on GitHub Actions:
fetches remote operations/VA/coordinator roles, scores them against his profile,
keeps state across runs, drafts cover letters (optional), and emails a daily digest.

**Nothing is applied automatically.** The pipeline surfaces apply-ready roles; Fabrizio
reviews and applies himself.

## What it does
- **Daily (Mon-Fri, 09:00 ART):** fetch -> filter by region eligibility -> score ->
  dedupe against `data/jobs.json` -> draft cover letters for new HIGH matches ->
  email digest -> commit updated state.
- **Weekly (Mon, 10:00 ART):** summary email (totals, new-this-week, top roles).

## Sources (v1)
- **Remotive** public API (one call per search term).
- **RemoteOK** public JSON feed.

LinkedIn is intentionally excluded (blocks scraping / against its terms) - keep it as a
manual check. To add per-company boards later, see "Extending sources" below.

## Setup
1. Create a new GitHub repo and push these files.
2. Actions -> enable workflows if prompted.
3. (Optional) Add repository **Secrets** (Settings -> Secrets and variables -> Actions):
   - `GMAIL_USER` - the Gmail address that sends the digest.
   - `GMAIL_APP_PASSWORD` - a Gmail **App Password** (needs 2FA on that account:
     https://myaccount.google.com/apppasswords). Not the normal password.
   - `DIGEST_TO` - where to send it (defaults to `GMAIL_USER`; comma-separate for several).
   - `ANTHROPIC_API_KEY` - only if you want auto-drafted cover letters. This uses the
     Anthropic API (console.anthropic.com), billed per token, **separate** from a
     Claude.ai subscription. Without it, everything else still runs.
4. Run it once by hand: Actions -> `job-pipeline-daily` -> **Run workflow**.

Without any secrets it still works: the digest is written to `data/digest-latest.md`
and to the Action's run summary.

## Tuning
Everything lives in `config.yml`: target titles, weighted keywords, region allow-list,
score thresholds, tool watchlist, sources, cover-letter model/budget. Edit and commit.

- `thresholds.min_match` - ignore anything below this score.
- `thresholds.high_match` - flag as HIGH and draft a cover letter.
- `region_allow` - only keep jobs whose required location matches these (empty/worldwide
  always pass). US-only roles are dropped.

## State
`data/jobs.json` is the single source of truth (status: new / reopened / stale).
The daily Action commits it back to the repo, so history is versioned.
Cover-letter drafts land in `data/cover-letters/`.

## Extending sources
Ashby / Greenhouse / Lever expose per-company public boards:
- Ashby:      `https://api.ashbyhq.com/posting-api/job-board/{org}`
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{org}/jobs`
- Lever:      `https://api.lever.co/v0/postings/{org}?mode=json`
Add a fetcher in `src/fetch.py` that loops a seed list of orgs and normalizes into the
same job shape, then call it from `fetch_all`. (The current leads - Marco, Scale Army -
are Ashby boards, good candidates for a seed list.)

## Local test
    pip install -r requirements.txt
    python -m src.run --mode daily
