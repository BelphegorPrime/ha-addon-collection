#!/usr/bin/env bashio

echo "Starting Authelia Add-on..."
echo "Creating configurations from provided user configuration..."

# Read configuration into variables
email=$(bashio::config '["Admin User Email"]')
domain=$(bashio::config 'Domain')
password=$(bashio::config 'Password')
jwt_secret=$(bashio::config '["JWT Secret"]')
session_secret=$(bashio::config '["Session Secret"]')
storage_encryption_key=$(bashio::config '["Storage Encryption Key"]')

# Generate admin hash
password_hash=$(authelia crypto hash generate argon2 --password "${password}")
password_hash="${password_hash:8}"

# build login data and calculate hashes
logins_json=$(jq -nc '[inputs]' < <(
  jq -c '.["Logins"][]' /data/options.json | while read -r l; do 
    e=$(echo "$l" | jq -r .email)
    tpw=$(echo "$l" | jq -r .password)
    pwh=$(authelia crypto hash generate argon2 --password "${tpw}")
    pwh="${pwh:8}"
    jq -n --arg email "$e" --arg password_hash "$pwh" \
      '{email: $email, password_hash: $password_hash}'
  done
))

# Build final JSON object with structured logins
json_string=$(jq -n \
  --arg email "$email" \
  --arg domain "$domain" \
  --arg password "$password" \
  --arg password_hash "$password_hash" \
  --arg jwt_secret "$jwt_secret" \
  --arg session_secret "$session_secret" \
  --arg storage_encryption_key "$storage_encryption_key" \
  --argjson logins "$logins_json" \
  '{
    email: $email,
    domain: $domain,
    password: $password,
    password_hash: $password_hash,
    jwt_secret: $jwt_secret,
    session_secret: $session_secret,
    storage_encryption_key: $storage_encryption_key,
    logins: $logins
  }')

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
