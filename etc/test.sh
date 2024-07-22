#!/bin/zsh

idx=0
json=results2.json
jq -n '[]' > "$json"
# model=3.1.2-splitchecks-40tt-0.1-withsave
model=3.1.4-focalbatch-withsave
# model=3.1.2-withsave
cat $model/main.log | egrep 'f1' | while read -r line; do
    f1=$(echo "$line" | sed "s/.*'f1': \([0-9.]*\).*/\1/")
    jq --argjson f1 "$f1" --argjson i "$idx" '. + [{"mode": "focal", "f1": $f1, "i": $i}]' "$json" > tmp.json
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