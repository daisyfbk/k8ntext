#!/bin/bash
tmp=$(mktemp -d)
cd "$tmp" || exit

if [[ -z "$1" || -z "$2" ]]; then
  echo "Usage: $0 <api-server-url> <path>"
  exit 1
fi

server=$1
path=$2
shift
shift

kubectl config view --raw -o json | jq -r '.users[0].user."client-certificate-data"' | base64 -d > client.crt
kubectl config view --raw -o json | jq -r '.users[0].user."client-key-data"' | base64 -d > client.key
kubectl config view --raw -o json | jq -r '.clusters[0].cluster."certificate-authority-data"' | base64 -d > ca.crt

curl -H "Content-Type: application/json" --key client.key --cert client.crt --cacert ca.crt -s  "$server/$path" "$@" | jq -c
cd - || exit
rm -rf "$tmp"
