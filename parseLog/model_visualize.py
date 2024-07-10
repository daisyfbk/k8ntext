import json
import logging as log
import os

import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import numpy as np
from matplotlib import pyplot as plt

import parameters as pm


def darken_color(color, factor=0.7):
    """Darken a given color by a specified factor."""
    # Convert color to RGB
    rgb = mcolors.to_rgb(color)
    # Darken the RGB values
    darkened_rgb = [max(x * factor, 0) for x in rgb]
    return mcolors.to_hex(darkened_rgb)


def plot_loss(losses: list) -> None:
    # Find the maximum length of loss histories
    for loss in losses:
        keys = list(loss.keys())
        for key in keys:
            if key[-2] == "_":
                loss[key[:-2]] = loss.pop(key)

    max_length = max(max(len(loss['loss']), len(loss['val_loss'])) for loss in losses)

    # Initialize lists to store adjusted loss histories
    all_losses = []
    all_val_losses = []

    # Adjust all loss histories to have the same maximum length
    for loss in losses:
        adjusted_loss = np.full(max_length, np.nan)
        adjusted_val_loss = np.full(max_length, np.nan)

        adjusted_loss[:len(loss['loss'])] = loss['loss']
        adjusted_val_loss[:len(loss['val_loss'])] = loss['val_loss']

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
        plt.axvline(x=len(losses[i]['loss']), color='gray', linestyle='--', alpha=0.5)

    plt.title('Average Model Loss with Standard Deviation')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.yscale('log')
    plt.legend()
    plt.savefig(pm.OUT_FOLDER + '/loss.png')
    plt.close()

    # New plot for metrics
    available_metrics = set()
    for loss in losses:
        available_metrics.update(loss.keys())
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
            if metric[-2] == "_":
                metric = metric[:-2]
            adjusted_metric = np.full(max_length, np.nan)

            adjusted_metric[:len(loss[metric])] = loss[metric]

            metrics[metric].append(adjusted_metric)

    # Convert lists to NumPy arrays
    metrics = {metric: np.array(values) for metric, values in metrics.items()}

    # Calculate mean and standard deviation safely
    mean_metrics = {metric: np.nanmean(values, axis=0) for metric, values in metrics.items()}
    std_metrics = {metric: np.nanstd(values, axis=0) for metric, values in metrics.items()}

    epochs = range(1, max_length + 1)

    plt.clf()
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
        plt.plot(epochs, mean_metrics[f'val_{metric}'], label=f'Average Validation {metric}', color=validation_color,
                 linestyle='--')
        plt.fill_between(epochs, mean_metrics[f'val_{metric}'] - std_metrics[f'val_{metric}'],
                         mean_metrics[f'val_{metric}'] + std_metrics[f'val_{metric}'], color=validation_color,
                         alpha=0.2)

    # Put a tick where the last epoch is for each attempt
    for i in range(len(losses)):
        plt.axvline(x=len(losses[i]['loss']), color='gray', linestyle='--', alpha=0.5)

    plt.title('Average Model Metrics with Standard Deviation')
    plt.xlabel('Epoch')
    plt.ylabel('Value')
    plt.yscale('log')
    plt.legend()
    plt.savefig(pm.OUT_FOLDER + '/metrics.png')
    plt.close()


def plot_metrics(metrics: list[dict]) -> None:
    plt.clf()

    if len(metrics) == 1:
        plot_confusion_matrix(metrics[0])
    else:
        # Plot core metrics: accuracy, precision, recall, f1
        available_metrics = ['accuracy', 'precision', 'recall', 'f1']
        data = {metric_name: [] for metric_name in available_metrics}
        for metric in metrics:
            for metric_name in available_metrics:
                data[metric_name].append(metric['core_metrics'][metric_name])

        # Prepare data for box plot
        data_for_plot = [data[metric_name] for metric_name in available_metrics]

        # Plot metrics as box plots
        plt.figure(figsize=(10, 6))
        plt.boxplot(data_for_plot, tick_labels=available_metrics, notch=True, patch_artist=True)

        plt.title('Core Metrics - Box and Whisker Plot')
        plt.xlabel('Metric')
        plt.ylabel('Value')
        plt.savefig(pm.OUT_FOLDER + '/core_metrics.png')
        plt.close()


