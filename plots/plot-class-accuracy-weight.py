# ../models/1_paper_tests/1_window_size/20240919_063020.311060__mfranzil-gpu/metrics.json
# [{"core_metrics": {"accuracy": 0.9997721106890939, "precision": 0.9900970258015107, "recall": 0.9954811711555006, "f1": 0.9881803106793476}, "majority_accuracy": null, "per_class_metrics": {"accuracy": {"119232": 1.0, "102480": 1.0, "4176": 1.0, "65984": 0.999581764951903, "75200": 1.0, "147536": 1.0, "38080": 1.0, "90256": 1.0, "2727984": 1.0, "65952": 1.0, "180624": 0.9984326018808778, "86416": 1.0, "4400": 1.0, "12752": 1.0, "65936": 1.0, "86432": 1.0, "3695024": 1.0, "61632": 1.0, "41376": 1.0, "172112": 1.0, "17808": 1.0, "94640": 1.0, "82320": 1.0, "74128": 1.0, "98384": 1.0, "12688": 1.0, "3276944": 1.0, "4496": 

import json

palette = {
    'blue': '#3070c8',
    'cyan': '#66CCEE',
    'green': '#228833',
    'yellow': '#CCBB44',
    'orange': '#EE7733',
    'red': '#EE6677',
    'purple': '#AA3377',
    'grey': '#BBBBBB'
}

with open('../models/1_paper_tests/1_window_size/20240919_063020.311060__mfranzil-gpu/metrics.json') as f:
    j = json.load(f)
    per_class_metrics = []
    for attempt in j:
        per_class_metrics.append(attempt['per_class_metrics'])

condensed = {}
for attempt in per_class_metrics:
    if set(attempt['accuracy'].keys()) != set(attempt['weight'].keys()):
        raise ValueError('Keys do not match')
    keys = attempt['accuracy'].keys()
    for key in keys:
        if key not in condensed:
            condensed[key] = []
        condensed[key].append({
            "accuracy": attempt['accuracy'][key],
            "weight": attempt['weight'][key],
        })

for key in condensed:
    merged_obj = {
        "accuracy": 0,
        "weight": 0,
    }

    for attempt in condensed[key]:
        merged_obj['accuracy'] += attempt['accuracy'] * attempt['weight']
        merged_obj['weight'] += attempt['weight']

    merged_obj['accuracy'] /= merged_obj['weight']
    merged_obj['weight'] /= len(condensed[key])
    condensed[key] = merged_obj

# sort by weight
condensed = {k: v for k, v in sorted(condensed.items(), key=lambda item: item[1]['accuracy']  * item[1]['weight']                                     , reverse=True)}
# print top 10 and bottom 10
top_10 = list(condensed.keys())[:10]
bottom_10 = list(condensed.keys())[-10:]
print('Top 10')
for key in top_10:
    print(key, condensed[key])
print('Bottom 10')
for key in bottom_10:
    print(key, condensed[key])

# sort by accuracy
condensed = {k: v for k, v in sorted(condensed.items(), key=lambda item: item[1]['accuracy'], reverse=True)}

del condensed['-1']
# plot weight against accuracy
import matplotlib.pyplot as plt

plt.figure(figsize=(7, 4), dpi=300)
plt.rcParams.update({'font.size': 12})

plt.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.5)

x = [condensed[key]['weight'] for key in condensed]
y = [condensed[key]['accuracy'] for key in condensed]

for i in range(len(x)):
    if x[i] > 3 * 10**3 or y[i] < 0.96:
        plt.scatter(x[i], y[i], s=15, c=palette["red"], marker='o', label='Accuracy of the class' if i == 0 else "")
    else:
        plt.scatter(x[i], y[i], s=15, c=palette["blue"], marker='o', label='Accuracy of the class' if i == 0 else "")

plt.xscale('log')
plt.xlim(1, 1e5)

plt.xlabel('Weight (# of samples)')
plt.ylabel('Accuracy')
plt.suptitle('Accuracy of each class against its weight')
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig('class-accuracy.png')

# Generate TikZ code
with open("class-accuracy.tex", "w") as f:
    f.write(r"""% Class accuracy TikZ plot
\documentclass{standalone}
\usepackage{tikz}
\usepackage{pgfplots}
\usepackage{xcolor}
\pgfplotsset{compat=1.18}

% Define exact colors as requested
\definecolor{plotblue}{HTML}{3070c8}
\definecolor{plotred}{HTML}{EE6677}

\begin{document}
\begin{tikzpicture}
\begin{axis}[
    width=\linewidth,
    height=4cm,
    grid=major,
    grid style={dashed, gray!30},
    xlabel={Weight (\# of samples)},
    ylabel={Accuracy},
    title={Accuracy of each class against its weight},
    xmode=log,
    log basis x=10,
    xmin=1, xmax=1e5,
    ymin=0.95, ymax=1.005,
    legend pos=south west,
    legend style={font=\footnotesize}
]

% High weight or low accuracy points (red)
\addplot[only marks, mark=*, mark size=1.5pt, color=plotred] coordinates {
""")
    
    # Add red points
    for i in range(len(x)):
        if x[i] > 3 * 10**3 or y[i] < 0.96:
            f.write(f"    ({x[i]}, {y[i]})\n")
    
    f.write(r"""
};
% \addlegendentry{Outliers}

% Regular points (blue)
\addplot[only marks, mark=*, mark size=1.5pt, color=plotblue] coordinates {
""")
    
    # Add blue points
    for i in range(len(x)):
        if not (x[i] > 3 * 10**3 or y[i] < 0.96):
            f.write(f"    ({x[i]}, {y[i]})\n")
    
    f.write(r"""
};
% \addlegendentry{Regular classes}

\end{axis}
\end{tikzpicture}
\end{document}
""")