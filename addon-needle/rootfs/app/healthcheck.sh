#!/usr/bin/env bash
set -Eeuo pipefail

curl \
    --fail \
    --silent \
    --show-error \
    --max-time 4 \
    "http://127.0.0.1:7860/model" \
    >/dev/null