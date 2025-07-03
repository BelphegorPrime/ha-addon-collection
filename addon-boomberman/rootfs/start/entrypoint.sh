#! /bin/bash

echo "Starting Boomberman Add-on..."
echo "Creating configurations from provided user configuration..."

SHARE_DATA_PATH=/share/boomberman/data

mkdir -p $SHARE_DATA_PATH

CONFIG_PATH=/data/options.json

cp $CONFIG_PATH $SHARE_DATA_PATH/options.json
cat $CONFIG_PATH

# Read configuration into variables
ai_enabled=$(jq --raw-output '["AI Enabled"]' $CONFIG_PATH)
ollama_url=$(jq --raw-output '["Ollama URL"]' $CONFIG_PATH)
ollama_model=$(jq --raw-output '["Ollama model"]' $CONFIG_PATH)

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

echo "${json_string}"

# render .env file config related files 
echo "${json_string}" | tempio -template /templates/.env_template -out /.env
cp /.env /app/.env

cp /fakeResponses.json $SHARE_DATA_PATH/fakeResponses.json

cat /app/.env
. /app/.env

echo "Starting Boomberman"

cd /app && exec node dist/start.js
