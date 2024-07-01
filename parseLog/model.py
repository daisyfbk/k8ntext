import argparse
import json

import keras.api.callbacks as callbacks
import keras.api.layers as layers
import keras.api.models as models
import numpy as np
from keras.api.optimizers import Adam
from keras.api.utils import to_categorical
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import confusion_matrix

import parameters as pm
from support.log import initialize_log
import logging as log

# Features
FEATURES = [
    # "requestURI",
    "verb",
    "user",
    "sourceIPs",
    "userAgent",
    "objectRef",
    # "cplabel"
    # "requestReceivedTimestamp",
]

EXCLUDE_FEATURES = [
    "user.uid",
    "user.extra.authentication.kubernetes.io/pod-name[0]",
    "user.extra.authentication.kubernetes.io/pod-uid[0]",
]

# APPLY_FILTER_TO_FEATURES = {}

LABEL_FEATURE = "label"


def flatten_object(_object: dict) -> dict:
    keys = _object.keys()
    queue = []
    for k in keys:
        queue.append((k, _object[k]))

    res = {}
    while len(queue) > 0:
        k, v = queue.pop(0)
        if isinstance(v, dict):
            for k2, v2 in v.items():
                queue.append((f"{k}.{k2}", v2))
            continue
        elif isinstance(v, list):
            for i, v2 in enumerate(v):
                queue.append((f"{k}[{i}]", v2))
            continue
        else:
            res[k] = v

    return res


def preprocess_data(__data: list[dict],
                    features: list[str] = None) -> tuple[list[dict], list[str]]:
    # Sort by requestReceivedTimestamp
    __data.sort(key=lambda x: x['requestReceivedTimestamp'])

    # Extract features
    extracted_data = []
    for d in __data:
        o = {}
        for f in FEATURES:
            try:
                o[f] = d[f]
            except KeyError:
                o[f] = None

        if LABEL_FEATURE in d:
            o["label"] = d[LABEL_FEATURE]
        extracted_data.append(o)

    # Flatten the features
    flattened_data = []
    for d in extracted_data:
        flattened_data.append(flatten_object(d))

    # Add missing features and remove excluded features
    if features is None:
        # Generate the feature list
        features = set()
        for d in flattened_data:
            for k in d.keys():
                features.add(k)
        total_features = [f for f in features if f not in EXCLUDE_FEATURES]
    else:
        # Use the provided feature list
        total_features = features

    total_features.sort()

    # Remove excluded features
    res = []
    for d in flattened_data:
        obj = {}
        for f in total_features:
            try:
                obj[f] = d[f]
            except KeyError:
                obj[f] = None
        res.append({k: obj[k] for k in sorted(obj.keys())})

    if LABEL_FEATURE in total_features:
        total_features.remove(LABEL_FEATURE)

    return res, total_features


