#!/usr/bin/env bashio

echo "Starting Authelia Add-on..."
echo "Creating configurations from provided user configuration..."

SHARE_DATA_PATH=/share/authelia/data
CONFIG_PATH=/data/options.json

# Read configuration into variables
password=$(bashio::config 'Password')

mkdir -p $SHARE_DATA_PATH/rsa
authelia crypto pair rsa generate -b 8192 -d $SHARE_DATA_PATH/rsa

jwks_key=$(secret "/ssl/privkey.pem" | mindent 10 "|" | msquote)

# Generate admin hash
password_hash=$(authelia crypto hash generate argon2 --password "${password}")
password_hash="${password_hash:8}"

# build login data and calculate hashes
logins_json=$(jq -nc '[inputs]' < <(
  jq -c '.["Logins"][]' $CONFIG_PATH | while read -r l; do 
    e=$(echo "$l" | jq -r .email)
    tpw=$(echo "$l" | jq -r .password)
    pwh=$(authelia crypto hash generate argon2 --password "${tpw}")
    pwh="${pwh:8}"
    jq -n --arg email "$e" --arg password_hash "$pwh" \
      '{email: $email, password_hash: $password_hash}'
  done
))

# Build final JSON object with flattened logins and generic configuration
config_json=$(jq 'to_entries | map({key: (.key | gsub(" "; "_") | ascii_downcase), value: .value}) | from_entries' $CONFIG_PATH)

json_string=$(jq -n \
  --arg password_hash "$password_hash" \
  --arg jwks_key "$jwks_key" \
  --argjson logins "$logins_json" \
  --argjson config "$config_json" \
  '$config + {password_hash: $password_hash, logins: $logins, jwks_key: $jwks_key}')

echo "${json_string}" | tee $SHARE_DATA_PATH/config.json

# render authelia config related files 
echo "${json_string}" | tempio -template /templates/configuration_template.yml -out /config/configuration.yml
echo "${json_string}" | tempio -template /templates/users_database_template.yml -out /config/users_database.yml

# render nginx snippet config files 
echo "${json_string}" | tempio -template /templates/authelia-location_template.conf -out /snippets/authelia-location.conf
echo "${json_string}" | tempio -template /templates/authelia-authrequest_template.conf -out /snippets/authelia-authrequest.conf

mkdir -p /share/nginx_snippets
cp -R /snippets/* /share/nginx_snippets/

echo "Starting Authelia"
exec authelia "${@}"
