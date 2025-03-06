import argparse
import functools
import json
import logging as log
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any
import collections

import joblib
import numpy as np
import sklearn.preprocessing as preprocessing
from keras import callbacks, losses, metrics as keras_metrics, models, layers, regularizers
from keras.api.optimizers import Adam
from keras.api.utils import to_categorical
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split, KFold

import model_features
import parameters as pm
from common import flatten_object, LABEL_UNKNOWN, LABEL_IGNORE
from label_proposer import brute_force_label_space, decode_label
from model_encoder import AuditEncoder, RisingEncoder
from model_tuner import tuner_search
from support.log import initialize_log, activate_stdout_logging, silence_stdout_logging, tqdm


def dump_features_statistics(flattened_data: list[dict[any, dict]]) -> dict:
    # Generate the feature list
    mapped_data: dict[any, set] = {}
    for d in flattened_data:
        for k in d:    
            if k not in mapped_data:
                mapped_data[k] = set()
            mapped_data[k].add(d[k])
    with open(pm.OUT_FOLDER + '/features.json', 'w') as f:
        json.dump({k: list(v) for k, v in mapped_data.items()}, f, indent=4)


    # Group by feature in mapped_data
    stats = {}
    for k in mapped_data.keys():
        try:
            stats[k] = {
                "feature": k,
                "top20": collections.Counter(mapped_data[k]).most_common(10),
                "count": len(mapped_data[k])
            }
        except TypeError:
            stats[k] = {
                "top20": None
            }
    with open(pm.OUT_FOLDER + '/features_stats.json', 'w') as f:
        json.dump(sorted([stats[i] for i in stats], key=lambda x: x["count"])
            , f, indent=2)
        
    return stats 


def preprocess_data(__data: list[dict],
                    features: list[str] | None = None) -> tuple[list[dict], list[str]]:
    # Sort by requestReceivedTimestamp
    __data.sort(key=lambda x: x['requestReceivedTimestamp'])

    # from random import shuffle
    # shuffle(__data)

    if features is None:
        # Use all features provided as default
        total_features = model_features.FEATURES
        if pm.FILTER_FEATURES is not None:
            # FILTER_FEATURES is a list of indexes to remove
            total_features = [f for i, f in enumerate(total_features) if i not in pm.FILTER_FEATURES]
    else:
        # Use the provided feature list
        total_features = features

    # Flatten the features
    flattened_data_init = []
    for d in __data:
        flattened_data_init.append(flatten_object(d))

    # Perform feature preprocessing if necessary
    for d in flattened_data_init:
        for f, p in model_features.FEATURE_PREPROCESSING.items():
            if f in d:
                d[f] = p(d[f])

    flattened_data = []
    for d in flattened_data_init:
        flattened_data.append(flatten_object(d))
    del flattened_data_init

    total_features.sort()

    # Extract features
    extracted_data = []
    for d in flattened_data:
        o = {}
        for f in total_features:
            if f not in d:
                o[f] = None
                continue
            try:
                o[f] = d[f]
            except Exception:
                log.exception(f"Failed to handle {f}")
                o[f] = None

        if pm.LABEL_FEATURE in d:
            o["label"] = d[pm.LABEL_FEATURE]
        if pm.LABEL_CP_FEATURE in d:
            o["cplabel"] = 1 if d[pm.LABEL_CP_FEATURE] else 0
        extracted_data.append(o)

    # Remove excluded features
    res = []
    for d in flattened_data:
        obj = {}
        for f in total_features + [pm.LABEL_FEATURE, pm.LABEL_CP_FEATURE]:
            try:
                obj[f] = d[f]
            except KeyError:
                obj[f] = None
        res.append({k: obj[k] for k in sorted(obj.keys())})

    if pm.LABEL_FEATURE in total_features:
        total_features.remove(pm.LABEL_FEATURE)
    if pm.LABEL_CP_FEATURE in total_features:
        total_features.remove(pm.LABEL_CP_FEATURE)

    return res, total_features


def generate_model_wrapper(X_shape: int, y_shape: int | tuple, version: int = 1) -> models.Model:
    match version:
        case 0:
            model = generate_multiclass_model(X_shape, y_shape)
        case 1:
            model = generate_binary_model(X_shape)
        case _:
            raise ValueError(f"Unknown model version {version}")

    mt = [
        keras_metrics.Precision(name='precision'),
        keras_metrics.Recall(name='recall'),
        keras_metrics.CategoricalAccuracy(name='categorical_accuracy'),
    ]

    model.compile(
        optimizer=Adam(learning_rate=pm.INITIAL_LEARNING_RATE),
        loss=losses.CategoricalFocalCrossentropy(),
        metrics=mt
    )

    return model

