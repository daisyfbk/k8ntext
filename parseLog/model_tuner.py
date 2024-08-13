import gc
import logging as log
from functools import partial

import keras
import keras_tuner as kt
from keras.api import layers, models, callbacks, backend

import parameters as pm
from support.log import silence_stdout_logging, activate_stdout_logging


def build_model(hp, X_shape: int, y_shape: int | tuple) -> models.Sequential:
    model = models.Sequential([
        layers.Input(shape=(pm.WINDOW_LENGTH, X_shape)),
        layers.Bidirectional(layers.LSTM(hp.Int('lstm_units_1', min_value=X_shape, max_value=X_shape * 8, step=X_shape),
                                         return_sequences=True, name='lstm_1'), name='bidirectional_1'),
        layers.BatchNormalization(name='batch_norm_1'),
        layers.Bidirectional(layers.LSTM(hp.Int('lstm_units_2', min_value=X_shape, max_value=X_shape * 8, step=X_shape),
                                         return_sequences=True, name='lstm_2'), name='bidirectional_2'),
        layers.Dropout(hp.Float('dropout', min_value=0.1, max_value=0.5, step=0.1), name='dropout_1'),
        layers.TimeDistributed(layers.Dense(y_shape[0] * y_shape[1], name='dense'), name='time_distributed'),
        layers.BatchNormalization(name='batch_norm_2'),
        layers.Reshape((pm.WINDOW_LENGTH, y_shape[0], y_shape[1]), name='reshape'),
        layers.Activation('softmax', name='softmax')
    ])

    model.compile(
        optimizer=keras.optimizers.Adam(hp.Choice('learning_rate', values=[0.001, 0.005, 0.0001])),
        loss='categorical_crossentropy',
        metrics=[
            keras.metrics.Precision(name='precision'),
            keras.metrics.Recall(name='recall'),
            keras.metrics.CategoricalAccuracy(name='categorical_accuracy')
        ]
    )

    return model


def tuner_search(data: list[dict],
                 tuner_type: str = 'hyperband'):
    from model import preprocess_data, encode_data, train_test_split
    flattened_data, total_features = preprocess_data(data)
    training_data = encode_data(flattened_data, total_features)

    x_train, _, y_train, _ = train_test_split(
        training_data['X'],
        training_data['y'],
        test_size=pm.TEST_TRAIN_SPLIT)

    x_train, x_val, y_train, y_val = train_test_split(
        x_train,
        y_train,
        test_size=pm.TRAIN_VALID_SPLIT)

    model_builder = partial(build_model, X_shape=training_data['X_shape'], y_shape=training_data['y_shape'])

    match tuner_type:
        case 'hyperband':
            tuner = kt.Hyperband(
                model_builder,
                objective='val_categorical_accuracy',
                max_epochs=pm.MAX_EPOCHS,
                executions_per_trial=pm.TUNER_EXECUTIONS_PER_TRIAL,
                overwrite=True,
                directory=pm.OUT_FOLDER,
                project_name='lstm_tuning'
            )
        case 'random':
            tuner = kt.RandomSearch(
                model_builder,
                objective='val_categorical_accuracy',
                executions_per_trial=pm.STATISTICS_ATTEMPTS,
                directory=pm.OUT_FOLDER,
                project_name='lstm_tuning',
                overwrite=True
            )
        case _:
            raise ValueError(f"Unknown tuner type: {tuner_type}")

    tuner.search_space_summary()

    cb = [
        callbacks.EarlyStopping(monitor='val_loss',
                                patience=pm.EARLY_STOPPING_PATIENCE,
                                restore_best_weights=True,
                                verbose=1),
        callbacks.ReduceLROnPlateau(monitor='val_loss',
                                    factor=pm.REDUCE_LR_FACTOR,
                                    patience=pm.REDUCE_LR_PATIENCE,
                                    verbose=1),
        callbacks.LambdaCallback(
            on_train_begin=lambda logs: log.info(f"Hyperparameter training started: {logs}"),
            on_train_end=lambda logs: log.info(f"Hyperparameter training ended: {logs}"),
            on_epoch_end=lambda epoch, logs: log.info(f"Epoch {epoch}: {logs}"),
        ),
        ClearMemory(),
        PrintBestModelSoFar(tuner)
    ]

    silence_stdout_logging()
    tuner.search(
        x_train,
        y_train,
        epochs=pm.MAX_EPOCHS,
        validation_data=(x_val, y_val),
        callbacks=cb
    )
    activate_stdout_logging()

    tuner.results_summary()

    best_models = tuner.get_best_models(num_models=4)
    best_trials = tuner.oracle.get_best_trials(num_trials=4)

    for i, model in enumerate(best_models):
        trial = best_trials[i]
        hyperparameters = trial.hyperparameters.values

        log.info(f"Best model {i}: {model}")
        log.info("Hyperparameters:")
        for param, value in hyperparameters.items():
            log.info(f"{param}: {value}")

        model.summary(print_fn=log.info, expand_nested=True, show_trainable=True)


class ClearMemory(callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        backend.clear_session()
        gc.collect()


class PrintBestModelSoFar(callbacks.Callback):
    def __init__(self, tuner):
        super().__init__()
        self.tuner = tuner

    def on_trial_end(self, trial, logs=None):
        best_trial = self.tuner.oracle.get_best_trials(num_trials=1)[0]
        print(f"Best trial so far: {best_trial.trial_id}")
        best_model = self.tuner.get_best_models(num_models=1)[0]
        best_model.summary()
