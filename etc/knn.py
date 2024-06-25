import random

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier



def generate_knn(data: list[dict]) -> tuple:
    flattened_data = preprocess_data(data)

    # print(flattened_data[0].keys())
    # K nearest neighbors

    X_before, y = [], []
    for d in flattened_data:
        y.append(d[LABEL_FEATURE])
        del d[LABEL_FEATURE]
        X_before.append(d)

    vec = DictVectorizer()
    X = vec.fit_transform(X_before)

    imp = SimpleImputer(missing_values=np.nan, strategy='mean')
    X = imp.fit_transform(X)

    random_state = random.randint(0, 500000)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=random_state)

    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(X_train, y_train)

    y_pred = knn.predict(X_test)

    f1 = accuracy_score(y_test, y_pred)

    model = {
        "vec": vec,
        "imp": imp,
        "knn": knn
    }

    return model, f1


def validate_knn(model: dict, data: dict) -> float:
    flattened_data = preprocess_data(data)

    vec, imp, knn = model["vec"], model["imp"], model["knn"]

    X = []
    for d in flattened_data:
        if LABEL_FEATURE in d:
            print(d)
            raise ValueError("Label feature found in validation data.")
        X.append(d)

    X_t = vec.transform(X)
    X_t2 = imp.transform(X_t)

    y_pred = knn.predict(X_t2)

    return X, y_pred