def generate_multiclass_model(X_shape: int, y_shape: int | tuple) -> models.Model:
    """
    Version 0 of the model that is used for multi-class classification.
    """
    uncompiled_model = models.Sequential([
        layers.Input(shape=(pm.WINDOW_LENGTH, X_shape)),
        layers.Bidirectional(layers.LSTM(X_shape * 4, return_sequences=True, name='lstm_1'), name='bidirectional_1'),
        layers.BatchNormalization(name='batch_norm_1'),
        layers.Bidirectional(layers.LSTM(X_shape * 3, return_sequences=True, name='lstm_2'), name='bidirectional_2'),
        layers.Dropout(0.4, name='dropout_1'),
        layers.TimeDistributed(layers.Dense(y_shape[0] * y_shape[1], activation='relu', name='dense'),
                               name='time_distributed'),
        layers.BatchNormalization(name='batch_norm_2'),
        layers.Reshape((pm.WINDOW_LENGTH, y_shape[0], y_shape[1]), name='reshape'),
        layers.Activation('softmax', name='softmax')
    ])

    return uncompiled_model


def generate_binary_model(X_shape: int) -> models.Model:
    """
    A version of the model that is used for binary classification.
    Instead of classifying into multiple classes, this model classifies into two classes:
    control-plane and non-control-plane.

    All the other parameters are the same.
    
    This model has version ID 1.
    """
    uncompiled_model = models.Sequential([
        layers.Input(shape=(pm.WINDOW_LENGTH, X_shape)),
        layers.Bidirectional(layers.LSTM(X_shape * 4, return_sequences=True, name='lstm_1'), name='bidirectional_1'),
        layers.BatchNormalization(name='batch_norm_1'),
        layers.Bidirectional(layers.LSTM(X_shape * 3, return_sequences=True, name='lstm_2'), name='bidirectional_2'),
        layers.Dropout(0.4, name='dropout_1'),
        layers.TimeDistributed(layers.Dense(2, activation='relu', name='dense'),
                               name='time_distributed'),
        layers.BatchNormalization(name='batch_norm_2'),
        layers.Reshape((pm.WINDOW_LENGTH, 2), name='reshape'),
        layers.Activation('softmax', name='softmax')
    ])

    return uncompiled_model


def get_model_callbacks(monitor: str = 'val_loss',
                        backup_models: bool = False,
                        verbose_logging: bool = False,
                        ) -> list:
    cb = [
        callbacks.EarlyStopping(monitor=monitor,
                                patience=pm.EARLY_STOPPING_PATIENCE,
                                restore_best_weights=True,
                                verbose=1),
        callbacks.ReduceLROnPlateau(monitor=monitor,
                                    factor=pm.REDUCE_LR_FACTOR,
                                    patience=pm.REDUCE_LR_PATIENCE,
                                    verbose=1),
    ]


    if backup_models:
        log.warning(f"Backup models enabled, saving to {pm.OUT_FOLDER + '/backup'}. Make"
                    f" sure you are not saving multiple models in the same run.")
        cb += [
            callbacks.BackupAndRestore(backup_dir=pm.OUT_FOLDER + '/backup'),
            callbacks.ModelCheckpoint(filepath=pm.OUT_FOLDER + '/model-checkpoint.keras', save_best_only=True)
        ]

    if verbose_logging:
        cb += [
            callbacks.LambdaCallback(
                on_train_begin=lambda logs: log.info(f"Training started: {logs}"),
                on_train_end=lambda logs: log.info(f"Training ended: {logs}"),
                on_epoch_end=lambda epoch, logs: log.info(f"Epoch {epoch}: {logs}"),
            )
        ]

    return cb


