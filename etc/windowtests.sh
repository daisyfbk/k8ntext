#!/bin/bash

cd ../parseLog || exit
for window_len in $(seq 5 5 200); do
    export WINDOW_LENGTH=$window_len
    python3 model.py -f ../logs/datasets/0-stitched-category-1a.json_cplabel_apionly ../logs/datasets/0-stitched-category-2.json -s
done