def plot_confusion_matrix(metrics: dict) -> None:
    # Step 3: print a confusion matrix for the top 10% of classes by amount of data
    class_accuracies = metrics['per_class_metrics']["accuracy"]

    class_accuracy_keys = list(class_accuracies.keys())
    class_accuracy_keys.sort(key=lambda x: -metrics['per_class_metrics']['weight'][x])
    if pm.CONFUSION_MATRIX_TOP_PERCENTAGE < 1:
        top_classes = class_accuracy_keys[:int(len(class_accuracies) * pm.CONFUSION_MATRIX_TOP_PERCENTAGE)]
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
    plt.savefig(pm.OUT_FOLDER + '/confusion_matrix.png')
    plt.close()


def statistical_loss_to_means(folder: str, required_labels: list[str]) -> tuple[list[dict], list[str]]:
    subfolders = [i for i in os.listdir(folder) if os.path.isdir(os.path.join(folder, i))]
    ret = []

    data = {}
    labels = []
    label_type = str if len(required_labels) > 1 else int

    for _, subfolder in enumerate(subfolders):
        with open(os.path.join(folder, subfolder, 'main.log')) as f:
            label = []
            for line in f:
                for required_label in required_labels:
                    if required_label in line:
                        value = line.split(required_label + ': ')[1].split(',')[0]
                        if label_type == int:
                            value = int(value)
                        label.append(value)

            if len(label) == len(required_labels):
                if label_type == str:
                    label = ", ".join(label)
                else:
                    label = label[0]
                labels.append(label)

        # print(f'Processing {subfolder} with window length {window_length}')
        with open(os.path.join(folder, subfolder, 'loss.json')) as f:
            history = json.load(f)
            for b, run in enumerate(history):
                o = {}
                for k, v in run.items():
                    if k[-2] == "_":
                        # some metrics are saved as recall_1, recall_2, etc.
                        k = k[:-2]
                    o[k] = v
                history[b] = o
            data[label] = history

    reordered_data = {}
    argsorted = np.argsort(labels)
    new_labels = []
    for i in range(len(labels)):
        reordered_data[i] = data[labels[argsorted[i]]]
        new_labels.append(labels[argsorted[i]])

    assert len(labels) == len(subfolders)

    for i, history in reordered_data.items():
        local_object = {}
        for _, metric in enumerate(pm.COLLECTED_METRICS):
            if metric[-2] == "_":
                metric = metric[:-2]
            values = [history[k][metric] for k in range(len(history))]
            local_labels = [len(values[i]) for i in range(len(values))]
            local_means = []
            for m in range(max(local_labels)):
                m = np.mean([values[i][m] for i in range(len(values)) if m < local_labels[i]])
                local_means.append(m)

            local_object[metric] = local_means

        ret.append(local_object)

    return ret, new_labels


def plot_multiple_runs(history, labels, observed_metrics):
    for metric_type in pm.COLLECTED_METRICS:
        y = [history[i][metric_type] for i in range(len(history))]

        plt.clf()
        plt.figure(figsize=(15, 15), dpi=300)

        colormap = plt.get_cmap('viridis')
        num_sequences = len(y)

        legend_handles = []
        for i, sequence in enumerate(y):
            # smooth the sequence
            sequence = np.convolve(sequence, np.ones(5) / 5, mode='valid')

            color_intensity = (i + 1) / num_sequences
            color = colormap(1 - color_intensity)
            plt.plot(sequence, color=color)  # Darker for later attempts

            ypos = float(sequence[-1])
            xpos = float(len(sequence) - 1)
            plt.scatter(xpos, ypos, color=color)
            plt.text(xpos + 0.05, ypos, labels[i], color=color)

            legend_handle = mlines.Line2D([], [], color=color, label=labels[i])
            legend_handles.append(legend_handle)

        plt.legend(handles=legend_handles, loc='center left', bbox_to_anchor=(1, 0.5))
        # plt.yscale('log')
        plt.xlabel('Epoch')
        plt.ylabel(metric_type)
        plt.title(f'Changes in {metric_type.upper()} as {observed_metrics} change, averaged over all runs')
        plt.ylim(*pm.METRICS_YRANGES[metric_type](y))
        # plt.tight_layout()
        plt.savefig(pm.OUT_FOLDER + metric_type + '.png')
        plt.close()
