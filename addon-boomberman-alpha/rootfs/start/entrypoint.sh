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

# Generic configuration processing - automatically converts all Home Assistant options
# to template variables by converting spaces to underscores and making lowercase
json_string=$(jq 'to_entries | map({key: (.key | gsub(" "; "_") | ascii_downcase), value: .value}) | from_entries' $CONFIG_PATH)

# render .env file config related files 
echo "${json_string}" | tempio -template /templates/.env_template -out /.env
cp /.env /app/.env

cp /fakeResponses.jsonl $SHARE_DATA_PATH/fakeResponses.jsonl

. /app/.env

echo "Starting Boomberman"

cd /app && exec node dist/start.js
