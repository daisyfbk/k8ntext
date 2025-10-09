import json
import logging as log

import numpy as np
from keras import models
from trustee import ClassificationTrustee


def generate_trustee_explanation(model: models.Model,
                                 x_train: np.ndarray,
                                 y_train: np.ndarray,
                                 x_test: np.ndarray,
                                 y_test: np.ndarray,
                                 feature_names: list = None,
                                 model_version: int = 0,
                                 num_iter: int = 50,
                                 num_stability_iter: int = 10,
                                 samples_size: float = 0.3) -> dict:
    """
    Generate model explanations using Trustee framework.

    Args:
        model: Trained Keras model
        x_train: Training features
        y_train: Training labels
        x_test: Test features  
        y_test: Test labels
        feature_names: List of feature names for interpretable output
        model_version: Model version (0 for multiclass, 1 for binary)
        num_iter: Number of iterations for Trustee
        num_stability_iter: Number of stability iterations
        samples_size: Sample size for explanation generation

    Returns:
        Dictionary containing explanation results and metrics
    """
    log.info("Starting Trustee explanation generation...")
    log.debug(f"Input types - x_train: {type(x_train)}, y_train: {type(y_train)}")
    log.debug(f"Input types - x_test: {type(x_test)}, y_test: {type(y_test)}")

    # Ensure all inputs are numpy arrays
    if not isinstance(x_train, np.ndarray):
        log.debug("Converting x_train to numpy array")
        x_train = np.array(x_train)
    if not isinstance(y_train, np.ndarray):
        log.debug("Converting y_train to numpy array")
        y_train = np.array(y_train)
    if not isinstance(x_test, np.ndarray):
        log.debug("Converting x_test to numpy array")
        x_test = np.array(x_test)
    if not isinstance(y_test, np.ndarray):
        log.debug("Converting y_test to numpy array")
        y_test = np.array(y_test)

    log.debug(f"Input shapes - x_train: {x_train.shape}, y_train: {y_train.shape}")
    log.debug(f"Input shapes - x_test: {x_test.shape}, y_test: {y_test.shape}")

    if len(x_train.shape) == 3:  # (samples, timesteps, features)
        x_train_flat = x_train.reshape(x_train.shape[0], -1)
        x_test_flat = x_test.reshape(x_test.shape[0], -1)
        log.debug(f"Flattened X shapes - x_train_flat: {x_train_flat.shape}, x_test_flat: {x_test_flat.shape}")

        # Generate meaningful feature names for flattened sequence data
        if feature_names is not None:
            flattened_feature_names = []
            timesteps = x_train.shape[1]  # Number of timesteps
            for t in range(timesteps):
                for feature_name in feature_names:
                    flattened_feature_names.append(f"{feature_name}_t{t}")
            log.debug(f"Generated {len(flattened_feature_names)} flattened feature names")
        else:
            flattened_feature_names = None
    else:
        x_train_flat = x_train
        x_test_flat = x_test
        flattened_feature_names = feature_names

    # Handle different model versions
    if model_version == 0:  # Multiclass
        # For multiclass, we need to handle the complex shape properly
        if len(y_train.shape) == 4:  # (samples, timesteps, label_types, subclasses)
            # For each sample, take the first timestep and flatten the label structure
            y_train_flat = y_train[:, 0, :, :].reshape(y_train.shape[0], -1)
            y_test_flat = y_test[:, 0, :, :].reshape(y_test.shape[0], -1)
            # Convert to single class labels by taking argmax across the flattened dimension
            y_train_flat = np.argmax(y_train_flat, axis=1)
            y_test_flat = np.argmax(y_test_flat, axis=1)
        elif len(y_train.shape) == 3:  # (samples, timesteps, classes)
            # Take the first timestep as representative
            y_train_flat = np.argmax(y_train[:, 0, :], axis=-1)
            y_test_flat = np.argmax(y_test[:, 0, :], axis=-1)
        else:
            y_train_flat = np.argmax(y_train, axis=-1)
            y_test_flat = np.argmax(y_test, axis=-1)
    else:  # Binary
        if len(y_train.shape) == 3:  # (samples, timesteps, classes)
            # Take the first timestep as representative
            y_train_flat = np.argmax(y_train[:, 0, :], axis=-1)
            y_test_flat = np.argmax(y_test[:, 0, :], axis=-1)
        else:
            y_train_flat = np.argmax(y_train, axis=-1)
            y_test_flat = np.argmax(y_test, axis=-1)

    log.debug(f"Flattened Y shapes - y_train_flat: {y_train_flat.shape}, y_test_flat: {y_test_flat.shape}")
    log.debug(
        f"Y label value ranges - y_train: [{y_train_flat.min()}, {y_train_flat.max()}], y_test: [{y_test_flat.min()}, {y_test_flat.max()}]")

    # Verify that X and y have the same number of samples
    assert x_train_flat.shape[0] == y_train_flat.shape[
        0], f"Training data shape mismatch: X={x_train_flat.shape[0]}, y={y_train_flat.shape[0]}"
    assert x_test_flat.shape[0] == y_test_flat.shape[
        0], f"Test data shape mismatch: X={x_test_flat.shape[0]}, y={y_test_flat.shape[0]}"

    # Create a wrapper for the model to handle sequence prediction
    class ModelWrapper:
        def __init__(self, model, original_shape, model_version):
            self.model = model
            self.original_shape = original_shape
            self.model_version = model_version

        def predict(self, X):
            # Ensure X is a numpy array
            if not isinstance(X, np.ndarray):
                X = np.array(X)

            # Reshape back to original sequence format
            X_reshaped = X.reshape(-1, self.original_shape[1], self.original_shape[2])
            predictions = self.model.predict(X_reshaped, verbose=0)

            # Ensure predictions is a numpy array
            if not isinstance(predictions, np.ndarray):
                predictions = np.array(predictions)

            # For sequence models, we need to handle the output properly
            if self.model_version == 0:  # Multiclass
                if len(predictions.shape) == 4:  # (samples, timesteps, label_types, subclasses)
                    # Take the first timestep and flatten, then argmax
                    pred_flat = predictions[:, 0, :, :].reshape(predictions.shape[0], -1)
                    return np.argmax(pred_flat, axis=1)
                elif len(predictions.shape) == 3:  # (samples, timesteps, classes)
                    # Take the first timestep
                    return np.argmax(predictions[:, 0, :], axis=-1)
                else:
                    return np.argmax(predictions, axis=-1)
            else:  # Binary
                if len(predictions.shape) == 3:  # (samples, timesteps, classes)
                    # Take the first timestep
                    return np.argmax(predictions[:, 0, :], axis=-1)
                else:
                    return np.argmax(predictions, axis=-1)

        def predict_proba(self, X):
            # Ensure X is a numpy array
            if not isinstance(X, np.ndarray):
                X = np.array(X)

            # Reshape back to original sequence format
            X_reshaped = X.reshape(-1, self.original_shape[1], self.original_shape[2])
            predictions = self.model.predict(X_reshaped, verbose=0)

            # Ensure predictions is a numpy array
            if not isinstance(predictions, np.ndarray):
                predictions = np.array(predictions)

            # Return probabilities for the first timestep
            if self.model_version == 0:  # Multiclass
                if len(predictions.shape) == 4:  # (samples, timesteps, label_types, subclasses)
                    # Take the first timestep and flatten
                    return predictions[:, 0, :, :].reshape(predictions.shape[0], -1)
                elif len(predictions.shape) == 3:  # (samples, timesteps, classes)
                    return predictions[:, 0, :]
                else:
                    return predictions
            else:  # Binary
                if len(predictions.shape) == 3:  # (samples, timesteps, classes)
                    return predictions[:, 0, :]
                else:
                    return predictions

    # Create model wrapper
    model_wrapper = ModelWrapper(model, x_train.shape, model_version)

    try:
        # Initialize Trustee
        trustee = ClassificationTrustee(expert=model_wrapper)

        # Fit Trustee
        log.info(f"Fitting Trustee with {num_iter} iterations...")
        trustee.fit(x_train_flat, y_train_flat,
                    num_iter=num_iter,
                    num_stability_iter=num_stability_iter,
                    samples_size=samples_size,
                    verbose=True)

        # Generate explanation
        log.info("Generating decision tree explanation...")
        dt, pruned_dt, agreement, reward = trustee.explain()

        # Get predictions from both models
        log.info(f"Getting predictions from original model for {len(x_test_flat)} samples...")
        y_pred_original = model_wrapper.predict(x_test_flat)

        log.info(f"Getting predictions from decision tree for {len(x_test_flat)} samples...")
        dt_y_pred = dt.predict(x_test_flat)

        # Ensure both predictions have the same shape
        log.info(
            f"Original model predictions shape: {y_pred_original.shape if hasattr(y_pred_original, 'shape') else len(y_pred_original)}")
        log.info(
            f"Decision tree predictions shape: {dt_y_pred.shape if hasattr(dt_y_pred, 'shape') else len(dt_y_pred)}")
        log.info(f"Test labels shape: {y_test_flat.shape if hasattr(y_test_flat, 'shape') else len(y_test_flat)}")

        # Convert to numpy arrays if needed and ensure all arrays are 1D and of the same length
        if not isinstance(y_pred_original, np.ndarray):
            y_pred_original = np.array(y_pred_original)
        if not isinstance(dt_y_pred, np.ndarray):
            dt_y_pred = np.array(dt_y_pred)
        if not isinstance(y_test_flat, np.ndarray):
            y_test_flat = np.array(y_test_flat)

        if hasattr(y_pred_original, 'flatten'):
            y_pred_original = y_pred_original.flatten()
        if hasattr(dt_y_pred, 'flatten'):
            dt_y_pred = dt_y_pred.flatten()
        if hasattr(y_test_flat, 'flatten'):
            y_test_flat = y_test_flat.flatten()

        # Calculate fidelity metrics
        from sklearn.metrics import classification_report

        fidelity_report = classification_report(y_pred_original, dt_y_pred, output_dict=True)
        explanation_report = classification_report(y_test_flat, dt_y_pred, output_dict=True)

        log.info("Trustee explanation generation completed successfully.")

        return {
            "decision_tree": dt,
            "pruned_decision_tree": pruned_dt,
            "agreement": float(agreement),
            "reward": float(reward),
            "fidelity_report": fidelity_report,
            "explanation_report": explanation_report,
            "trustee_predictions": dt_y_pred.tolist(),
            "original_predictions": y_pred_original.tolist(),
            "test_labels": y_test_flat.tolist(),
            "feature_names": flattened_feature_names
        }

    except Exception as e:
        log.exception(f"Error during Trustee explanation generation.")
        return {}


