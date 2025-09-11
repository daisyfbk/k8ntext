#!/bin/zsh

BASE=/Users/matte/Library/CloudStorage/OneDrive-FondazioneBrunoKessler/projects/2023-k8ntext/results/current/

python3 visualizer.py -f $BASE/inference-on-same-dataset/labeled.json --output-full-log-with-uuid -k predicted_label --cluster-timeout 60 --cluster-max-lines 200
mv with_uuids.json $BASE/uuid-checks/labeled.json
python3 visualizer.py -f $BASE/inference-on-same-dataset/labeled.json --output-full-log-with-uuid -k label --cluster-timeout 60 --cluster-max-lines 200
mv with_uuids.json $BASE/uuid-checks/original.json
python3 compare_clusters.py $BASE/uuid-checks/original.json $BASE/uuid-checks/labeled.json
mv cluster_comparison.png $BASE/uuid-checks/cluster_comparison.png
open $BASE/uuid-checks/cluster_comparison.png