def encode_data(flattened_data: list[dict],
                total_features: list[str],
                include_y: bool = True,
                model_version: int = 0,
                previous_xenc: list | None = None
                ) -> dict:
    log.info(f"Encoding a total of {len(flattened_data)} sequences.")
    x_before = []
    if include_y:
        y_before = []

    for d in flattened_data:
        if include_y:
            match model_version:
                case 0:
                    d.pop(pm.LABEL_CP_FEATURE)
                    y_before.append(d.pop(pm.LABEL_FEATURE))
                case 1:
                    d.pop(pm.LABEL_FEATURE)
                    y_before.append(d.pop(pm.LABEL_CP_FEATURE))
                case _:
                    raise ValueError(f"Unknown model version {model_version}")
        else:
            d.pop(pm.LABEL_FEATURE)
            d.pop(pm.LABEL_CP_FEATURE)
        x_before.append(list(d.values()))

    len_features = len(total_features)
    assert len(x_before[0]) == len_features, f"Number of features do not match ({len(x_before[0])} != {len_features})"
    all_labels = brute_force_label_space(print_result=False)
    len_classes = len(all_labels)

    x_before = np.array(x_before)
    xenc = []
    for i in range(x_before.shape[1]):
        if previous_xenc is None:
            le = RisingEncoder()
            le.fit(x_before[:, i])
        else:
            le = previous_xenc[i]
        x_before[:, i] = le.transform(x_before[:, i])
        xenc.append(le)

    # each label is transformed from a number to five one-hot encoded values (len_subclasses = 5)
    log.info(f"Features: {len_features}: {total_features}")

    if include_y:
        match model_version:
            case 0:
                yle = AuditEncoder()
                len_labeltypes = 5
                len_subclasses = yle.length
                y_encoded = yle.fit_transform(y_before)
                y_onehot = to_categorical(y_encoded, num_classes=len_subclasses)

                log.info(f"Classes: {len_classes}, cast to a one-hot encoding of {len_labeltypes} x {len_subclasses}")

                len_local_classes = len(set(y_before))
                log.info(f"Classes in the dataset: {len_local_classes}")
            case 1:
                # Binary classification, pm.LABEL_FEATURE is either true (control-plane) or false (non-control-plane
                yle = preprocessing.LabelEncoder()
                y_encoded = yle.fit_transform(y_before)
                y_onehot = to_categorical(y_encoded, num_classes=2)

                log.info(f"Classes: {len_classes}, cast to a one-hot encoding of 2")

                len_local_classes = len(set(y_before))
                log.info(f"Classes in the dataset: {len_local_classes}")
            case _:
                raise ValueError(f"Unknown model version {model_version}")

    # Create batches
    X = np.zeros((len(x_before) - pm.WINDOW_LENGTH + 1, pm.WINDOW_LENGTH, len_features))
    if include_y:
        match model_version:
            case 0:
                y = np.zeros((len(x_before) - pm.WINDOW_LENGTH + 1, pm.WINDOW_LENGTH, len_labeltypes, len_subclasses))
                y_shape = (len_labeltypes, len_subclasses)
            case 1:
                y = np.zeros((len(x_before) - pm.WINDOW_LENGTH + 1, pm.WINDOW_LENGTH, 2))
                y_shape = 2

    for i in tqdm(range(pm.WINDOW_LENGTH, len(x_before) + 1)):
        X[i - pm.WINDOW_LENGTH] = x_before[i - pm.WINDOW_LENGTH:i]
        if include_y:
            y[i - pm.WINDOW_LENGTH] = y_onehot[i - pm.WINDOW_LENGTH:i]

    if include_y:
        log.info(f"Resulting shapes: {X.shape}, {y.shape}")
        return {
            "X": X,
            "y": y,
            "x_encoders": xenc,
            "y_encoder": yle,
            "X_shape": len_features,
            "y_shape": y_shape,
        }
    else:
        log.info(f"Resulting shapes: {X.shape}")
        return {
            "X": X,
            "x_encoders": xenc,
            "X_shape": len_features
        }


def decode_chunk(chunk, yle):
    return [yle.inverse_transform(sequence_pred) for sequence_pred in chunk]


def decode_labels(y_labels, yle):
    chunks = np.array_split(y_labels, os.cpu_count())
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(functools.partial(decode_chunk, yle=yle), chunks))
    y_decoded = np.concatenate(results)
    return y_decoded


