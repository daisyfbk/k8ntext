#!/bin/zsh

idx=0
json=results.json
jq -n '[]' > "$json"
# 1 = "3.1.8*"

model=$(find . -type d -name $1 | grep -v validation | sort | tail -n 1 | cut -f 2 -d '/')


# cat $model/main.log | egrep 'f1' | while read -r line; do
#    f1=$(echo "$line" | sed "s/.*'f1': \([0-9.]*\).*/\1/")

# cat loss.json | jq '.[1].val_loss'
cat $model/loss.json | jq -c '.[].val_loss[-1]' | while read -r line; do
    loss=$(echo "$line")
    jq --arg mode "$2" --argjson loss "$loss" --argjson i "$idx" '. + [{"mode": $mode, "loss": $loss, "i": $i}]' "$json" > tmp.json
    mv tmp.json "$json"
    idx=$((idx+1))
done

for i in $model-validation/*; do
    [[ ! -d "$i" ]] && continue
    attempt=$(cat "$i/main.log" | egrep 'model: ../logs/models.*/attempt_([0-9]+)/model_([0-9]+).keras' | sed "s/.*attempt_\([0-9]\+\)\/model_\([0-9]\+\).keras/\1/")
    error_statistics=$(cat "$i/inference.json" | jq '.error_statistics.correct')
    # insert into json with the same index as the attempt
    jq --argjson error_statistics "$error_statistics" --argjson attempt "$attempt" '.[$attempt].error_statistics = $error_statistics' "$json" > tmp.json
    mv tmp.json "$json"
done

name=$(echo $1 | sed -E 's/(\*|\/|\-)//g')
mv "$json" "results-$name.json"