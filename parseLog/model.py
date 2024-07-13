import argparse
import collections
import json
import logging as log
from typing import Any

import joblib
from keras import callbacks, losses, metrics as keras_metrics, models, layers
import numpy as np
import sklearn.preprocessing as preprocessing
from keras.api.optimizers import Adam
from keras.api.utils import to_categorical
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

from label_proposer import brute_force_label_space, decode_label
import model_features
import parameters as pm
from common import flatten_object, LABEL_UNKNOWN, tqdm
from model_encoder import AuditEncoder, RisingEncoder
from model_tuner import tuner_search
from support.log import initialize_log, activate_stdout_logging, silence_stdout_logging


def preprocess_data(__data: list[dict],
                    features: list[str] = None) -> tuple[list[dict], list[str]]:
    # Sort by requestReceivedTimestamp
    __data.sort(key=lambda x: x['requestReceivedTimestamp'])

    # from random import shuffle
    # shuffle(__data)

    # Flatten the features
    flattened_data = []
    for d in __data:
        flattened_data.append(flatten_object(d))

    # Perform feature preprocessing if necessary
    for d in flattened_data:
        for f, p in model_features.FEATURE_PREPROCESSING.items():
            if f in d:
                d[f] = p(d[f])

    # Extract features
    extracted_data = []
    for d in flattened_data:
        o = {}
        for f in model_features.FEATURES:
            try:
                o[f] = d[f]
            except KeyError:
                o[f] = None

        if pm.LABEL_FEATURE in d:
            o["label"] = d[pm.LABEL_FEATURE]
        extracted_data.append(o)

    # Add missing features and remove excluded features
    if features is None:
        total_features = model_features.FEATURES
    else:
        # Use the provided feature list
        total_features = features

    total_features.sort()

    # Generate the feature list
    #            if k not in mapped_data:
    #                mapped_data[k] = []
    #            mapped_data[k].append(d[k])
    #    with open(pm.OUT_FOLDER + '/features.json', 'w') as f:
    #        json.dump(mapped_data, f)
    #    # Group by feature in mapped_data
    #    stats = {}
    #    for k in mapped_data.keys():
    #        try:
    #            stats[k] = {
    #                "top20": collections.Counter(mapped_data[k]).most_common(10)
    #            }
    #        except TypeError:
    #            stats[k] = {
    #                "top20": None
    #            }
    #    with open(pm.OUT_FOLDER + '/features_stats.json', 'w') as f:
    #        json.dump(stats, f, indent=2)
    #    exit(1)

    # Remove excluded features
    res = []
    for d in flattened_data:
        obj = {}
        for f in total_features + [pm.LABEL_FEATURE]:
            try:
                obj[f] = d[f]
            except KeyError:
                obj[f] = None
        res.append({k: obj[k] for k in sorted(obj.keys())})

    if pm.LABEL_FEATURE in total_features:
        total_features.remove(pm.LABEL_FEATURE)

    return res, total_features


def generate_model(X_shape: int, y_shape: int | tuple) -> models.Model:
    model = models.Sequential([
        layers.Input(shape=(pm.WINDOW_LENGTH, X_shape)),
        layers.LSTM(X_shape * 4, return_sequences=True, name='lstm_8x'),
        layers.LSTM(X_shape * 8, return_sequences=True, name='lstm_4x'),
        layers.LSTM(X_shape * 8, return_sequences=True, name='lstm_2x'),
        layers.Dropout(0.3, name='dropout'),
        layers.TimeDistributed(layers.Dense(y_shape[0] * y_shape[1], name='dense'), name='time_distributed'),
        layers.Reshape((pm.WINDOW_LENGTH, y_shape[0], y_shape[1]), name='reshape'),
        # layers.Dropout(0.5, name='dropout_2'),
        layers.Activation('softmax', name='softmax')
    ])

    mt = [
        keras_metrics.Precision(name='precision'),
        keras_metrics.Recall(name='recall'),
        keras_metrics.CategoricalAccuracy(name='categorical_accuracy')
    ]

    model.compile(
        optimizer=Adam(learning_rate=pm.INITIAL_LEARNING_RATE),
        loss=losses.CategoricalCrossentropy(),
        metrics=mt
    )

    return model


