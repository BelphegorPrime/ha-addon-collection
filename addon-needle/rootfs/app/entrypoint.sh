#!/usr/bin/env bash
set -Eeuo pipefail

PORT="7860"
SELECTION="/tmp/needle-selected-weights"

# Explicit weights have priority. Without them, look for a manually
# benchmarked confidence-capable trained model under /share/needle-training.
# LoRA adapters and uncalibrated .cact exports are never auto-selected.
python3 /app/model_select.py

args=(
    playground
    --host "0.0.0.0"
    --port "${PORT}"
)

if [[ -s "${SELECTION}" ]]; then
    weights="$(cat "${SELECTION}")"
    args+=(--weights "${weights}")
    echo "Starting Needle with selected model: ${weights}"
else
    echo "Starting Needle with the bundled base model."
fi

echo "The Needle playground will listen on port ${PORT}."
exec needle "${args[@]}"