def generate_model(data: list[dict]) -> dict:
    flattened_data, total_features = preprocess_data(data)
    x_before, y_before = [], []

    for d in flattened_data:
        y_before.append(d.pop(LABEL_FEATURE))
        x_before.append(list(d.values()))

    len_features = len(total_features)
    assert len(x_before[0]) == len_features, "Number of features do not match."
    len_classes = len(set(y_before))

    log.info(f"Features: {len_features}")
    log.info(f"Classes: {len_classes}")

    x_before = np.array(x_before)

    xenc = []
    for i in range(x_before.shape[1]):
        le = LabelEncoder()
        x_before[:, i] = le.fit_transform(x_before[:, i])
        xenc.append(le)

    # One-hot encoding for y_before
    yle = LabelEncoder()
    y_before_encoded = yle.fit_transform(y_before)
    y_before_onehot = to_categorical(y_before_encoded, num_classes=len_classes)

    # Create batches
    X = np.zeros((len(x_before) - pm.WINDOW_LENGTH, pm.WINDOW_LENGTH, len_features))
    y = np.zeros((len(x_before) - pm.WINDOW_LENGTH, pm.WINDOW_LENGTH, len_classes))

    for i in range(pm.WINDOW_LENGTH, len(x_before)):
        X[i - pm.WINDOW_LENGTH] = x_before[i - pm.WINDOW_LENGTH:i]
        y[i - pm.WINDOW_LENGTH] = y_before_onehot[i - pm.WINDOW_LENGTH:i]

    log.info(f"Resulting shapes: {X.shape}, {y.shape}")

    # classification model
    model = models.Sequential([
        layers.Input(shape=(pm.WINDOW_LENGTH, len_features)),
        layers.LSTM(len_features * 8, return_sequences=True),
        layers.LSTM(len_features * 4, return_sequences=True),
        layers.LSTM(len_features * 2, return_sequences=True),
        layers.Dropout(0.2),
        layers.TimeDistributed(layers.Dense(len_classes)),
        layers.Activation('softmax')
    ])

    cb = [
        callbacks.EarlyStopping(monitor='val_loss', patience=pm.EARLY_STOPPING_PATIENCE, restore_best_weights=True),
        callbacks.ModelCheckpoint(filepath=pm.OUT_FOLDER + '/model-checkpoint.keras', save_best_only=True),
        callbacks.ReduceLROnPlateau(monitor='val_loss', factor=pm.REDUCE_LR_FACTOR, patience=pm.REDUCE_LR_PATIENCE)
    ]

    model.compile(
        optimizer=Adam(learning_rate=pm.INITIAL_LEARNING_RATE),
        loss='categorical_crossentropy',
        metrics=['categorical_accuracy'],

    )

    indices = np.arange(len(X))

    x_train, x_test, y_train, y_test, i_train, i_test = train_test_split(X, y, indices, test_size=pm.TEST_TRAIN_SPLIT)

    print(model.summary())

    history = model.fit(x_train, y_train, epochs=pm.MAX_EPOCHS, callbacks=cb, validation_split=pm.TRAIN_VALID_SPLIT)
    y_pred = model.predict(x_test)

    # y_pred is a tensor of shape (len(x_test), WINDOW_LENGTH, len_classes)
    # let's derive the class labels from this tensor:
    # for example, vector 0 will be in position 0 for the first batch, 1 for the second batch, etc.

    y_pred_labels = np.argmax(y_pred, axis=-1)
    y_test_labels = np.argmax(y_test, axis=-1)
    
    # original_positions = np.argsort(i_test)

    # y_pred_labels_unshuffled = y_pred_labels[original_positions]
    # y_test_labels_unshuffled = y_test_labels[original_positions]

    y_pred_decoded = []
    y_test_decoded = []

    # Iterate over each sequence
    for sequence_pred, sequence_test in zip(y_pred_labels, y_test_labels):
        # Inverse transform each sequence and append to the decoded lists
        y_pred_decoded.append(yle.inverse_transform(sequence_pred))
        y_test_decoded.append(yle.inverse_transform(sequence_test))

    # Convert lists of arrays back to 2D arrays if necessary
    y_pred_decoded = np.array(y_pred_decoded)
    y_test_decoded = np.array(y_test_decoded)

    accuracies, ori_seq, pred_seq = calculate_accuracy(y_test_decoded, y_pred_decoded,
                                                       include_majority_accuracy=False,
                                                       include_class_accuracies=True,
                                                       include_confusion_matrix=True)

    log.info(f"Model accuracy (accuracy_score): {accuracies['model_accuracy']}")
    log.info(f"Majority class accuracy: {accuracies['majority_accuracy']}")

    return {
        "model": model,
        "y_encoders": yle,
        "x_encoders": xenc,
        "features": total_features,
        "accuracies": accuracies,
        "original_sequence": ori_seq,
        "predicted_sequence": pred_seq,
        "history": history
    }


