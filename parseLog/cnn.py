# {"kind":"Event","apiVersion":"audit.k8s.io/v1","level":"RequestResponse","auditID":"067debb3-be1d-4e0f-b65f-ce1871e60ed9","stage":"ResponseComplete","requestURI":"/apis/node.k8s.io/v1/runtimeclasses?allowWatchBookmarks=true&resourceVersion=3274044&timeout=9m46s&timeoutSeconds=586&watch=true","verb":"watch","user":{"username":"system:kube-controller-manager","groups":["system:authenticated"]},"sourceIPs":["192.168.38.9"],"userAgent":"kube-controller-manager/v1.28.7 (linux/amd64) kubernetes/c8dcb00/shared-informers","objectRef":{"resource":"runtimeclasses","apiGroup":"node.k8s.io","apiVersion":"v1"},"responseStatus":{"metadata":{},"code":200},"requestReceivedTimestamp":"2024-06-05T12:37:08.419005Z","stageTimestamp":"2024-06-05T12:46:54.421057Z","annotations":{"authorization.k8s.io/decision":"allow","authorization.k8s.io/reason":"RBAC: allowed by ClusterRoleBinding \"system:kube-controller-manager\" of ClusterRole \"system:kube-controller-manager\" to User \"system:kube-controller-manager\""},"label":-1}

# Data preprocessing and feature selection

import argparse
import json

import keras.api.callbacks as callbacks
import keras.api.layers as layers
import keras.api.models as models
import numpy as np
from keras.api.utils import to_categorical
from keras.api.optimizers import Adam
from matplotlib import pyplot as plt
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

ATTEMPTS = 40
WINDOW_LENGTH = 40
EPOCHS = 300
PATIENCE = 40
OUT_FOLDER = 'out'

# Features
FEATURES = [
    # "requestURI",
    "verb",
    "user",
    "sourceIPs",
    "userAgent",
    "objectRef",
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


def generate_cnn(data: list[dict]) -> dict:
    flattened_data, total_features = preprocess_data(data)
    x_before, y_before = [], []

    for d in flattened_data:
        y_before.append(d.pop(LABEL_FEATURE))
        x_before.append(list(d.values()))

    len_features = len(total_features)
    assert len(x_before[0]) == len_features, "Number of features do not match."
    len_classes = len(set(y_before))

    print("Features:", len_features)
    print("Classes:", len_classes)

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
    X = np.zeros((len(x_before) - WINDOW_LENGTH, WINDOW_LENGTH, len_features))
    y = np.zeros((len(x_before) - WINDOW_LENGTH, WINDOW_LENGTH, len_classes))

    for i in range(WINDOW_LENGTH, len(x_before)):
        X[i - WINDOW_LENGTH] = x_before[i - WINDOW_LENGTH:i]
        y[i - WINDOW_LENGTH] = y_before_onehot[i - WINDOW_LENGTH:i]

    print(X.shape, y.shape)

    # classification model
    model = models.Sequential([
        layers.Input(shape=(WINDOW_LENGTH, len_features)),
        layers.Conv1D(WINDOW_LENGTH, 3, activation='relu'),
        # layers.Dropout(0.1),
        layers.Conv1D(WINDOW_LENGTH * 2, 3, activation='relu'),
        # layers.Dropout(0.2),
        layers.Conv1D(WINDOW_LENGTH * 4, 3, activation='relu'),
        # layers.Dropout(0.3),
        layers.Conv1D(WINDOW_LENGTH * 8, 3, activation='relu'),
        layers.Flatten(),
        layers.Dropout(0.3),
        layers.Dense(WINDOW_LENGTH * len_classes),
        layers.Reshape((WINDOW_LENGTH, len_classes)),
        layers.Activation('softmax')
    ])

    cb = [
        callbacks.EarlyStopping(monitor='val_loss', patience=PATIENCE, restore_best_weights=True),
        callbacks.ModelCheckpoint(filepath=OUT_FOLDER + '/model-checkpoint.keras', save_best_only=True),
        callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=40)
    ]

    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['categorical_accuracy'],
        
    )

    indices = np.arange(len(X))

    x_train, x_test, y_train, y_test, i_train, i_test = train_test_split(X, y, indices, test_size=0.1, shuffle=True)

    print(model.summary())

    history = model.fit(x_train, y_train, epochs=EPOCHS, callbacks=cb, validation_split=0.2)
    y_pred = model.predict(x_test)

    # y_pred is a tensor of shape (len(x_test), WINDOW_LENGTH, len_classes)
    # let's derive the class labels from this tensor:
    # for example, vector 0 will be in position 0 for the first batch, 1 for the second batch, etc.
    
    y_pred_labels = np.argmax(y_pred, axis=-1)
    y_test_labels = np.argmax(y_test, axis=-1)
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

    # print("Predicted and actual classes for all batches:")
    label_categorizations = {}
    for i in range(WINDOW_LENGTH):
        for j in range(len(y_pred_decoded)):
            pred = y_pred_decoded[j][i]
            actual = y_test_decoded[j][i]

            if pred not in label_categorizations:
                label_categorizations[pred] = []
            label_categorizations[pred].append(actual)

    accuracies = {}
    for k, v in label_categorizations.items():
        accuracies[k] = accuracy_score(v, [k] * len(v))
       #print(f"{k}: {accuracies[k]}")

    print("Weighted accuracy:", sum([len(v) * acc for k, v in label_categorizations.items() for acc in [accuracies[k]]]) / len(y_pred_decoded) / WINDOW_LENGTH)

    return {
        "model": model,
        "y_encoders": yle,
        "x_encoders": xenc,
        "features": total_features,
        "accuracies": accuracies,
        "history": history
    }