def model_training(data: list[dict],
                   statistical_mode: bool = False) -> dict:
    flattened_data, total_features = preprocess_data(data)

    training_data = encode_data(flattened_data, total_features, model_version=pm.MODEL_VERSION)
    xenc = training_data['x_encoders']
    yle = training_data['y_encoder']
    X_shape = training_data['X_shape']
    y_shape = training_data['y_shape']

    model = generate_model_wrapper(X_shape, y_shape, pm.MODEL_VERSION)

    # x_train, x_test, y_train, y_test, i_train, i_test = train_test_split(X, y, indices, test_size=pm.TEST_TRAIN_SPLIT)
    x_train, x_test, y_train, y_test = train_test_split(
        training_data['X'],
        training_data['y'],
        test_size=pm.TEST_TRAIN_SPLIT)

    cb = get_model_callbacks(monitor='val_loss', backup_models=True, verbose_logging=True)

    silence_stdout_logging()
    model.summary(print_fn=log.info, expand_nested=True, show_trainable=True)
    model.summary(expand_nested=True, show_trainable=True)
    history = model.fit(x_train, y_train, epochs=pm.MAX_EPOCHS, callbacks=cb, validation_split=pm.TRAIN_VALID_SPLIT)
    y_pred = model.predict(x_test)
    activate_stdout_logging()

    match pm.MODEL_VERSION:
        case 0:
            y_pred_sublabels = np.argmax(y_pred, axis=-1)
            y_test_sublabels = np.argmax(y_test, axis=-1)

            print("Decoding labels...")
            y_pred_decoded = decode_labels(y_pred_sublabels, yle)
            y_test_decoded = decode_labels(y_test_sublabels, yle)
        case 1:
            # Binary classification
            y_pred_decoded = np.argmax(y_pred, axis=-1)
            y_test_decoded = np.argmax(y_test, axis=-1)
    

    metrics = calculate_metrics_wrapper(y_test_decoded,
                                y_pred_decoded,
                                include_per_class=True,
                                include_confusion_matrix=True)

    log.info(f"Model metrics (core, adjusted using macro averaging): {metrics['core_metrics']}")

    return {
        "model": model,
        "y_encoders": yle,
        "x_encoders": xenc,
        "features": total_features,
        "metrics": metrics,
        "history": history
    }


def kfold_training(data: list[dict]) -> dict:
    if pm.MODEL_VERSION != 0:
        raise ValueError("K-fold training is only supported for model version 0.")
    
    flattened_data, total_features = preprocess_data(data)

    training_data = encode_data(flattened_data, total_features, model_version=pm.MODEL_VERSION)
    xenc = training_data['x_encoders']
    yle = training_data['y_encoder']
    X_shape = training_data['X_shape']
    y_shape = training_data['y_shape']
    X = training_data['X']
    y = training_data['y']

    kf = KFold(n_splits=pm.STATISTICS_ATTEMPTS, shuffle=False)

    res = {}
    for i, (train_index, test_index) in enumerate(kf.split(X)):
        log.info(f"Starting training fold {i + 1}...")
        log.info(f"Test indices: {test_index[0]} to {test_index[-1]} out of {len(X)}")

        x_train, x_test = X[train_index], X[test_index]
        y_train, y_test = y[train_index], y[test_index]

        model = generate_model_wrapper(X_shape, y_shape, pm.MODEL_VERSION)

        cb = get_model_callbacks(monitor='loss')

        silence_stdout_logging()
        model.summary(print_fn=log.info, expand_nested=True, show_trainable=True)
        model.summary(expand_nested=True, show_trainable=True)

        history = model.fit(x_train, y_train, epochs=pm.MAX_EPOCHS, callbacks=cb, validation_split=0)

        y_pred = model.predict(x_test)
        activate_stdout_logging()

        y_pred_sublabels = np.argmax(y_pred, axis=-1)
        y_test_sublabels = np.argmax(y_test, axis=-1)

        print("Decoding labels...")
        y_pred_decoded = decode_labels(y_pred_sublabels, yle)
        y_test_decoded = decode_labels(y_test_sublabels, yle)

        data_test = [data[i] for i in test_index]

        maj = calculate_majorities(data_test, y_pred_decoded)

        metrics = calculate_class_metrics(y_test_decoded,
                                    y_pred_decoded,
                                    include_per_class=True,
                                    include_confusion_matrix=True)

        res[i] = {
            'index': i,
            "model": model,
            "y_encoders": yle,
            "x_encoders": xenc,
            "features": total_features,
            "metrics": metrics,
            'history': history,
            'maj_result': maj
        }
        
    return res


def calculate_metrics_wrapper(y_true, y_pred,
                              **kwargs) -> dict:
    match pm.MODEL_VERSION:
        case 0:
            return calculate_class_metrics(y_true, y_pred, **kwargs)
        case 1:
            return calculate_binary_metrics(y_true, y_pred, **kwargs)


def calculate_binary_metrics(y_true, y_pred, **kwargs) -> dict:
    if y_true.shape != y_pred.shape:
        raise ValueError("Shapes of y_true and y_pred do not match.")

    accuracy = float(accuracy_score(y_true.flatten(), y_pred.flatten()))
    precision = float(precision_score(y_true.flatten(), y_pred.flatten(), average='macro', zero_division=np.nan))
    recall = float(recall_score(y_true.flatten(), y_pred.flatten(), average='macro', zero_division=np.nan))
    f1 = float(f1_score(y_true.flatten(), y_pred.flatten(), average='macro', zero_division=np.nan))

    return {
        "core_metrics": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1
        }
    }


