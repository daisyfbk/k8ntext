#!/bin/bash

find "$1" -name "*labelled" | while read -r file; do
    echo "$file"
    count=$(jq .label "$file" | grep -v "\-1" | uniq -c | sed 's/^\s*//')
    label=$(echo "$count" | cut -f 2 -d " " | while read -r l; do python3 label_proposer.py -d -l "$l"; done)
    echo "$label"
    echo "----------"
done
