import os

# Supply an .env file if you want to override these values
STATISTICS_ATTEMPTS = int(os.getenv('STATISTICS_ATTEMPTS', 40))  # Number of attempts in stats mode
WINDOW_LENGTH = int(os.getenv('WINDOW_LENGTH', 40))  # Sliding window length
MAX_EPOCHS = int(os.getenv('MAX_EPOCHS', 300))  # Maximum number of epochs
INITIAL_LEARNING_RATE = float(os.getenv('INITIAL_LEARNING_RATE', 0.001))  # Initial learning rate
EARLY_STOPPING_PATIENCE = int(os.getenv('EARLY_STOPPING_PATIENCE', 40))  # Epochs before early stopping kicks in
REDUCE_LR_FACTOR = float(os.getenv('REDUCE_LR_FACTOR', 0.5))  # Factor ReduceLRonPlateau reduces learning rate by
REDUCE_LR_PATIENCE = int(os.getenv('REDUCE_LR_PATIENCE', 20))  # Epochs before ReduceLRonPlateau kicks in
TEST_TRAIN_SPLIT = float(os.getenv('TEST_TRAIN_SPLIT', 0.1))  # Percentage of data to use for testing
TRAIN_VALID_SPLIT = float(os.getenv('TRAIN_VALID_SPLIT', 0.2))  # Percentage of data to use for validation
CONFUSION_MATRIX_TOP_PERCENTAGE = float(os.getenv('CONFUSION_MATRIX_TOP_PERCENTAGE', 0.2))
# Top % of classes to show in confusion matrix
LABEL_FEATURE = str(os.getenv('LABEL_FEATURE', 'label'))  # Name of the feature that contains the label

# This variable is managed by support/log.py and should not be changed here
OUT_FOLDER = 'out'
