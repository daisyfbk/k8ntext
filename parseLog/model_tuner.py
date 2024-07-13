from functools import partial

import keras
import keras_tuner as kt
from keras.api import layers, models

import parameters as pm


def build_model(hp, len_classes, len_features):
    pm_WINDOW_LENGTH = hp.Int('WINDOW_LENGTH', min_value=5, max_value=120, step=5)

    model = models.Sequential([
        layers.Input(shape=(pm_WINDOW_LENGTH, len_features)),
        layers.LSTM(hp.Int('lstm_units_8x', min_value=len_features, max_value=len_features * 12, step=len_features), return_sequences=True, name='lstm_8x'),
        layers.LSTM(hp.Int('lstm_units_4x', min_value=len_features, max_value=len_features * 12, step=len_features), return_sequences=True, name='lstm_4x'),
        layers.LSTM(hp.Int('lstm_units_2x', min_value=len_features, max_value=len_features * 12, step=len_features), return_sequences=True, name='lstm_2x'),
        layers.Dropout(hp.Float('dropout', min_value=0.1, max_value=0.5, step=0.1), name='dropout'),
        layers.TimeDistributed(layers.Dense(len_classes * pm_WINDOW_LENGTH, activation='softmax', name='dense'), name='time_distributed'),
        layers.Reshape((pm_WINDOW_LENGTH, len_classes, pm_WINDOW_LENGTH), name='reshape'),
        layers.Activation('softmax', name='softmax')
    ])

    model.compile(
        optimizer=keras.optimizers.Adam(hp.Choice('learning_rate', values=[0.05, 0.001, 0.005, 0.0001])),
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

    len_classes = training_data['len_classes']
    len_features = training_data['len_features']
    model_builder = partial(build_model, len_classes=len_classes, len_features=len_features)

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

    tuner.search(
        x_train,
        y_train,
        epochs=pm.MAX_EPOCHS,
        validation_data=(x_val, y_val)
    )

    tuner.results_summary()

    best_models = tuner.get_best_models(num_models=3)
    for model in best_models:
        model.summary()
