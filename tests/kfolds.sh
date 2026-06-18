#!/bin/bash

cd ../parseLog || exit
for split in $(seq 1 1 20); do
    export STATISTICS_ATTEMPTS=$split
    python3 model.py -f ../logs/datasets/0-stitched-category-*n.json_apionly --kfolds
done