def validate_cnn(model: models.Model, features: list[str], yle, data: list[dict]) -> list:
    flattened_data, _ = preprocess_data(data, features)
    x_before = []

    for d in flattened_data:
        x_before.append(list(d.values()))

    x_before = np.array(x_before)
    xenc = []
    for i in range(x_before.shape[1]):
        le = LabelEncoder()
        x_before[:, i] = le.fit_transform(x_before[:, i])
        xenc.append(le)

    # Create batches
    X = np.zeros((len(x_before) - WINDOW_LENGTH, WINDOW_LENGTH, len(features)))

    for i in range(WINDOW_LENGTH, len(x_before)):
        X[i - WINDOW_LENGTH] = x_before[i - WINDOW_LENGTH:i]

    y_pred = model.predict(X)
    y_pred_labels = np.argmax(y_pred, axis=-1)
    y_pred_decoded = []
    for sequence_pred in y_pred_labels:
        y_pred_decoded.append(yle.inverse_transform(sequence_pred))

    y_pred_decoded = np.array(y_pred_decoded)

    predicted = {}

    for i in range(len(y_pred_decoded)):
        for j in range(len(y_pred_decoded[i])):
            if i + j not in predicted:
                predicted[i + j] = []
            predicted[i + j].append(y_pred_decoded[i][j])

    y_final_pred = []
    for k, v in predicted.items():
        y_final_pred.append(max(set(v), key=v.count))

    # for i in range(len(y_final_pred)):
    #     print("Label:", y_final_pred[i])
    #     print("Actual:", data[i]['label'])
        
    # print(predicted)

    return y_final_pred




def open_file(file: str) -> list:
    try:
        with open(file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print('File not found.')
        exit(1)

    assert "lines" in locals(), "No data found in the file."
    assert len(lines) > 0, "No data found in the file."

    data = []
    for line in lines:
        try:
            j = json.loads(line)
            data.append(j)
        except json.JSONDecodeError:
            print('Error decoding JSON data.')
            exit(1)

    return data


def main(args):
    if not args.model:
        if not args.file:
            print('Please provide a valid file.')
            exit(1)

        if type(args.file) == list:
            data = []
            for file in args.file:
                data += open_file(file)
        else:
            data = open_file(args.file)

        losses = []
        accuracies = []

        if args.stats_mode:
            for i in range(ATTEMPTS):
                result = generate_cnn(data)
                history = result['history']
                acc = result['accuracies']
                
                # Plot ALL the losses over the epochs
                losses.append(history)
                accuracies.append(acc)
                print("Attempt", i + 1, "done.")
                print("Final loss:", history.history['loss'][-1])

        else:
            result = generate_cnn(data)

            print('Model generated.')
            
            model = result['model']
            features = result['features']
            yle = result['y_encoders']

            # Save the model and the features
            model.save(OUT_FOLDER + '/model.keras')
            with open(OUT_FOLDER + '/model.keras' + '.features', 'w') as f:
                json.dump(features, f)

            with open(OUT_FOLDER + '/model.keras' + '.x_encoders', 'w') as f:
                json.dump([x.classes_.tolist() for x in result['x_encoders']], f)

            with open(OUT_FOLDER + '/model.keras' + '.y_encoders', 'w') as f:
                json.dump(yle.classes_.tolist(), f)

        # Plot all losses over the epochs
        for loss in losses:
            plt.plot(loss.history['loss'])
        plt.title('Model loss')
        plt.savefig(OUT_FOLDER + '/loss.png')

        # Plot all accuracies
        for acc in accuracies:
            for k, v in acc.items():
                plt.plot(v)
        plt.title('Model accuracy')
        plt.savefig(OUT_FOLDER + '/accuracy.png')


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

    if args.validation_file:
        validation_data = open_file(args.validation_file)
        y_pred = validate_cnn(model, features, yle, validation_data)

        from label_proposer import decode_label

        if 'label' in validation_data[0]:
            val_acc = {}
            for i in range(len(y_pred)):
                predicted = y_pred[i]
                original = validation_data[i]['label']
                if predicted != original:
                    print("Predicted:", predicted, "Original:", original)
                if original not in val_acc:
                    val_acc[original] = []
                val_acc[original].append(predicted)

            weights = []
            for k, v in val_acc.items():
                acc = len([x for x in v if x == k]) / len(v)
                weights.append(len(v) * acc)

            print("Total weighted accuracy:", sum(weights) / len(validation_data))

        else:
            for i in range(len(y_pred)):
                minilog = validation_data[i]
                try:
                    decoded = decode_label(y_pred[i])
                except:
                    decoded = "Unknown label"
                _d = f"{decoded['apiGroup']}/{decoded['version']}/{decoded['uri']} {decoded['verb']}"
                _o = f'{minilog["requestURI"]} {minilog["verb"]}'

                print(f"{y_pred[i]} decoded into {_d} from {_o}")

            # minilog = validation_data[i]
            # decoded = decode_label(label)
            # _d = f"{decoded['apiGroup']}/{decoded['version']}/{decoded['uri']} {decoded['verb']}"
            # _o = f'{minilog["requestURI"]} {minilog["verb"]}'
            # print(f"{label} -> {_d} {_o}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='model')
    parser.add_argument('-f', '--file', type=str, help='Path to the training/test data', nargs='+')
    parser.add_argument('-V', '--validation_file', type=str, help='Path to the validation data')
    parser.add_argument('-m', '--model', type=str, help='Path to the model file')
    parser.add_argument('-s', '--stats-mode', action='store_true', help='Repeat training multiple times to get stats')

    args = parser.parse_args()

    if args.model and args.stats_mode:
        print('Cannot use stats mode with a model file.')
        exit(1)

    if args.model and args.file:
        print('Cannot train a model and use a model file at the same time.')
        exit(1)


    main(args)
