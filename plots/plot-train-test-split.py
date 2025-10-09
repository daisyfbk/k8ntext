import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Extract data from the table
data = [
    {"Tr/Te": 0.1, "Tr/Va": 0.1, "F1": 0.9839},
    {"Tr/Te": 0.1, "Tr/Va": 0.2, "F1": 0.9824},
    {"Tr/Te": 0.1, "Tr/Va": 0.4, "F1": 0.9806},
    {"Tr/Te": 0.1, "Tr/Va": 0.3, "F1": 0.9800},
    {"Tr/Te": 0.1, "Tr/Va": 0.5, "F1": 0.9752},
    {"Tr/Te": 0.1, "Tr/Va": 0.6, "F1": 0.9722},
    {"Tr/Te": 0.1, "Tr/Va": 0.7, "F1": 0.9647},
    {"Tr/Te": 0.1, "Tr/Va": 0.8, "F1": 0.9538},
    {"Tr/Te": 0.2, "Tr/Va": 0.1, "F1": 0.9753},
    {"Tr/Te": 0.2, "Tr/Va": 0.2, "F1": 0.9696},
    {"Tr/Te": 0.2, "Tr/Va": 0.3, "F1": 0.9690},
    {"Tr/Te": 0.3, "Tr/Va": 0.1, "F1": 0.9597},
    {"Tr/Te": 0.3, "Tr/Va": 0.2, "F1": 0.9571},
    {"Tr/Te": 0.3, "Tr/Va": 0.3, "F1": 0.9332},
]

# Create a matrix for the F1 scores
tr_te_values = sorted(set(d["Tr/Te"] for d in data))
tr_va_values = sorted(set(d["Tr/Va"] for d in data))

# Initialize matrix with NaN values
f1_matrix = np.full((len(tr_te_values), len(tr_va_values)), np.nan)

# Fill in the matrix
for d in data:
    tr_te_idx = tr_te_values.index(d["Tr/Te"])
    tr_va_idx = tr_va_values.index(d["Tr/Va"])
    f1_matrix[tr_te_idx, tr_va_idx] = d["F1"]

# Create a custom colormap (blue to white)
cmap = mcolors.LinearSegmentedColormap.from_list("accuracy_cmap", 
                                               [(0.0, "#FFFFFF"),
                                                (1.0, "#3070c8")], N=100)

# Set up the plot
plt.rcParams.update({'font.size': 12})
fig, ax = plt.subplots(figsize=(10, 4))

# Create heatmap using pcolormesh
mesh = ax.pcolormesh(f1_matrix, cmap=cmap, vmin=0.93, vmax=0.99)

# Add colorbar
cbar = plt.colorbar(mesh)
cbar.set_label('F1 Score')

# Set ticks and labels
ax.set_xticks(np.arange(len(tr_va_values)) + 0.5)
ax.set_yticks(np.arange(len(tr_te_values)) + 0.5)
ax.set_xticklabels(tr_va_values)
ax.set_yticklabels(tr_te_values)

# Adjust tick positions
ax.set_xticks(np.arange(len(tr_va_values) + 1), minor=True)
ax.set_yticks(np.arange(len(tr_te_values) + 1), minor=True)
ax.grid(which="minor", color="w", linestyle='-', linewidth=2)
ax.tick_params(which="minor", bottom=False, left=False)

# Add text annotations with F1 values
for i in range(len(tr_te_values)):
    for j in range(len(tr_va_values)):
        if not np.isnan(f1_matrix[i, j]):
            ax.text(j + 0.5, i + 0.5, f"{f1_matrix[i, j]:.4f}",
                    ha="center", va="center", 
                    color="black" if f1_matrix[i, j] < 0.96 else "white")

# Set title and labels
plt.title("F1 Score by Train/Test and Train/Validation Splits")
plt.xlabel("Train/Validation Split")
plt.ylabel("Train/Test Split")

# Invert y-axis to match seaborn's heatmap orientation
plt.gca().invert_yaxis()

# Adjust layout
plt.tight_layout()
plt.savefig("f1_score_heatmap.png", dpi=300)

import matplot2tikz
matplot2tikz.save("f1_score_heatmap.tex", axis_width='12cm', axis_height='6cm')