def calculate_class_metrics(y_true, y_pred,
                      include_majority_accuracy=False,
                      include_per_class=False,
                      include_confusion_matrix=False) -> dict:
    if y_true.shape != y_pred.shape:
        raise ValueError("Shapes of y_true and y_pred do not match.")

    accuracy = float(accuracy_score(y_true.flatten(), y_pred.flatten()))
    precision = float(precision_score(y_true.flatten(), y_pred.flatten(), average='macro', zero_division=np.nan))
    recall = float(recall_score(y_true.flatten(), y_pred.flatten(), average='macro', zero_division=np.nan))
    f1 = float(f1_score(y_true.flatten(), y_pred.flatten(), average='macro', zero_division=np.nan))

    if include_majority_accuracy:
        original_sequence_y_true = {}
        original_sequence_y_pred = {}

        for i in range(len(y_true)):
            for j in range(len(y_true[i])):
                index = i + j
                if index not in original_sequence_y_pred:
                    original_sequence_y_pred[index] = []
                    original_sequence_y_true[index] = []

                original_sequence_y_pred[index].append(y_pred[i][j])
                original_sequence_y_true[index].append(y_true[i][j])

        # Check that in y_true all the values are the same for each key
        for k, v in original_sequence_y_true.items():
            assert len(set(v)) == 1, f"Values in y_true are not the same for key {k}"

        # Majority class accuracy
        original_sequence = [list(set(v))[0] for k, v in original_sequence_y_true.items()]
        predicted_sequence = [max(set(v), key=v.count) for k, v in original_sequence_y_pred.items()]

        absolute_accuracy = 0
        for i in range(len(original_sequence)):
            if original_sequence[i] == predicted_sequence[i]:
                absolute_accuracy += 1

        majority_accuracy = absolute_accuracy / len(original_sequence)
        majority_accuracy = float(majority_accuracy)

        # original_sequence = [int(x) for x in original_sequence]
        # predicted_sequence = [int(x) for x in predicted_sequence]
    else:
        majority_accuracy = None
        # original_sequence = None
        # predicted_sequence = None

    # Weighted accuracies for each class
    if include_per_class:
        label_categorizations = {}
        for i in range(pm.WINDOW_LENGTH):
            for j in range(len(y_pred)):
                pred = y_pred[j][i]
                actual = y_true[j][i]

                if actual not in label_categorizations:
                    label_categorizations[actual] = []

                label_categorizations[actual].append(pred)

        per_class_metrics = {
            'accuracy': {},
            'precision': {},
            'recall': {},
            'f1': {},
            'weight': {}
        }
        for k, v in label_categorizations.items():
            k = int(k)
            per_class_metrics['accuracy'][k] = float(accuracy_score(v, [k] * len(v)))
            per_class_metrics['precision'][k] = precision_score([k] * len(v), v, average='macro', zero_division=np.nan)
            per_class_metrics['recall'][k] = recall_score([k] * len(v), v, average='macro', zero_division=np.nan)
            per_class_metrics['f1'][k] = f1_score([k] * len(v), v, average='macro', zero_division=np.nan)
            per_class_metrics['weight'][k] = len(v)

    else:
        per_class_metrics = None

    if include_confusion_matrix:
        # Ensure labels are only from y_true
        labels = sorted(list(set(y_true.flatten())))
        sklearn_cm = confusion_matrix(y_true.flatten(), y_pred.flatten(), labels=labels, normalize='true')

        cm = {}
        for i in range(len(sklearn_cm)):
            for j in range(len(sklearn_cm[i])):
                i_label = int(labels[i])
                j_label = int(labels[j])
                if i_label not in cm:
                    cm[i_label] = {}
                # Skip zero values to save space
                if sklearn_cm[i][j] != 0:
                    cm[i_label][j_label] = float(sklearn_cm[i][j])
    else:
        cm = None

    return {
        "core_metrics": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1
        },
        "majority_accuracy": majority_accuracy,
        "per_class_metrics": per_class_metrics,
        "confusion_matrix": cm,
    }


