# Sharpening Kubernetes Audit Logs with Context Awareness

This repository holds the code for K8NTEXT, a project that aims to enhance Kubernetes audit logs by correlating them. The goal is to provide a more comprehensive understanding of the events occurring in a Kubernetes cluster by linking related audit log entries together.

The following files are available:

- `README.md`: this file;
- `parseLog`: the source code for K8NTEXT, which includes the logic for parsing and correlating audit logs;
- `analysis`: contains scripts for comparing the results of the prediction process, including an HTML visualizer;
- `data-collection`: scripts used to collect the dataset from a Kubernetes cluster;
- `plots`: scripts for generating plots and visualizations from the results;
- `tests`: some shell scripts for evaluating K8NTEXT. The data is then fed to the `plots` scripts.

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

The dataset is in the `audit-log` directory. In order to use K8NTEXT, `cd` into `parseLog` and use `model.py`:

- by doing `python3 model.py -f (already split dataset)`, you will get the model along with some statistics in the `out` directory,
- by doing `python3 model.py -m (model.keras path) -f (inference dataset)`, you will get the inference results in the `out` directory.

### Model Explainability with Trustee

K8NTEXT now supports model explainability using the [Trustee framework](https://trusteeml.github.io/). Trustee extracts decision tree explanations from black-box ML models, providing interpretable insights into model behavior.

To generate model explanations:

```bash
python3 model.py -f (dataset) --trustee
```

You can also generate explanations for a pre-trained model:

```bash
python3 model.py -m (model.keras path) -f (dataset) --trustee
```

Additional Trustee options:

- `--trustee-iter`: Number of iterations for explanation generation (default: 100)
- `--trustee-stability-iter`: Number of stability iterations (default: 20)  
- `--trustee-sample-size`: Sample size for explanation generation (default: 0.5)

Example with custom parameters:

```bash
python3 model.py -f dataset.json --trustee --trustee-iter 100 --trustee-stability-iter 20 --trustee-sample-size 0.5
```

Example with pre-trained model and custom parameters:

```bash
python3 model.py -m out/model.keras -f dataset.json --trustee --trustee-iter 150 --trustee-stability-iter 25
```

The explanation results will be saved in the output directory as:

- `trustee_decision_tree.txt`: Human-readable decision tree rules with actual feature names
- `trustee_decision_tree.dot`: Graphical decision tree representation (can be converted to PNG/PDF with Graphviz)
- `trustee_explanation.json`: Fidelity metrics, explanation accuracy, and feature information
- `trustee_predictions.json`: Detailed prediction comparisons

**Feature Naming**: Since K8NTEXT uses sequence models, features are flattened for Trustee analysis. Feature names in the decision tree follow the pattern `feature_name_t0`, `feature_name_t1`, etc., where `t0`, `t1` represent different time steps in the sequence window.

To edit the parameters of the model, you can modify the `parameters.py` file. The features are in `model_features.py`.

Finally, labeled logs can be visualized using the `visualizer.py` script. Run `visualizer.py --help` to see the available options.

## License

This software is licensed under the Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International license. More information is available in the `LICENSE` file.

## Acknowledgements

When citing this project, please use the following citation:

```generic
M. Franzil, V. Armani, L. A. D. Knob, and D. Siracusa, ‘Sharpening Kubernetes Audit Logs with Context Awareness’. arXiv, Jun. 19, 2025. doi: 10.48550/arXiv.2506.16328. Available: http://arxiv.org/abs/2506.16328. 
```

The authors of this project are:

- [Matteo Franzil](https://github.com/mfranzil), Fondazione Bruno Kessler - `matteo.franzil@fbk.eu`
- Valentino Armani, Fondazione Bruno Kessler - `varmani@fbk.eu`
- [Luis Augusto Dias Knob](https://github.com/luisdknob), Fondazione Bruno Kessler - `l.diasknob@fbk.eu`
- Domenico Siracusa, Fondazione Bruno Kessler - `domenico.siracusa@fbk.eu`
