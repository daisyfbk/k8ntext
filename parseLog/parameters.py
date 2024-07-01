import os

# Supply an .env file if you want to override these values
STATISTICS_ATTEMPTS = int(os.getenv('STATISTICS_ATTEMPTS', 40))
WINDOW_LENGTH = int(os.getenv('WINDOW_LENGTH', 40))
MAX_EPOCHS = int(os.getenv('MAX_EPOCHS', 400))
INITIAL_LEARNING_RATE = float(os.getenv('INITIAL_LEARNING_RATE', 0.001))
EARLY_STOPPING_PATIENCE = int(os.getenv('EARLY_STOPPING_PATIENCE', 50))
REDUCE_LR_FACTOR = float(os.getenv('REDUCE_LR_FACTOR', 0.5))
REDUCE_LR_PATIENCE = int(os.getenv('REDUCE_LR_PATIENCE', 40))
TEST_TRAIN_SPLIT = float(os.getenv('TEST_TRAIN_SPLIT', 0.1))
TRAIN_VALID_SPLIT = float(os.getenv('TRAIN_VALID_SPLIT', 0.2))

# This variable is managed by support/log.py and should not be changed here
OUT_FOLDER = 'out'
