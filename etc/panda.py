import pandas as pd
import matplotlib.pyplot as plt
import json

data = json.loads(open("../logs/models/data.json").read())

# Convert the JSON data to a pandas DataFrame
df = pd.DataFrame(data).sort_values(by='f1')

# Plotting
fig, ax = plt.subplots()
# Assuming 'mode' is categorical and you want different colors for each mode
colors = {'normal': 'blue', 'focal': 'green'}
for mode, color in colors.items():
    mode_df = df[df['mode'] == mode]
    ax.scatter(mode_df['f1'], mode_df['error_statistics'], c=color, label=mode)

    # colored line in the average of the data
    ax.axhline(mode_df['error_statistics'].mean(), color=color, linestyle='--')

# Adding labels and title for clarity
ax.set_xlabel('F1')
ax.set_ylabel('Number of Correct Predictions')
ax.set_title('Scatter Plot of F1 vs Actual Number of Correct Predictions')
plt.legend()
plt.show()