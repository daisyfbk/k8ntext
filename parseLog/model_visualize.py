import numpy as np
from matplotlib import pyplot as plt
import logging as log

from parameters import OUT_FOLDER, CONFUSION_MATRIX_TOP_PERCENTAGE
import matplotlib.colors as mcolors


def darken_color(color, factor=0.7):
    """Darken a given color by a specified factor."""
    # Convert color to RGB
    rgb = mcolors.to_rgb(color)
    # Darken the RGB values
    darkened_rgb = [max(x * factor, 0) for x in rgb]
    return mcolors.to_hex(darkened_rgb)


def plot_loss(losses: list) -> None:
    # Find the maximum length of loss histories
    max_length = max(max(len(loss.history['loss']), len(loss.history['val_loss'])) for loss in losses)

    # Initialize lists to store adjusted loss histories
    all_losses = []
    all_val_losses = []

    # Adjust all loss histories to have the same maximum length
    for loss in losses:
        adjusted_loss = np.full(max_length, np.nan)
        adjusted_val_loss = np.full(max_length, np.nan)

        adjusted_loss[:len(loss.history['loss'])] = loss.history['loss']
        adjusted_val_loss[:len(loss.history['val_loss'])] = loss.history['val_loss']

        all_losses.append(adjusted_loss)
        all_val_losses.append(adjusted_val_loss)

    # Convert lists to NumPy arrays
    all_losses = np.array(all_losses)
    all_val_losses = np.array(all_val_losses)

    # Calculate mean and standard deviation safely
    mean_loss = np.nanmean(all_losses, axis=0)
    std_loss = np.nanstd(all_losses, axis=0)
    mean_val_loss = np.nanmean(all_val_losses, axis=0)
    std_val_loss = np.nanstd(all_val_losses, axis=0)

    epochs = range(1, max_length + 1)

    plt.figure(figsize=(10, 6))

    plt.plot(epochs, mean_loss, label='Average Training Loss')
    plt.fill_between(epochs, mean_loss - std_loss, mean_loss + std_loss, alpha=0.3)
    plt.plot(epochs, mean_val_loss, label='Average Validation Loss')
    plt.fill_between(epochs, mean_val_loss - std_val_loss, mean_val_loss + std_val_loss, alpha=0.3)

    # Put a tick where the last epoch is for each attempt
    for i in range(len(losses)):
        plt.axvline(x=len(losses[i].history['loss']), color='gray', linestyle='--', alpha=0.5)

    plt.title('Average Model Loss with Standard Deviation')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.yscale('log')
    plt.legend()
    plt.savefig(OUT_FOLDER + '/loss.png')

    # New plot for metrics
    available_metrics = set()
    for loss in losses:
        available_metrics.update(loss.history.keys())
    available_metrics = list(available_metrics - {'loss', 'val_loss'})
    if 'learning_rate' in available_metrics:
        available_metrics.remove('learning_rate')
    if available_metrics == []:
        return
    if len(available_metrics) != 2 * len([metric for metric in available_metrics if metric.startswith('val_')]):
        log.error('WARNING: Not all metrics have validation counterparts, skipping plotting metrics')
        return

    metrics = {metric: [] for metric in available_metrics}    

    # Adjust all loss histories to have the same maximum length
    for loss in losses:
        for metric in available_metrics:
            adjusted_metric = np.full(max_length, np.nan)

            adjusted_metric[:len(loss.history[metric])] = loss.history[metric]

            metrics[metric].append(adjusted_metric)

    # Convert lists to NumPy arrays
    metrics = {metric: np.array(values) for metric, values in metrics.items()}

    # Calculate mean and standard deviation safely
    mean_metrics = {metric: np.nanmean(values, axis=0) for metric, values in metrics.items()}
    std_metrics = {metric: np.nanstd(values, axis=0) for metric, values in metrics.items()}

    epochs = range(1, max_length + 1)

    plt.figure(figsize=(10, 6))
    
    colormap = plt.get_cmap('tab10')
    metric_colors = {metric: colormap(i) for i, metric in enumerate(available_metrics) if not metric.startswith('val_')}

    for metric in available_metrics:
        if metric.startswith('val_'):
            continue
        training_color = metric_colors[metric]
        validation_color = darken_color(training_color, 0.7)

        # Plot training metric
        plt.plot(epochs, mean_metrics[metric], label=f'Average Training {metric}', color=training_color)
        plt.fill_between(epochs, mean_metrics[metric] - std_metrics[metric], mean_metrics[metric] + std_metrics[metric],
                        color=training_color, alpha=0.3)

        # Plot validation metric with slightly different style or alpha
        plt.plot(epochs, mean_metrics[f'val_{metric}'], label=f'Average Validation {metric}', color=validation_color, linestyle='--')
        plt.fill_between(epochs, mean_metrics[f'val_{metric}'] - std_metrics[f'val_{metric}'],
                        mean_metrics[f'val_{metric}'] + std_metrics[f'val_{metric}'], color=validation_color, alpha=0.2)

        
    # Put a tick where the last epoch is for each attempt
    for i in range(len(losses)):
        plt.axvline(x=len(losses[i].history['loss']), color='gray', linestyle='--', alpha=0.5)

    plt.title('Average Model Metrics with Standard Deviation')
    plt.xlabel('Epoch')
    plt.ylabel('Value')
    plt.legend()
    plt.yscale('log')
    plt.savefig(OUT_FOLDER + '/metrics.png')