def model_inference(model: models.Model,
                    features: list[str],
                    x_encoders: list[Any],
                    yle: preprocessing.LabelEncoder,
                    data: list[dict],
                    model_version: int = 0) -> dict:
    flattened_data, total_features = preprocess_data(data, features)
    training_data = encode_data(flattened_data, total_features, include_y=False, previous_xenc=x_encoders, model_version=pm.MODEL_VERSION)
    X = training_data['X']

    log.info("Predicting labels...")
    y_pred = model.predict(X)

    log.info("Decoding labels...")
    if model_version == 1:
        y_pred_decoded = np.argmax(y_pred, axis=-1)
    elif model_version == 0:
        y_pred_labels = np.argmax(y_pred, axis=-1)
        y_pred_decoded = decode_labels(y_pred_labels, yle)
    else:
        raise ValueError(f"Unknown model version {model_version}")
    
    return calculate_majorities(data, y_pred_decoded)


def calculate_majorities(data: list[dict],
                         y_pred_decoded: np.ndarray) -> dict:
    # Calculate majorities
    original_sequence_y_pred = {}

    for i in range(len(y_pred_decoded)):
        for j in range(len(y_pred_decoded[i])):
            index = i + j
            if index not in original_sequence_y_pred:
                original_sequence_y_pred[index] = []

            # the more central the value, the more weight it has
            weight = 1 - abs(j - pm.WINDOW_LENGTH / 2) / (pm.WINDOW_LENGTH / 2)
            original_sequence_y_pred[index].append((y_pred_decoded[i][j], weight))

    # Drop sequences that do not have pm.WINDOW_LENGTH elements
    original_sequence_y_pred = {k: v for k, v in original_sequence_y_pred.items() if len(v) == pm.WINDOW_LENGTH}
    selected = sorted(list(original_sequence_y_pred.keys()))

    predicted_sequence = {}
    sequence_weights = {}

    for k, v in original_sequence_y_pred.items():
        # Sum the weights for each label
        weighted_labels = {}
        for label, weight in v:
            if label not in weighted_labels:
                weighted_labels[label] = 0
            weighted_labels[label] += weight

        sequence_weights[int(k)] = {int(k): float(v) for k, v in weighted_labels.items()}
        # log.debug(f"Weights for {k}: {weighted_labels}")

        most_weighted = max(weighted_labels, key=weighted_labels.get)
        predicted_sequence[int(k)] = int(most_weighted)

    if len(predicted_sequence) > len(data):
        raise ValueError(f"Predicted sequence length does not match data length: {len(predicted_sequence)} != {len(data)}. Cannot reshape.")
    elif len(predicted_sequence) < len(data):
        log.warning(f"Shorter predicted sequence than data: {len(predicted_sequence)} != {len(data)}. Reshaping to match.")

    correct = 0
    accounted = 0
    error_statistics = {
        "total": 0,
        "correct": 0,
        "errors": {
            "predicted one, not in it": [],
            "predicted many, not in it": [],
            "predicted many, in it": []
        },
        "indecisions": {}
    }

    for i in range(len(data)):
        if i not in selected:
            continue

        if pm.LABEL_FEATURE not in data[i]:
            continue

        original = data[i][pm.LABEL_FEATURE]
        predicted = predicted_sequence[i]

        if original in (None, LABEL_UNKNOWN, LABEL_IGNORE):
            continue

        accounted += 1

        if original == predicted:
            correct += 1
        else:
            # log.info(f"Error in sequence {i}: (embedded) {original} != {predicted} (predicted)")
            try:
                decoded_original = decode_label(original)
                decoded_predicted = decode_label(predicted)

                decoded_original = decoded_original['raw']
                try:
                    decoded_predicted = decoded_predicted['raw']
                except Exception:
                    log.error("Failed to decode predicted label, skipping")
                    continue

                sequence_weight_local = sequence_weights[i]

                message = f"Error in sequence {i}: (d) {original} != {predicted} (p), "

                if len(sequence_weight_local) > 1:
                    # round to 2 decimals
                    if original in sequence_weight_local.keys():
                        r = "had it in the options"
                        error_statistics["errors"]["predicted many, in it"].append(i)
                        error_statistics["indecisions"][i] = (original, predicted, sequence_weight_local)
                        log.debug(
                            f"Indecision in sequence {i}: predicted {[predicted]}, original {original}, seq {sequence_weight_local}")
                    else:
                        r = "missed it"
                        error_statistics["errors"]["predicted many, not in it"].append(i)
                    message += f"solver {r}: {[(k, round(v, 2)) for k, v in sequence_weight_local.items()]}, "
                else:
                    error_statistics["errors"]["predicted one, not in it"].append(i)
                    message += f"solver only predicted one, "

                for key in decoded_original.keys():
                    if decoded_original[key] != decoded_predicted[key]:
                        message += f"{key}: {decoded_original[key]} != {decoded_predicted[key]}, "

                message = message[:-2]

                log.debug(message)
            except Exception:
                log.exception(f"Failed to manage error message in sequence {i}")

    error_statistics["total"] = accounted
    error_statistics["correct"] = correct

    if accounted == 0:
        log.error("Provided dataset is not labeled, skipping error statistics")

        return {
            "total": len(data),
            "predicted_sequence": [int(x) for x in predicted_sequence.values()],
            "sequence_weights": sequence_weights
        }
    
    else:
        log.info(f"Accuracy on labeled: {correct / accounted} (errors: {accounted - correct} / {accounted})")

        return {
            "accounted": accounted,
            "correct": correct,
            "total": len(data),
            "accuracy": correct / accounted,
            "error_statistics": error_statistics,
            "predicted_sequence": [int(x) for x in predicted_sequence.values()],
            "original_sequence": [d[pm.LABEL_FEATURE] if pm.LABEL_FEATURE in d else None for d in data],
            "sequence_weights": sequence_weights
        }


