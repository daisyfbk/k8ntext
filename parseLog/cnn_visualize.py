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
    plt.savefig(OUT_FOLDER + '/loss.png')


def plot_accuracy(accuracies: list[dict]) -> None:
    plt.clf()

    # Step 1: Collect data for each class across all attempts
    class_accuracies = {}
    for attempt_acc in accuracies:
        for class_label, acc in attempt_acc.items():
            class_label = int(class_label)
            if class_label not in class_accuracies:
                class_accuracies[class_label] = []
            class_accuracies[class_label].append(acc)

    class_descriptions = {}
    from label_proposer import decode_label
    for class_label in class_accuracies.keys():
        class_descriptions[class_label] = decode_label(class_label, as_string=True)
            
    # Prepare data for boxplot
    sorted_labels = sorted(class_accuracies.keys(), key=lambda x: -int(x))
    data = [class_accuracies[label] for label in sorted_labels]

    # Substitute class labels with descriptions
    sorted_labels = [class_descriptions[label] for label in sorted_labels]

    # Step 2: Create a boxplot
    plt.figure(figsize=(20, 25))
    plt.subplots_adjust(left=0.4)
    box = plt.boxplot(data, vert=False, patch_artist=True, labels=sorted_labels)

    plt.title('Class Accuracies')
    plt.xlabel('Accuracy')

    plt.legend()
    plt.savefig(OUT_FOLDER + '/accuracy.png')
