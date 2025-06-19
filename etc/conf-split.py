import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

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

# luminance-based palette
import matplotlib.colors as mcolors
cmap = mcolors.LinearSegmentedColormap.from_list("accuracy_cmap", 
                                                     [
                                                         (0.0, "#FFFFFF"),
                                                         (1.0, "#3070c8")
                                                     ], N=100)
                                                     
                                                     
                                                #     ["#EE6677", "#EE6677", "#FFCC88", "#3070c8"], N=100)
plt.rcParams.update({'font.size': 12})
# Create heatmap
plt.figure(figsize=(10, 4))
ax = sns.heatmap(f1_matrix, annot=True, fmt=".4f", cmap=cmap, 
                 xticklabels=tr_va_values, yticklabels=tr_te_values,
                 vmin=0.93, vmax=0.99)  # Setting color scale to highlight differences

plt.title("F1 Score by Train/Test and Train/Validation Splits")
plt.xlabel("Train/Validation Split")
plt.ylabel("Train/Test Split")
plt.tight_layout()
plt.savefig("f1_score_heatmap.png", dpi=300)