def open_file(file: str) -> list:
    try:
        with open(file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        log.error('File not found.')
        exit(1)

    assert "lines" in locals(), "No data found in the file."
    assert len(lines) > 0, "No data found in the file."

    data = []
    for line in lines:
        try:
            j = json.loads(line)
            data.append(j)
        except json.JSONDecodeError:
            log.error('Error decoding JSON data.')
            exit(1)

    return data


def save_model(result: dict, base_path: str, model_basename: str = "model.keras"):
    model = result['model']
    model.save(base_path + '/' + model_basename)

    with open(base_path + '/' + model_basename + '.x_encoders', 'wb') as f:
        joblib.dump(result['x_encoders'], f)
    x_encoders: RisingEncoder = result['x_encoders']
    json_x_encoders = x_encoders.get_config()
    with open(base_path + '/' + model_basename + '.x_encoders.json', 'w') as f:
        json.dump(json_x_encoders, f)

    with open(base_path + '/' + model_basename + '.y_encoders', 'wb') as f:
        joblib.dump(result['y_encoders'], f)
    with open(base_path + '/' + model_basename + '.features', 'w') as f:
        json.dump(result['features'], f)


def main(args):
    if not args.file:
        log.error('Please provide a valid file.')
        exit(1)

    if isinstance(args.file, list):
        data = []
        for file in args.file:
            data += open_file(file)
    else:
        data = open_file(args.file)

    if args.hyperparam_tuning:
        tuner_search(data, tuner_type=args.hyperparam_tuning)
        exit(0)

    if not args.model:
        losses = []
        metrics = []

        if args.stats_mode:
            if 'save' in args.stats_mode:
                save_models = True
                log.info('Starting statistics mode with model saving.')
            else:
                save_models = False
                log.info('Starting statistics mode.')

            if 'kfolds' in args.stats_mode:
                log.info("Starting k-fold training.")
                result = kfold_training(data)

                for i in range(len(result)):
                    os.makedirs(pm.OUT_FOLDER + f'/attempt_{i}', exist_ok=True)

                    losses.append(result[i]['history'])
                    metrics.append(result[i]['metrics'])

                    if 'save' in args.stats_mode: 
                        save_model(result[i], pm.OUT_FOLDER + f'/attempt_{i}', model_basename=f'model_{i}.keras')
                        
                        y_pred = result[i]['maj_result']['predicted_sequence']
                        for log_line, label in zip(data, y_pred):
                            log_line["predicted_label"] = label

                        with open(pm.OUT_FOLDER + f'/attempt_{i}/labeled.json', 'w') as f:
                            for line in data:
                                f.write(json.dumps(line) + '\n')

                    with open(pm.OUT_FOLDER + f'/attempt_{i}/inference.json', 'w') as f:
                        json.dump(result[i]['maj_result'], f)
            else:
                for i in range(pm.STATISTICS_ATTEMPTS):
                    result = model_training(data, statistical_mode=True)
                    losses.append(result['history'])
                    metrics.append(result['metrics'])
                    log.info(f"Attempt {i + 1} done.")

                    if save_models:
                        os.makedirs(pm.OUT_FOLDER + f'/attempt_{i}', exist_ok=True)
                        save_model(result, pm.OUT_FOLDER + f'/attempt_{i}', model_basename=f'model_{i}.keras')

        else:
            log.info("Starting model training.")
            result = model_training(data)

            log.info('Model generated.')

            model = result['model']
            losses.append(result['history'])
            metrics.append(result['metrics'])

            save_model(result, pm.OUT_FOLDER)

        # Always save the loss and accuracy data
        with open(pm.OUT_FOLDER + '/loss.json', 'w') as f:
            json.dump([loss.history for loss in losses], f)

        with open(pm.OUT_FOLDER + '/metrics.json', 'w') as f:
            json.dump(metrics, f)

        from model_visualize import plot_loss, plot_metrics
        plot_loss([loss.history for loss in losses])
        plot_metrics(metrics)

    else:
        log.info('Inference mode.')
        model = models.load_model(args.model)
        with open(args.model + '.x_encoders', 'rb') as f:
            x_encoders = joblib.load(f)
        with open(args.model + '.y_encoders', 'rb') as f:
            y_encoders = joblib.load(f)
        with open(args.model + '.features', 'r') as f:
            features = json.load(f)

        result = model_inference(model, features, x_encoders, y_encoders, data,
                                 model_version=pm.MODEL_VERSION)

        if 'save' in args.stats_mode: 
            y_pred = result['predicted_sequence']
            for log_line, label in zip(data, y_pred):
                log_line["predicted_label"] = label

            with open(pm.OUT_FOLDER + '/labeled.json', 'w') as f:
                for line in data:
                    f.write(json.dumps(line) + '\n')

        with open(pm.OUT_FOLDER + '/inference.json', 'w') as f:
            json.dump(result, f)

        if 'error_statistics' in result and result['error_statistics']['total'] > 0:
            from model_visualize import plot_error_statistics
            plot_error_statistics(result['error_statistics'])


if __name__ == '__main__':
    stats_mode_help = "Turns on statistics mode and accepts a comma-separated list of options: " \
                        "save: saves the models generated during the process, else only statistics are saved. " \
                        "kfolds: uses k-fold cross-validation instead of random splits. "

    parser = argparse.ArgumentParser(prog='model')
    parser.add_argument('-f', '--file', type=str, help='Path to the files, one or many', nargs='+', required=True)
    parser.add_argument('-m', '--model', type=str,
                        help='Path to the model file; if provided, will do inference instead of training')
    parser.add_argument('-s', '--stats-mode', nargs='?', const='stats_only', default='',
                        help=stats_mode_help)
    parser.add_argument('-y', '--hyperparam-tuning', type=str,
                        help='Use hyperparameter tuning instead of training')
    parser.add_argument('-l', '--log-level', type=str, help='Log level', default='INFO')
    parser.add_argument('-G', '--gpu', type=int, help='GPU to use, ignored if only one or no GPU is available',
                        default=-1)
    parser.add_argument('--mirroring', action='store_true', help='Use mirrored strategy for multi-GPU training')

    __args = parser.parse_args()

    initialize_log(log_level=__args.log_level)

    if pm.KERAS_BACKEND == 'tensorflow':
        import tensorflow as tf

        physical_devices = tf.config.list_physical_devices('GPU')

        if len(physical_devices) > 1 and 0 <= __args.gpu < len(physical_devices):
            tf.config.experimental.set_visible_devices(physical_devices[__args.gpu], 'GPU')
            log.info(f"Visible device set to {__args.gpu}")

        for device in physical_devices:
            tf.config.experimental.set_memory_growth(device, True)
            log.info("Memory growth enabled for device: " + str(device))

    # also exclude modules imported
    __param = [f"{k}: {v}" for k, v in vars(pm).items() \
               if not k.startswith('__') and not callable(v)
               and (isinstance(v, int) or isinstance(v, float) or isinstance(v, str))]
    __param.extend([f"{k}: {v}" for k, v in __args.__dict__.items() \
                    if not k.startswith('__') and not callable(v)])
    log.info("Starting model generation with the following parameters:")
    for p in __param:
        log.info("" + p)

    if __args.model and __args.stats_mode:
        log.error('Cannot use stats mode with a model file.')
        exit(1)

    if pm.KERAS_BACKEND == "tensorflow" and \
            __args.mirroring and \
            len(tf.config.list_physical_devices('GPU')) > 1:

        strategy = tf.distribute.MirroredStrategy()
        if strategy.num_replicas_in_sync > 1:
            with strategy.scope():
                log.info(f"Number of devices mirroring: {strategy.num_replicas_in_sync}")
                main(__args)
        else:
            main(__args)
    else:
        main(__args)