def encode_data(flattened_data: list[dict],
                total_features: list[str],
                include_y: bool = True,
                previous_xenc: list | None = None
                ) -> dict:
    x_before = []
    if include_y:
        y_before = []

    for d in flattened_data:
        if include_y:
            y_before.append(d.pop(pm.LABEL_FEATURE))
        else:
            d.pop(pm.LABEL_FEATURE)
        x_before.append(list(d.values()))

    len_features = len(total_features)
    assert len(x_before[0]) == len_features, "Number of features do not match."
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
        yle = AuditEncoder()
        len_labeltypes = 5
        len_subclasses = yle.length
        y_encoded = yle.fit_transform(y_before)
        y_onehot = to_categorical(y_encoded, num_classes=len_subclasses)

        log.info(f"Classes: {len_classes}, cast to a one-hot encoding of {len_labeltypes} x {len_subclasses}")

        # Previous implementation
        # yle = preprocessing.LabelEncoder()
        # y_encoded = yle.fit_transform(y_before)
        # y_onehot = to_categorical(y_encoded, num_classes=len_classes)

    # Create batches
    X = np.zeros((len(x_before) - pm.WINDOW_LENGTH + 1, pm.WINDOW_LENGTH, len_features))
    if include_y:
        y = np.zeros((len(x_before) - pm.WINDOW_LENGTH + 1, pm.WINDOW_LENGTH, len_labeltypes, len_subclasses))
        # Previous implementation
        # y = np.zeros((len(x_before) - pm.WINDOW_LENGTH + 1, pm.WINDOW_LENGTH, len_classes))

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
            "y_shape": (len_labeltypes, len_subclasses),
            # Previous implementation "y_shape": len_classes
        }
    else:
        log.info(f"Resulting shapes: {X.shape}")
        return {
            "X": X,
            "x_encoders": xenc,
            "X_shape": len_features
        }


def model_training(data: list[dict],
                   statistical_mode: bool = False) -> dict:
    flattened_data, total_features = preprocess_data(data)

    training_data = encode_data(flattened_data, total_features)
    xenc = training_data['x_encoders']
    yle = training_data['y_encoder']
    X_shape = training_data['X_shape']
    y_shape = training_data['y_shape']

    model = generate_model(X_shape, y_shape)

    # indices = np.arange(len(X))
    # x_train, x_test, y_train, y_test, i_train, i_test = train_test_split(X, y, indices, test_size=pm.TEST_TRAIN_SPLIT)
    x_train, x_test, y_train, y_test = train_test_split(
        training_data['X'],
        training_data['y'],
        test_size=pm.TEST_TRAIN_SPLIT)

    print(model.summary())

    cb = [
        callbacks.EarlyStopping(monitor='val_loss',
                                patience=pm.EARLY_STOPPING_PATIENCE,
                                restore_best_weights=True,
                                verbose=1),
        callbacks.ReduceLROnPlateau(monitor='val_loss',
                                    factor=pm.REDUCE_LR_FACTOR,
                                    patience=pm.REDUCE_LR_PATIENCE,
                                    verbose=1),
    ]

    if not statistical_mode:
        cb += [
            callbacks.BackupAndRestore(backup_dir=pm.OUT_FOLDER + '/backup'),
            callbacks.ModelCheckpoint(filepath=pm.OUT_FOLDER + '/model-checkpoint.keras', save_best_only=True),
            # log metrics
            callbacks.LambdaCallback(
                on_train_begin=lambda logs: log.info(f"Training started: {logs}"),
                on_train_end=lambda logs: log.info(f"Training ended: {logs}"),
                on_epoch_end=lambda epoch, logs: log.info(f"Epoch {epoch}: {logs}"),
            )
        ]

    silence_stdout_logging()
    history = model.fit(x_train, y_train, epochs=pm.MAX_EPOCHS, callbacks=cb, validation_split=pm.TRAIN_VALID_SPLIT)
    y_pred = model.predict(x_test)
    activate_stdout_logging()

    y_pred_sublabels = np.argmax(y_pred, axis=-1)
    y_test_sublabels = np.argmax(y_test, axis=-1)

    y_pred_decoded = []
    y_test_decoded = []

    log.info("Decoding labels (predicted)...")
    for sequence_pred in tqdm(y_pred_sublabels):
        y_pred_decoded.append(yle.inverse_transform(sequence_pred))

    log.info("Decoding labels (actual)...")
    for sequence_test in tqdm(y_test_sublabels):
        y_test_decoded.append(yle.inverse_transform(sequence_test))

    y_pred_decoded = np.array(y_pred_decoded)
    y_test_decoded = np.array(y_test_decoded)
    metrics = calculate_metrics(y_test_decoded,
                                y_pred_decoded,
                                include_per_class=True,
                                include_confusion_matrix=True)

    log.info(f"Model metrics (core): {metrics['core_metrics']}")

    return {
        "model": model,
        "y_encoders": yle,
        "x_encoders": xenc,
        "features": total_features,
        "metrics": metrics,
        "history": history
    }