def calculate_accuracy(y_true, y_pred,
                       include_majority_accuracy = False,
                       include_class_accuracies = False,
                       include_confusion_matrix = False) -> tuple[dict, list | None, list | None]:
    if y_true.shape != y_pred.shape:
        raise ValueError("Shapes of y_true and y_pred do not match.")
    
    model_accuracy = accuracy_score(y_true.flatten(), y_pred.flatten())
    model_accuracy = float(model_accuracy)

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

        original_sequence = [int(x) for x in original_sequence]
        predicted_sequence = [int(x) for x in predicted_sequence]
    else:
        majority_accuracy = None
        original_sequence = None
        predicted_sequence = None

    # Weighted accuracies for each class
    if include_class_accuracies:
        label_categorizations = {}
        for i in range(pm.WINDOW_LENGTH):
            for j in range(len(y_pred)):
                pred = y_pred[j][i]
                actual = y_true[j][i]

                if actual not in label_categorizations:
                    label_categorizations[actual] = []

                label_categorizations[actual].append(pred)

        per_class_accuracies = {}
        per_class_weights = {}
        for k, v in label_categorizations.items():
            k = int(k)
            per_class_accuracies[k] = float(accuracy_score(v, [k] * len(v)))
            per_class_weights[k] = len(v)

    else:
        per_class_accuracies = None
        per_class_weights = None

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
        "model_accuracy": model_accuracy,
        "majority_accuracy": majority_accuracy,
        "per_class_accuracies": per_class_accuracies,
        "per_class_weights": per_class_weights,
        "confusion_matrix": cm
    }, original_sequence, predicted_sequence
    

