#!/bin/bash

cd ../parseLog || exit
for window_len in $(seq 5 5 150); do
    export WINDOW_LENGTH=$window_len
    python3 model.py -f ../logs/datasets/0-stitched-category-1n.json_apionly ../logs/datasets/0-stitched-category-2n.json_apionly -s
done