def calculate_metrics(y_true, y_pred,
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
            per_class_metrics['precision'][k] = precision_score([k] * len(v), v, average='macro', zero_division=0)
            per_class_metrics['recall'][k] = recall_score([k] * len(v), v, average='macro', zero_division=0)
            per_class_metrics['f1'][k] = f1_score([k] * len(v), v, average='macro', zero_division=0)
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
                    data: list[dict]) -> list:
    flattened_data, total_features = preprocess_data(data, features)
    training_data = encode_data(flattened_data, total_features, include_y=False, previous_xenc=x_encoders)
    X = training_data['X']

    log.info("Predicting labels...")
    y_pred = model.predict(X)

    y_pred_labels = np.argmax(y_pred, axis=-1)

    y_pred_decoded = []

    log.info("Decoding labels...")
    for sequence_pred in tqdm(y_pred_labels):
        y_pred_decoded.append(yle.inverse_transform(sequence_pred))

    y_pred_decoded = np.array(y_pred_decoded)

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

    predicted_sequence = []
    for k, v in original_sequence_y_pred.items():
        # Sum the weights for each label
        weighted_labels = {}
        for label, weight in v:
            if label not in weighted_labels:
                weighted_labels[label] = 0
            weighted_labels[label] += weight

        # Get the label with the highest weight
        most_weighted = max(weighted_labels, key=weighted_labels.get)
        ## Get most common element in the list
        #most_common = collections.Counter(v).most_common()
        #if len(most_common) == 1:
        #    # If there is only one element, use it
        #    predicted_sequence.append(int(most_common[0][0]))
        #elif most_common[0][1] > most_common[1][1]:
        #    # If the first element is absolute majority, use it
        #    predicted_sequence.append(int(most_common[0][0]))
        #else:
        #    # If there is a tie, insert all the elements with equal weight
        #    tmp = []
        #    item, count = most_common[0]
        #    while len(most_common) > 0 and most_common[0][1] == count:
        #        tmp.append(int(most_common.pop(0)[0]))
        #    predicted_sequence.append(tmp)
        predicted_sequence.append(int(most_weighted))

    assert len(predicted_sequence) == len(
        data), f"Predicted sequence length does not match data length: {len(predicted_sequence)} != {len(flattened_data)}"

    ok = 0
    cpcount = 0
    for i in range(len(data)):
        if pm.LABEL_FEATURE not in data[i]:
            continue
        if data[i][pm.LABEL_FEATURE] in (None, LABEL_UNKNOWN):
            continue
        cpcount += 1
        if data[i][pm.LABEL_FEATURE] == predicted_sequence[i]:
            ok += 1
        else:
            # log.info(f"Error in sequence {i}: (embedded) {data[i][pm.LABEL_FEATURE]} != {predicted_sequence[i]} (predicted)")
            try:
                decoded_original = decode_label(data[i][pm.LABEL_FEATURE])['raw']
                decoded_predicted = decode_label(predicted_sequence[i])['raw']
                message = f"Error in sequence {i}: "
                for key in decoded_original.keys():
                    if decoded_original[key] != decoded_predicted[key]:
                        message += f"{key}: {decoded_original[key]} != {decoded_predicted[key]}, "
                log.warning(message)
            except Exception:
                pass

    log.info(f"Accuracy on labeled: {ok / cpcount} (errors: {cpcount - ok} / {cpcount})")

    return predicted_sequence


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
            for i in range(pm.STATISTICS_ATTEMPTS):
                result = model_training(data, statistical_mode=True)
                losses.append(result['history'])
                metrics.append(result['metrics'])
                log.info(f"Attempt {i + 1} done.")
        else:
            result = model_training(data)

            log.info('Model generated.')

            model = result['model']
            losses.append(result['history'])
            metrics.append(result['metrics'])

            # Save the model and the features
            model.save(pm.OUT_FOLDER + '/model.keras')
            with open(pm.OUT_FOLDER + '/model.keras' + '.x_encoders', 'wb') as f:
                joblib.dump(result['x_encoders'], f)
            with open(pm.OUT_FOLDER + '/model.keras' + '.y_encoders', 'wb') as f:
                joblib.dump(result['y_encoders'], f)
            with open(pm.OUT_FOLDER + '/model.keras' + '.features', 'w') as f:
                json.dump(result['features'], f)
            # with open(pm.OUT_FOLDER + '/model.keras' + '.original_sequence', 'w') as f:
            #     json.dump(result['original_sequence'], f)
            # with open(pm.OUT_FOLDER + '/model.keras' + '.predicted_sequence', 'w') as f:
            #     json.dump(result['predicted_sequence'], f)

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

        y_pred = model_inference(model, features, x_encoders, y_encoders, data)

        for log_line, label in zip(data, y_pred):
            log_line["predicted_label"] = label

        with open(pm.OUT_FOLDER + '/results.json', 'w') as f:
            for line in data:
                f.write(json.dumps(line) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='model')
    parser.add_argument('-f', '--file', type=str, help='Path to the files, one or many', nargs='+')
    parser.add_argument('-m', '--model', type=str,
                        help='Path to the model file; if provided, will do inference instead of training')
    parser.add_argument('-s', '--stats-mode', action='store_true',
                        help='Repeat process multiple times for statistics')
    parser.add_argument('-y', '--hyperparam-tuning', type=str,
                        help='Use hyperparameter tuning instead of training')

    __args = parser.parse_args()

    initialize_log(log_level="INFO")

    if pm.KERAS_BACKEND == 'tensorflow':
        # os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
        import tensorflow as tf

        physical_devices = tf.config.list_physical_devices('GPU')
        for device in physical_devices:
            tf.config.experimental.set_memory_growth(device, True)
            log.info("Memory growth enabled for device: " + str(device))

    # also exclude modules imported
    __param = [f"{k}: {v}" for k, v in vars(pm).items() if not k.startswith('__') and not callable(v)
               and (isinstance(v, int) or isinstance(v, float) or isinstance(v, str))]
    log.info("Starting model generation with the following parameters:")
    for p in __param:
        log.info("" + p)

    if __args.model and __args.stats_mode:
        log.error('Cannot use stats mode with a model file.')
        exit(1)

    main(__args)