def validate_model(model: models.Model, features: list[str], yle, data: list[dict]) -> list:#
    # flattened_data, _ = preprocess_data(data, features)
    # x_before = []

    # for d in flattened_data:
    #     x_before.append(list(d.values()))

    # x_before = np.array(x_before)
    # xenc = []
    # for i in range(x_before.shape[1]):
    #     le = LabelEncoder()
    #     x_before[:, i] = le.fit_transform(x_before[:, i])
    #     xenc.append(le)

    # # Create batches
    # X = np.zeros((len(x_before) - pm.WINDOW_LENGTH, pm.WINDOW_LENGTH, len(features)))

    # for i in range(pm.WINDOW_LENGTH, len(x_before)):
    #     X[i - pm.WINDOW_LENGTH] = x_before[i - pm.WINDOW_LENGTH:i]

    # y_pred = model.predict(X)
    # y_pred_labels = np.argmax(y_pred, axis=-1)
    # y_pred_decoded = []
    # for sequence_pred in y_pred_labels:
    #     y_pred_decoded.append(yle.inverse_transform(sequence_pred))

    # y_pred_decoded = np.array(y_pred_decoded)

    # predicted = {}

    # for i in range(len(y_pred_decoded)):
    #     for j in range(len(y_pred_decoded[i])):
    #         if i + j not in predicted:
    #             predicted[i + j] = []
    #         predicted[i + j].append(y_pred_decoded[i][j])

    # y_final_pred = []
    # for k, v in predicted.items():
    #     y_final_pred.append(max(set(v), key=v.count))

    # #### START OF WIP CODE
    # ####
    # ####

    # from label_proposer import decode_label

    # if 'label' in validation_data[0]:
    #     val_acc = {}
    #     for i in range(len(y_pred)):
    #         predicted = y_pred[i]
    #         original = validation_data[i]['label']
    #         if predicted != original:
    #             print("Predicted: ", predicted, "Original: ", original)
    #         if original not in val_acc:
    #             val_acc[original] = []
    #         val_acc[original].append(predicted)

    #     weights = []
    #     for k, v in val_acc.items():
    #         acc = len([x for x in v if x == k]) / len(v)
    #         weights.append(len(v) * acc)

    #     print("Total weighted accuracy:", sum(weights) / len(validation_data))

    # else:
    #     for i in range(len(y_pred)):
    #         minilog = validation_data[i]
    #         try:
    #             decoded = decode_label(y_pred[i])
    #         except:
    #             decoded = "Unknown label"
    #         _d = f"{decoded['apiGroup']}/{decoded['version']}/{decoded['uri']} {decoded['verb']}"
    #         _o = f'{minilog["requestURI"]} {minilog["verb"]}'

    #         print(f"{y_pred[i]} decoded into {_d} from {_o}")

    #     # minilog = validation_data[i]
    #     # decoded = decode_label(label)
    #     # _d = f"{decoded['apiGroup']}/{decoded['version']}/{decoded['uri']} {decoded['verb']}"
    #     # _o = f'{minilog["requestURI"]} {minilog["verb"]}'
    #     # print(f"{label} -> {_d} {_o}")

    # ####
    # ####
    # #### END OF WIP CODE
    y_final_pred = None
    return y_final_pred


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
    if not args.model:
        if not args.file:
            log.error('Please provide a valid file.')
            exit(1)

        if isinstance(args.file, list):
            data = []
            for file in args.file:
                data += open_file(file)
        else:
            data = open_file(args.file)

        losses = []
        accuracies = []

        if args.stats_mode:
            for i in range(pm.STATISTICS_ATTEMPTS):
                result = generate_model(data)
                history = result['history']
                acc = result['accuracies']

                # Plot ALL the losses over the epochs
                losses.append(history)
                accuracies.append(acc)
                log.info(f"Attempt {i + 1} done.")
                log.info(f"Final loss: {history.history['loss'][-1]}")

        else:
            result = generate_model(data)

            log.info('Model generated.')

            model = result['model']
            losses.append(result['history'])
            accuracies.append(result['accuracies'])
    
            # Save the model and the features
            model.save(pm.OUT_FOLDER + '/model.keras')
            with open(pm.OUT_FOLDER + '/model.keras' + '.x_encoders', 'w') as f:
                json.dump([x.classes_.tolist() for x in result['x_encoders']], f)
            with open(pm.OUT_FOLDER + '/model.keras' + '.y_encoders', 'w') as f:
                json.dump(result['y_encoders'].classes_.tolist(), f)
            with open(pm.OUT_FOLDER + '/model.keras' + '.features', 'w') as f:
                json.dump(result['features'], f)
            with open(pm.OUT_FOLDER + '/model.keras' + '.original_sequence', 'w') as f:
                json.dump(result['original_sequence'], f)
            with open(pm.OUT_FOLDER + '/model.keras' + '.predicted_sequence', 'w') as f:
                json.dump(result['predicted_sequence'], f)


            from model_visualize import plot_confusion_matrix
            plot_confusion_matrix(accuracies[0])

        # Always save the loss and accuracy data
        with open(pm.OUT_FOLDER + '/loss.json', 'w') as f:
            json.dump([loss.history for loss in losses], f)
        with open(pm.OUT_FOLDER + '/accuracy.json', 'w') as f:
            json.dump(accuracies, f)

        from model_visualize import plot_loss, plot_accuracy
        plot_loss(losses)
        plot_accuracy(accuracies)

    else:
        model = models.load_model(args.model)
        with open(args.model + '.features', 'r') as f:
            features = json.load(f)
        with open(args.model + '.x_encoders', 'r') as f:
            x_encoders = json.load(f)
            xenc = [LabelEncoder().fit(x) for x in x_encoders]
        with open(args.model + '.y_encoders', 'r') as f:
            y_encoders = json.load(f)
            yle = LabelEncoder().fit(y_encoders)

        validation_data = open_file(args.validation_file)
        y_pred = validate_model(model, features, yle, validation_data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='model')
    parser.add_argument('-f', '--file', type=str, help='Path to the files, one or many', nargs='+')
    parser.add_argument('-m', '--model', type=str,
                        help='Path to the model file; if provided, will do inference instead of training')
    parser.add_argument('-s', '--stats-mode', action='store_true',
                        help='Repeat process multiple times for statistics')

    __args = parser.parse_args()

    initialize_log(log_level="INFO")

    # also exclude modules imported
    __param_str = ', '.join([f"{k}: {v}" for k, v in vars(pm).items() if not k.startswith('__') and not callable(v)])
    log.info("Starting model generation with the following parameters: " + __param_str)

    if __args.model and __args.stats_mode:
        log.error('Cannot use stats mode with a model file.')
        exit(1)

    if __args.model and __args.file:
        log.error('Cannot train a model and use a model file at the same time.')
        exit(1)

    main(__args)
