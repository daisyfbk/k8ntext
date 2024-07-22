#!/bin/zsh

i=0
json=results.json
jq -n '[]' > "$json"
# model=3.1.2-splitchecks-40tt-0.1-withsave
model=3.1.3-splitchecks-40tt-0.1-oldmodel-withsave/
cat $model/main.log | egrep 'f1' | while read -r line; do
    precision=$(echo "$line" | sed "s/.*'precision': \([0-9.]*\),.*/\1/")
    i=$((i+1))
    jq --argjson precision "$precision" --argjson i "$i" '. + [{"mode": "number", "precision": $precision, "i": $i}]' "$json" > tmp.json
    mv tmp.json "$json"
done


for i in $model-validation/*; do
    [[ ! -d "$i" ]] && continue
    attempt=$(cat "$i/main.log" | egrep 'model: ../logs/models.*/attempt_([0-9]+)/model_([0-9]+).keras' | sed "s/.*attempt_\([0-9]\+\)\/model_\([0-9]\+\).keras/\1/")
    error_statistics=$(cat "$i/inference.json" | jq '.error_statistics')
    # insert into json with the same index as the attempt
    jq --argjson error_statistics "$error_statistics" --argjson attempt "$attempt" '.[$attempt].error_statistics = $error_statistics' "$json" > tmp.json
    mv tmp.json "$json"
done