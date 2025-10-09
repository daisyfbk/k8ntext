import pandas as pd
import matplotlib.pyplot as plt
import json
import argparse

argparser = argparse.ArgumentParser()
argparser.add_argument('--file', '-f', type=str, required=True, nargs='+')
args = argparser.parse_args()

if len(args.file) == 1:
    file = args.file[0]
    data = json.loads(open(file).read())
else:
    data = []
    for file in args.file:
        print("Adding file", file)
        data += json.loads(open(file).read())

df = pd.DataFrame(data).sort_values(by='loss')

fig, ax = plt.subplots()
labels = list(df['mode'].unique())
cmap = plt.get_cmap('tab20')
colors = {label: plt.cm.tab20(i) for i, label in enumerate(labels)}
for mode, color in colors.items():
    mode_df = df[df['mode'] == mode]
    ax.scatter(mode_df['loss'], mode_df['error_statistics'], color=color, label=mode)
    ax.axhline(mode_df['error_statistics'].mean(), color=color, linestyle='--')

# Adding labels and title for clarity
ax.set_xlabel('Value of loss function at the end of training')
ax.set_ylabel('Number of Correct Predictions')
ax.set_title('Scatter Plot of loss vs Actual Number of Correct Predictions')
plt.legend()
plt.show()