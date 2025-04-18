#!/usr/bin/env bashio

echo "Starting Authelia Add-on..."
echo "Creating configurations from provided user configuration..."

# Declare variables
declare email
declare domain
declare password
declare jwt_secret
declare session_secret
declare storage_encryption_key
declare password_hash

# Read configuration into variables
email=$(bashio::config '["Admin User Email"]')
domain=$(bashio::config 'Domain')
password=$(bashio::config 'Password')
jwt_secret=$(bashio::config '["JWT Secret"]')
session_secret=$(bashio::config '["Session Secret"]')
storage_encryption_key=$(bashio::config '["Storage Encryption Key"]')

password_hash=$(authelia crypto hash generate argon2 --password "${password}")
password_hash="${password_hash:8}"

declare json_string
json_string="{\"email\": \"${email}\", \"domain\": \"${domain}\", \"password\": \"${password}\", \"password_hash\": \"${password_hash}\", \"jwt_secret\": \"${jwt_secret}\", \"session_secret\": \"${session_secret}\", \"storage_encryption_key\": \"${storage_encryption_key}\"}"

echo "${json_string}" | tempio -template /templates/configuration_template.yml -out /config/configuration.yml
echo "${json_string}" | tempio -template /templates/users_database_template.yml -out /config/users_database.yml
echo "${json_string}" | tempio -template /templates/authelia-location_template.conf -out /snippets/authelia-location.conf

cp -R /snippets /share/nginx_snippets

echo "Starting Authelia"
exec authelia "${@}"