def save_trustee_explanation(explanation_result: dict, base_path: str):
    """
    Save Trustee explanation results to files.

    Args:
        explanation_result: Dictionary containing explanation results
        base_path: Base path for saving files
    """
    if not explanation_result:
        log.warning("No Trustee explanation results to save.")
        return

    log.info("Saving Trustee explanation results...")

    # Save decision tree as text
    if "decision_tree" in explanation_result:
        try:
            from sklearn.tree import export_text
            feature_names = explanation_result.get("feature_names", None)
            if feature_names:
                tree_rules = export_text(explanation_result["decision_tree"], feature_names=feature_names)
                log.info(f"Exported decision tree with {len(feature_names)} feature names")
            else:
                tree_rules = export_text(explanation_result["decision_tree"])
                log.info("Exported decision tree without feature names")

            with open(base_path + '/trustee_decision_tree.txt', 'w') as f:
                f.write(tree_rules)
        except Exception as e:
            log.warning(f"Could not save decision tree as text: {str(e)}")

    # Try to save decision tree as graphical representation
    if "decision_tree" in explanation_result:
        try:
            from sklearn.tree import export_graphviz
            feature_names = explanation_result.get("feature_names", None)

            dot_data = export_graphviz(
                explanation_result["decision_tree"],
                feature_names=feature_names,
                filled=True,
                rounded=True,
                special_characters=True,
                max_depth=10  # Limit depth for readability
            )

            with open(base_path + '/trustee_decision_tree.dot', 'w') as f:
                f.write(dot_data)

            log.info("Decision tree saved as DOT file (can be converted to PNG/PDF with Graphviz)")
        except Exception as e:
            log.debug(f"Could not save decision tree as DOT file: {str(e)}")

    # Save explanation metrics and results
    explanation_summary = {
        "agreement": explanation_result.get("agreement", 0.0),
        "reward": explanation_result.get("reward", 0.0),
        "fidelity_report": explanation_result.get("fidelity_report", {}),
        "explanation_report": explanation_result.get("explanation_report", {}),
        "feature_names": explanation_result.get("feature_names", []),
        "summary": {
            "fidelity_accuracy": explanation_result.get("fidelity_report", {}).get("accuracy", 0.0),
            "explanation_accuracy": explanation_result.get("explanation_report", {}).get("accuracy", 0.0),
            "num_test_samples": len(explanation_result.get("test_labels", [])),
            "num_features": len(explanation_result.get("feature_names", []))
        }
    }

    with open(base_path + '/trustee_explanation.json', 'w') as f:
        json.dump(explanation_summary, f, indent=2)

    # Save detailed predictions for analysis
    detailed_results = {
        "trustee_predictions": explanation_result.get("trustee_predictions", []),
        "original_predictions": explanation_result.get("original_predictions", []),
        "test_labels": explanation_result.get("test_labels", [])
    }

    with open(base_path + '/trustee_predictions.json', 'w') as f:
        json.dump(detailed_results, f, indent=2)

    log.info(f"Trustee explanation results saved to {base_path}")