def plot_metrics(metrics: list[dict]) -> None:
    plt.clf()

    if len(metrics) == 1:
        plot_confusion_matrix(metrics[0])
    else:
        # Plot core metrics: accuracy, precision, recall, f1
        available_metrics = ['accuracy', 'precision', 'recall', 'f1']
        data = {}
        for metric_name in available_metrics:
            values = [metric['core_metrics'][metric_name] for metric in metrics]
            mean = np.mean(values)
            std = np.std(values)
            data[metric_name] = (mean, std)

        # Plot metrics for scalar values
        plt.figure(figsize=(10, 6))
        x_positions = np.arange(len(available_metrics))
        means = [data[metric_name][0] for metric_name in available_metrics]
        stds = [data[metric_name][1] for metric_name in available_metrics]
        plt.bar(x_positions, means, yerr=stds, align='center', alpha=0.7, ecolor='black', capsize=10)
        plt.xticks(x_positions, available_metrics)
        plt.ylim(min(0.8, min(means) - 0.1), max(1, max(means) + 0.1))

        plt.title('Core Metrics')
        plt.xlabel('Metric')
        plt.ylabel('Value')
        plt.savefig(OUT_FOLDER + '/core_metrics.png')


# def plot_boxplot(metrics: list[dict], metric_name: str) -> None:
#     # Step 1: Collect data for each class across all attempts
#     class_accuracies = {}
#     for attempt_acc in metrics:
#         attempt_acc = attempt_acc['per_class_metrics']
#         for class_label, acc in attempt_acc.items():
#             class_label = int(class_label)
#             if class_label not in class_accuracies:
#                 class_accuracies[class_label] = []
#             class_accuracies[class_label].append(acc)
# 
#     class_descriptions = {}
#     from label_proposer import decode_label
#     for class_label in class_accuracies.keys():
#         class_descriptions[class_label] = decode_label(class_label, as_string=True) + f' ({class_label})'
#             
#     # Prepare data for boxplot
#     sorted_labels = sorted(class_accuracies.keys(), key=lambda x: -int(x))
#     data = [class_accuracies[label] for label in sorted_labels]
# 
#     # Substitute class labels with descriptions
#     sorted_labels = [class_descriptions[label] for label in sorted_labels]
# 
#     # Step 2: Create a boxplot
#     plt.figure(figsize=(20, 25))
#     plt.subplots_adjust(left=0.4)
#     box = plt.boxplot(data, vert=False, patch_artist=True, labels=sorted_labels)
# 
#     plt.title('Class Accuracies')
#     plt.xlabel('Accuracy')
# 
#     plt.legend()
#     plt.savefig(OUT_FOLDER + '/' + metric_name + '_boxplot.png')


def plot_confusion_matrix(metrics: dict) -> None:
    # Step 3: print a confusion matrix for the top 10% of classes by amount of data
    class_accuracies = metrics['per_class_metrics']["accuracy"]

    class_accuracy_keys = list(class_accuracies.keys())
    class_accuracy_keys.sort(key=lambda x: -metrics['per_class_metrics']['weight'][x])
    if CONFUSION_MATRIX_TOP_PERCENTAGE < 1:
        top_classes = class_accuracy_keys[:int(len(class_accuracies) * CONFUSION_MATRIX_TOP_PERCENTAGE)]
    else:
        top_classes = class_accuracy_keys

    confusion_matrix = np.zeros((len(top_classes), len(top_classes)))

    for i, class_i in enumerate(top_classes):
        for j, class_j in enumerate(top_classes):
            confusion_matrix[i, j] = metrics['confusion_matrix'].get(class_i, {int(class_j): 0}).get(int(class_j), 0)

    plt.figure(figsize=(len(top_classes) // 2, len(top_classes) // 2))
    plt.imshow(confusion_matrix, interpolation='nearest', cmap='Blues')
    plt.title('Confusion Matrix')
    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.xticks(range(len(top_classes)), [class_label for class_label in top_classes], rotation=90)
    plt.yticks(range(len(top_classes)), [class_label for class_label in top_classes])
    # Put text on each cell
    for i in range(len(top_classes)):
        for j in range(len(top_classes)):
            color = 'white' if confusion_matrix[i, j] > confusion_matrix.max() / 2 else 'black'
            plt.text(j, i, f"{confusion_matrix[i, j]:.2f}", ha='center', va='center', color=color)

    plt.colorbar()
    plt.savefig(OUT_FOLDER + '/confusion_matrix.png')
