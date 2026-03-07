#!/usr/bin/env bash
# Test the pipeline using existing data.json: generate summary + dry-run email (no API collect, no real send).
# Use this to iterate on prompts or test without hitting GitHub/LeanKit/Calendar or sending email.
#
# Prerequisites: data.json in project root (from a previous collect or checked-in sample).
# Usage:
#   ./scripts/test_pipeline.sh           # daily standup from data.json, dry-run email
#   ./scripts/test_pipeline.sh weekly    # weekly catch-up from data.json, dry-run email

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

MODE="${1:-daily}"
OUTPUT_JSON="${STANDUP_DATA_FILE:-data.json}"
OUTPUT_TXT="${STANDUP_SUMMARY_FILE:-summary.txt}"

if [[ ! -f "$OUTPUT_JSON" ]]; then
  echo "Missing $OUTPUT_JSON. Run collect first, e.g.:"
  echo "  $PYTHON scripts/collect_data.py --mode $MODE --output $OUTPUT_JSON --timezone Europe/London"
  exit 1
fi

if [[ "$MODE" == "weekly" ]]; then
  echo "== Generating weekly catch-up from $OUTPUT_JSON (dry-run email)"
  "$PYTHON" scripts/generate_catchup.py --input "$OUTPUT_JSON" --output "$OUTPUT_TXT"
  "$PYTHON" scripts/send_email.py --input "$OUTPUT_TXT" --subject "Weekly Catch-up (test)" --dry-run
else
  echo "== Generating daily standup from $OUTPUT_JSON (dry-run email)"
  "$PYTHON" scripts/generate_standup.py --input "$OUTPUT_JSON" --output "$OUTPUT_TXT"
  "$PYTHON" scripts/send_email.py --input "$OUTPUT_TXT" --subject "Daily Standup (test)" --dry-run
fi

echo ""
echo "Summary written to $OUTPUT_TXT"
