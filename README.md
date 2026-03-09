# SitDown

Automated standup and weekly catch-up summaries using:
- GitHub commit activity
- LeanKit cards
- Google Calendar events
- OpenAI for summary generation
- Resend email delivery

If an `Annual Leave` event is present on your Google Calendar, the workflow skips sending any message.

## Workflows

- `daily-standup.yml`: Mon-Fri at 8:00 UTC
- `weekly-catchup.yml`: Tuesday at 9:00 UTC

Both workflows also support manual run via `workflow_dispatch`.

## Required Secrets

Configure these repository secrets in GitHub:

- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `STANDUP_EMAIL` (recipient email address)
- `LEANKIT_BEARER_TOKEN` if your using leankit api 
- `GOOGLE_CALENDAR_CREDENTIALS` (base64-encoded service-account JSON)
- `GOOGLE_CALENDAR_ID` (for example `jesse.doka-nwogu@singletrack.com`)

Notes:
- `GITHUB_TOKEN` is provided by GitHub Actions automatically.

## Optional Variables

Repository variables:

- `STANDUP_TIMEZONE` (default: `Europe/London`)
- `OPENAI_MODEL` (default in scripts: `gpt-4o-mini`)
- `RESEND_FROM` (optional sender; for example `Breaking Standup <onboarding@resend.dev>`)
- `STANDUP_EMAIL_SUBJECT` (optional default subject when `--subject` is not provided)

## Local Development

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables locally:

```bash
export GITHUB_TOKEN="..."
export LEANKIT_BEARER_TOKEN="..."
export GOOGLE_CALENDAR_CREDENTIALS="..."   # base64 JSON
export GOOGLE_CALENDAR_ID=""
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o-mini"          # optional
export RESEND_API_KEY="..."
export STANDUP_EMAIL="you@example.com"
export RESEND_FROM="Breaking Standup <onboarding@email.com>"  # optional
export GITHUB_ORG=""
export GITHUB_AUTHOR=""
```

### One-command scripts (recommended)

From repo root, with `.env-local` (or env vars) set:

```bash
# Daily: collect → generate → send
./scripts/run_daily.sh

# Daily but only print what would be emailed (no send)
./scripts/run_daily.sh --dry-run

# Weekly
./scripts/run_weekly.sh
./scripts/run_weekly.sh --dry-run
```

Use `--no-collect` to reuse existing `data.json` (e.g. `./scripts/run_daily.sh --no-collect --dry-run`).

### Test without sending (use existing data.json)

No API collect, no real email—good for testing prompts or generation:

```bash
./scripts/test_pipeline.sh        # daily from data.json, dry-run email
./scripts/test_pipeline.sh weekly # weekly from data.json, dry-run email
```

### Manual step-by-step

Run daily flow:

```bash
python scripts/collect_data.py --mode daily --output data.json --timezone Europe/London
python scripts/generate_standup.py --input data.json --output summary.txt
python scripts/send_email.py --input summary.txt --subject "Daily Standup"
```

Run weekly flow:

```bash
python scripts/collect_data.py --mode weekly --output data.json --timezone Europe/London
python scripts/generate_catchup.py --input data.json --output summary.txt
python scripts/send_email.py --input summary.txt --subject "Weekly Catch-up"
```

## Data Shape (high level)

`collect_data.py` writes `data.json` with:

- `mode`
- `generated_at`
- `timezone`
- `windows` (time ranges used)
- `annual_leave` (boolean)
- `github` (repos scanned, commits, changed files)
- `leankit` (assigned cards, filtered subsets)
- `calendar` (events in relevant window)
