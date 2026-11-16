#!/usr/bin/env bash
# Run τ²-bench airline through Inspect, then rebuild the static viewer.
# Usage: inspect/run.sh <sample ids, comma-separated> <epochs> [extra inspect args]
#   e.g. inspect/run.sh 0,1,3,4,5 1
set -euo pipefail
cd "$(dirname "$0")/.."
IDS="$1"; EPOCHS="$2"; shift 2

# Inspect reads ANTHROPIC_API_KEY. If only EVALS_ANTHROPIC_API_KEY is set, pass it
# under the standard name for this command only (never printed).
KEY="${ANTHROPIC_API_KEY:-${EVALS_ANTHROPIC_API_KEY:-}}"
[ -n "$KEY" ] || { echo "No API key in ANTHROPIC_API_KEY or EVALS_ANTHROPIC_API_KEY" >&2; exit 1; }

ANTHROPIC_API_KEY="$KEY" inspect eval inspect_evals/tau2_airline \
  --model anthropic/claude-haiku-5-5 \
  --model-role user=anthropic/claude-sonnet-5-5 \
  -T shuffle=false \
  --sample-id "$IDS" \
  --epochs "$EPOCHS" \
  --log-dir inspect/logs \
  "$@"

# Rebuild the static viewer with every log so far (overwrite).
inspect view bundle --log-dir inspect/logs --output-dir inspect/logs-www --overwrite
python3 inspect/make_vercel_json.py
