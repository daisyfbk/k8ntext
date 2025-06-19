# Sharpening Kubernetes Audit Logs with Context Awareness

This repository holds the code for K8NTEXT, a project that aims to enhance Kubernetes audit logs by correlating them. The goal is to provide a more comprehensive understanding of the events occurring in a Kubernetes cluster by linking related audit log entries together.

The following informative files are available:

- `README.md`: this file;
- `parseLog`: the source code for K8NTEXT, which includes the logic for parsing and correlating audit logs;
- `scripts`: some scripts to help with the setup and execution of the project.

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

To edit the parameters of the model, you can modify the `parameters.py` file. The features are in `model_features.py`.

Finally, labeled logs can be visualized using the `visualizer.py` script. Run `visualizer.py --help` to see the available options.

## License

This software is licensed under the Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International license. More information is available in the `LICENSE` file.

## Acknowledgements

When citing this project, please use the following citation:

```generic
Franzil, Matteo; Armani, Valentino; Knob, Luis Augusto Dias; Siracusa, Domenico. Sharpening Kubernetes Audit Logs with Context Awareness. 2025.
```

The authors of this project are:

- [Matteo Franzil](https://github.com/mfranzil), Fondazione Bruno Kessler - `matteo.franzil@fbk.eu`
- Valentino Armani, Fondazione Bruno Kessler - `varmani@fbk.eu`
- [Luis Augusto Dias Knob](https://github.com/luisdknob), Fondazione Bruno Kessler - `l.diasknob@fbk.eu`
- Domenico Siracusa, Fondazione Bruno Kessler - `domenico.siracusa@fbk.eu`
