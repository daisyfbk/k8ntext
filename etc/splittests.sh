#!/bin/bash

cd ../parseLog
for train_test_split in $(seq 0.1 0.1 0.9); do
    for train_val_split in $(seq 0.1 0.1 0.9); do
        export TEST_TRAIN_SPLIT=$train_test_split
        export TRAIN_VALID_SPLIT=$train_val_split
        python3 model.py -f ../logs/datasets/0-stitched-category-1a.json_cplabel_apionly ../logs/datasets/0-stitched-category-2.json
    done
done
