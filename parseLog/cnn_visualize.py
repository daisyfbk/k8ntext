import numpy as np
from matplotlib import pyplot as plt

from cnn_options import OUT_FOLDER


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
    plt.title('Average Model Loss with Standard Deviation')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.savefig(OUT_FOLDER + '/avg_loss.png')

    plt.legend()
    plt.title('Model loss')
    plt.savefig(OUT_FOLDER + '/loss.png')


def plot_accuracy(accuracies: list[dict]) -> None:
    # Plot all accuracies as a histogram
    plt.clf()

    num_attempts = len(accuracies)
    bar_width = 0.8 / num_attempts

    plt.figure(figsize=(25, 6))
    plt.yscale('log')
    plt.xticks(rotation=90)
    plt.ylim(0.00001, 1)

    plt.subplots_adjust(bottom=0.3)

    for attempt_idx, attempt_acc in enumerate(accuracies):
        items = sorted(attempt_acc.items(), key=lambda x: x[0])
        labels, values = zip(*items)

        positions = [x + (attempt_idx * bar_width) for x in range(len(attempt_acc))]
        plt.bar(positions, values, width=bar_width, label=f'Attempt {attempt_idx + 1}', align='center')

        if attempt_idx == 0:
            plt.xticks([x + bar_width * (num_attempts / 2 - 0.5) for x in range(len(attempt_acc))], labels)

    plt.title('Class accuracies')
    plt.legend()
    plt.savefig(OUT_FOLDER + '/accuracy.png')
