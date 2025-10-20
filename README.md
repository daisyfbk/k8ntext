# Sharpening Kubernetes Audit Logs with Context Awareness

This repository holds the code for K8NTEXT, a project that aims to enhance Kubernetes audit logs by correlating them. The goal is to provide a more comprehensive understanding of the events occurring in a Kubernetes cluster by linking related audit log entries together.

The following files are available:

- `README.md`: this file;
- `parseLog`: the source code for K8NTEXT, which includes the logic for parsing and correlating audit logs;
- `analysis`: contains a script for comparing the results of the clustering process, including an HTML visualizer;
- `data-collection`: scripts used to collect the dataset from a Kubernetes cluster;
- `plots`: scripts for generating plots and visualizations from the results;
- `tests`: some shell scripts for evaluating K8NTEXT. The data is then fed to the `plots` scripts.
- `scripts`: miscellaneous scripts used for various tasks. Not fundamental to the project.

## Getting started

To get started with K8NTEXT, follow these steps:

1. Clone the repository:

   ```bash
   git clone https://github.com/daisyfbk/k8ntext.git
   ```

2. Navigate to the project directory:

   ```bash
    cd k8ntext
    ```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    # If on macOS, use requirements-macos.txt instead
    ```

## Use cases

### Training a model

The dataset is in the Releases section of this repository, due to its size. Download it and extract it to a folder of your choice (e.g., `audit-log`). The dataset can be also be created using the `data-collection` scripts (see below).

In order to train a model:

1. `cd` into `parseLog`:

   ```bash
   cd parseLog
   ```

2. Use `model.py` to train a model:

   ```bash
   python3 model.py -f $DATASET_FILE
   ```

   where `$DATASET_FILE` is a JSON file containing a labeled dataset. TThe trained model and some statistics will be saved in the `out` directory.

The model can be deeply customized by editing the `parameters.py` file. The features used for training are in `model_features.py`. For example, in `parameters.py`, the key of the label can be changed by modifying the `LABEL_KEY` variable, which is set to `label` by default.

For convenience, our dataset is available in the `audit-log` directory. The train-test-validation split is automatically done by `model.py`.

### Running a pre-trained model

Once a model has been trained, it can be used to make predictions on new data.

1. `cd` into `parseLog`:

   ```bash
   cd parseLog
   ```

2. Use `model.py` to make predictions:

   ```bash
   python3 model.py -m $MODEL_FILE -f $DATASET_FILE
    ```

    where `$MODEL_FILE` is the path to the trained model (e.g., `out/model.keras`) and `$DATASET_FILE` is a JSON file containing the dataset to be used for inference. The predictions will be saved in the `out` directory. The same dataset format used for training is used for inference.

### Clustering the model results

Once predictions have been made, the results can be clustered using the `cluster.py` script.

1. `cd` into `parseLog`:

   ```bash
   cd parseLog
   ```

2. Use `cluster.py` to cluster the results:

   ```bash
   python3 cluster.py -f $DATASET_FILE [-k $LABEL_KEY]
   ```

   where `$DATASET_FILE` is the JSON file containing the dataset with predictions, `-k $LABEL_KEY` is an optional argument to specify the key used for labels (default is `label`, but if you are running it on a labeled dataset, you might want to set it to `predicted_label`).
   The results are output to the `out` directory.

### Gathering and labeling data from a Kubernetes cluster

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


### Testing the labeling process

The `tests` directory contains some shell scripts that can be used to test the labeling process. In particular:

- `feature-zeroing.sh`: tests the features by zeroing them one at a time and checking the impact on the model's performance.
- `kfolds.sh`: performs k-fold cross-validation on the dataset to evaluate the model's performance.
- `train-test-split.sh`: splits the dataset into training and testing sets and evaluates the model's performance as the ratio of the split changes.
- `window-size.sh`: evaluates the model's performance as the size of the window changes.

### Plotting results

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

### Querying functionality

The querying functionality described in the paper has not been ported to the new clustering algorithm yet. It will be added in a future release. For the moment, it can be used by using the files in the `trash` directory, which contains the old implementation of the clusterizer/visualizer. The code is not maintained and might not work with the current version of the project.

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

## License

This software is licensed under the Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International license. More information is available in the `LICENSE` file.

## Acknowledgements

When citing this project, please use the following citation:

```generic
M. Franzil, V. Armani, L. A. D. Knob, and D. Siracusa, ‘Sharpening Kubernetes Audit Logs with Context Awareness’. arXiv, Jun. 19, 2025. doi: 10.48550/arXiv.2506.16328. Available: http://arxiv.org/abs/2506.16328. 
```

The authors of this project are:

- [Matteo Franzil](https://github.com/mfranzil), University of Trento and Fondazione Bruno Kessler - `matteo.franzil@unitn.it`
- Valentino Armani, Fondazione Bruno Kessler - `varmani@fbk.eu`
- [Luis Augusto Dias Knob](https://github.com/luisdknob), Fondazione Bruno Kessler - `l.diasknob@fbk.eu`
- [Domenico Siracusa](https://github.com/custoz), University of Trento and Fondazione Bruno Kessler - `domenico.siracusa@unitn.it`
