#!/usr/bin/env bash
# Run the full weekly catch-up pipeline: collect → generate → send.
# Usage:
#   ./scripts/run_weekly.sh              # collect, generate, send
#   ./scripts/run_weekly.sh --dry-run    # collect, generate, print email (no send)
#   ./scripts/run_weekly.sh --no-collect # use existing data.json, generate, send
#   ./scripts/run_weekly.sh --no-collect --dry-run  # generate from data.json, print email

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# Use venv Python if present
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

if [[ -f .env-local ]]; then
  set -a
  source .env-local
  set +a
fi

TIMEZONE="${STANDUP_TIMEZONE:-Europe/London}"
OUTPUT_JSON="${STANDUP_DATA_FILE:-data.json}"
OUTPUT_TXT="${STANDUP_SUMMARY_FILE:-summary.txt}"
SUBJECT="${STANDUP_EMAIL_SUBJECT:-Weekly Catch-up}"

NO_COLLECT=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --no-collect) NO_COLLECT=true ;;
    --dry-run)    DRY_RUN=true ;;
  esac
done

if ! $NO_COLLECT; then
  echo "== Collecting data (weekly, $TIMEZONE) ..."
  "$PYTHON" scripts/collect_data.py --mode weekly --output "$OUTPUT_JSON" --timezone "$TIMEZONE"
fi

echo "== Generating weekly catch-up summary ..."
"$PYTHON" scripts/generate_catchup.py --input "$OUTPUT_JSON" --output "$OUTPUT_TXT"

if $DRY_RUN; then
  echo "== Dry run: would send email (not sending)"
  "$PYTHON" scripts/send_email.py --input "$OUTPUT_TXT" --subject "$SUBJECT" --dry-run
else
  echo "== Sending email ..."
  "$PYTHON" scripts/send_email.py --input "$OUTPUT_TXT" --subject "$SUBJECT"
fi

echo "Done."
