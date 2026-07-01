# Additional documentation

## Gathering and labeling data from a Kubernetes cluster

The dataset provided with this project has been collected as following.

1. Set up your Kubernetes cluster and ensure you have access to it via `kubectl`.
2. Make sure auditing has been enabled in your cluster. You can follow the [official Kubernetes documentation](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/) to enable auditing. In our case, a permissive audit policy has been used, in the `audit-policy.yaml` file.
3. `cd` to the `data-collection` directory:

   ```bash
   cd data-collection
   ```

4. Run the `move-logs.sh` script to start collecting audit logs. The script will guide you through the process, allowing you to cut pieces of the audit log file as needed. The collected logs will be stored in the `$DATASET_FOLDER` directory.
5. Once you have collected the logs, cd to the `parseLog` directory:

   ```bash
   cd ../parseLog
   ```

6. Use the `labeler.py` script to label the collected logs. The script will process the logs, automatically label control plane events, and prompt you to label user events.

## Testing the labeling process

The `tests` directory contains some shell scripts that can be used to test the labeling process. In particular:

- `feature-zeroing.sh`: tests the features by zeroing them one at a time and checking the impact on the model's performance.
- `kfolds.sh`: performs k-fold cross-validation on the dataset to evaluate the model's performance.
- `train-test-split.sh`: splits the dataset into training and testing sets and evaluates the model's performance as the ratio of the split changes.
- `window-size.sh`: evaluates the model's performance as the size of the window changes.

## Plotting results

Once you have the results of your model and have executed the tests described in the previous section, you can use the scripts in the `plots` directory to generate visualizations. In particular:

- `plot-feature-zeroing.py`: generates a bar plot showing the impact of zeroing each feature on the model's performance.
- `plot-kfolds.py`: shows the results of the k-fold cross-validation as a multiple heatmap.
- `plot-train-test-split.py`: generates a heatmap showing the model's performance as the train-test split ratio changes.

Window tests do not have a dedicated plot script, as the results are shown in table format in the paper.

Some other scripts do not rely on the tests, but can be used to visualize the results of the model:

- `plot-average-cluster-sizes.py`: generates a bar plot showing the average size of each cluster once the results have been clustered.
- `plot-class-accuracy-weighted.py`: generates a scatterplot showing the accuracy of each class weighted by its frequency in the dataset.
- `plot-

 All the plots presented in the paper can be generated using these scripts.

### Explainability with Trustee

K8NTEXT now supports model explainability using the [Trustee framework](https://trusteeml.github.io/). Trustee extracts decision tree explanations from black-box ML models, providing interpretable insights into model behavior.

To generate model explanations:

1. `cd` into `parseLog`:

   ```bash
   cd parseLog
   ```

2. Use `model.py` with the `--trustee` flag to train a model and generate explanations:

    ```bash
    python3 model.py -f $DATASET_FILE --trustee
    ```

    You can also generate explanations for a pre-trained model:

    ```bash
    python3 model.py -m $MODEL_FILE  -f $DATASET_FILE --trustee
    ```

The explanation results will be saved in the output directory as:

- `trustee_decision_tree.txt`: Human-readable decision tree rules with actual feature names
- `trustee_decision_tree.dot`: Graphical decision tree representation (can be converted to PNG/PDF with Graphviz)
- `trustee_explanation.json`: Fidelity metrics, explanation accuracy, and feature information
- `trustee_predictions.json`: Detailed prediction comparisons

Features are flattened for Trustee analysis. Feature names in the decision tree follow the pattern `feature_name_t0`, `feature_name_t1`, etc., where `t0`, `t1` represent different time steps in the sequence window.