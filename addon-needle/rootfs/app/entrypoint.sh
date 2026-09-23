#!/usr/bin/env bash
set -Eeuo pipefail

OPTIONS_FILE="/data/options.json"
PORT="7860"

weights="$(
    python3 - "${OPTIONS_FILE}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("")
    raise SystemExit

try:
    options = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"Unable to read {path}: {error}") from error

print(str(options.get("weights", "")).strip())
PY
)"

args=(
    playground
    --host "0.0.0.0"
    --port "${PORT}"
)

if [[ -n "${weights}" ]]; then
    if [[ "${weights}" != /* ]]; then
        echo "ERROR: The weights option must be an absolute path, for example /share/model.cact." >&2
        exit 1
    fi

    if [[ ! -f "${weights}" ]]; then
        echo "ERROR: The configured weights file does not exist: ${weights}" >&2
        exit 1
    fi

    args+=(--weights "${weights}")
    echo "Starting Needle with custom weights: ${weights}"
else
    echo "Starting Needle with the bundled base model."
fi

echo "The Needle playground will listen on port ${PORT}."
exec needle "${args[@]}"