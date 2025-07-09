#! /bin/bash

echo "Starting Boomberman Add-on..."

SHARE_DATA_PATH=/share/boomberman/data

mkdir -p $SHARE_DATA_PATH

if [ ! -f "$SHARE_DATA_PATH/10G.gzip" ]; then
  echo "Creating some gzip files. That can take some minutes"
  dd if=/dev/zero bs=1M count=10240 | gzip > $SHARE_DATA_PATH/10G.gzip
  echo "Finished creating some gzip files"
fi

echo "Creating configurations from provided user configuration..."

cp $SHARE_DATA_PATH/10G.gzip /app/public/10G.gzip

CONFIG_PATH=/data/options.json

# Read configuration into variables
ai_enabled=$(jq --raw-output '.["AI Enabled"]' $CONFIG_PATH)
ollama_url=$(jq --raw-output '.["Ollama URL"]' $CONFIG_PATH)
ollama_model=$(jq --raw-output '.["Ollama model"]' $CONFIG_PATH)

# Build final JSON object with structured logins
json_string=$(jq -n \
  --arg ai_enabled "$ai_enabled" \
  --arg ollama_url "$ollama_url" \
  --arg ollama_model "$ollama_model" \
  '{
    ai_enabled: $ai_enabled,
    ollama_url: $ollama_url,
    ollama_model: $ollama_model,
  }')

# render .env file config related files 
echo "${json_string}" | tempio -template /templates/.env_template -out /.env
cp /.env /app/.env

cp /fakeResponses.jsonl $SHARE_DATA_PATH/fakeResponses.jsonl

. /app/.env

echo "Starting Boomberman"

cd /app && exec node dist/start.js
