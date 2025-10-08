#!/bin/env bash

cd ../parseLog || exit
for i in $(seq 0 40); do 
    export FILTER_FEATURES=$i; STATISTICS_ATTEMPTS=5 python3 model.py -f ../logs/datasets/0-stitched-category-*n.json_apionly -s
done