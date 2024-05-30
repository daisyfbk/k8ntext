#!/usr/bin/env bash
# list_rbac_resources.sh - list all the kubernetes rbac resources/sub-resources
# Requires jq (https://stedolan.github.io/jq/)
# Usage: ./list_rbac_resources.sh <kubernetes api server url>
tmp=$(mktemp -d)
cd "$tmp" || exit

kubectl config view --raw -o json | jq -r '.users[0].user."client-certificate-data"' | base64 -d > client.crt
kubectl config view --raw -o json | jq -r '.users[0].user."client-key-data"' | base64 -d > client.key
kubectl config view --raw -o json | jq -r '.clusters[0].cluster."certificate-authority-data"' | base64 -d > ca.crt

# Generate a UUID for the tmp output file
UUID=$(uuidgen)

# Get the list of APIs
APIS=$(curl --key client.key --cert client.crt --cacert ca.crt -s "$1/apis" | jq -r '[.groups | .[].name] | join(" ")')

# Add header to tmp output file
echo "API Version Resource Verb Namespaced Kind" >> "list_rbac_resources_${UUID}"

# Get the list of resources/sub-resources from the core API
api="v1"
curl --key client.key --cert client.crt --cacert ca.crt -s "$1/api/v1" | jq -r --arg api "$api" '.resources | .[] | "core \($api) \(.name) \(.verbs | join(",")) \(.namespaced) \(.kind)"' >> "list_rbac_resources_${UUID}"

# Get the list of resources/sub-resources from the other APIs
for api in $APIS; do
    version=$(curl --key client.key --cert client.crt --cacert ca.crt -s "$1/apis/$api" | jq -r '.preferredVersion.version')
    curl --key client.key --cert client.crt --cacert ca.crt -s "$1/apis/$api/$version" | jq -r --arg version "$version" --arg api "$api" '.resources | .[]? | "\($api) \($version) \(.name) \(.verbs | join(",")) \(.namespaced) \(.kind)"' >> "list_rbac_resources_${UUID}"
done

# Print the list of resources/sub-resources using the column command
column -t "list_rbac_resources_${UUID}"

cd - || exit
rm -rf "$tmp"
