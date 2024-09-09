import os

# Supply an .env file if you want to override these values
STATISTICS_ATTEMPTS = int(os.getenv('STATISTICS_ATTEMPTS', 40))  # Number of attempts in stats mode
WINDOW_LENGTH = int(os.getenv('WINDOW_LENGTH', 60))  # Sliding window length
MAX_EPOCHS = int(os.getenv('MAX_EPOCHS', 160))  # Maximum number of epochs
INITIAL_LEARNING_RATE = float(os.getenv('INITIAL_LEARNING_RATE', 0.004))  # Initial learning rate
EARLY_STOPPING_PATIENCE = int(os.getenv('EARLY_STOPPING_PATIENCE', 8))  # Epochs before early stopping kicks in
REDUCE_LR_FACTOR = float(os.getenv('REDUCE_LR_FACTOR', 0.1))  # Factor ReduceLRonPlateau reduces learning rate by
REDUCE_LR_PATIENCE = int(os.getenv('REDUCE_LR_PATIENCE', 4))  # Epochs before ReduceLRonPlateau kicks in
TEST_TRAIN_SPLIT = float(os.getenv('TEST_TRAIN_SPLIT', 0.1))  # Percentage of data to use for testing
TRAIN_VALID_SPLIT = float(os.getenv('TRAIN_VALID_SPLIT', 0.1))  # Percentage of data to use for validation
TUNER_EXECUTIONS_PER_TRIAL = int(os.getenv('TUNER_EXECUTIONS_PER_TRIAL', 5))
# Top % of classes to show in confusion matrix
LABEL_FEATURE = str(os.getenv('LABEL_FEATURE', 'label'))  # Name of the feature that contains the label
OUT_FOLDER = os.getenv('OUT_FOLDER', 'out')
CREATE_OUT_SUBFOLDERS = os.getenv('CREATE_OUT_SUBFOLDERS', 1)
CREATE_OUT_SUBFOLDERS = bool(int(CREATE_OUT_SUBFOLDERS) == 1)
# Whether to create subfolders in out folder (1) or use it directly (0)
KERAS_BACKEND = os.getenv('KERAS_BACKEND', 'tensorflow')

FILTER_FEATURES = os.getenv('FILTER_FEATURES', None)
if FILTER_FEATURES is not None and FILTER_FEATURES != "":
    FILTER_FEATURES = list(map(int, FILTER_FEATURES.split(',')))
 # Selectively remove features (by index on model_features.py) 

# The following variables are used by model_visualize, change them as you change the model

COLLECTED_METRICS = [
    "learning_rate",
    "loss", "val_loss",
    "recall", "val_recall",
    "precision", "val_precision",
    "categorical_accuracy", "val_categorical_accuracy"
]
METRICS_YRANGE_TEMPLATES = {
    "losslike": (-0.0001, 0.1),
    "acclike": (0.96, 1.0001),
    "lr": (-0.0001, 0.0015)
}
METRICS_YRANGES = {
    "learning_rate": lambda _: METRICS_YRANGE_TEMPLATES["lr"],
    "loss": lambda _: METRICS_YRANGE_TEMPLATES["losslike"],
    "val_loss": lambda _: METRICS_YRANGE_TEMPLATES["losslike"],
    "recall": lambda _: METRICS_YRANGE_TEMPLATES["acclike"],
    "val_recall": lambda _: METRICS_YRANGE_TEMPLATES["acclike"],
    "precision": lambda _: METRICS_YRANGE_TEMPLATES["acclike"],
    "val_precision": lambda _: METRICS_YRANGE_TEMPLATES["acclike"],
    "categorical_accuracy": lambda _: METRICS_YRANGE_TEMPLATES["acclike"],
    "val_categorical_accuracy": lambda _: METRICS_YRANGE_TEMPLATES["acclike"]
}
