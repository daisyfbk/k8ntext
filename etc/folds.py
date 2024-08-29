import pandas as pd
import matplotlib.pyplot as plt
# Read the CSV file
df = pd.read_csv('lmao.csv')
df['fold'] = df['fold'].astype(float)
# sort the dataframe
df = df.sort_values(by=['features', 'background', 'fold'])
# Plot accuracy for different backgrounds and folds
plt.figure(figsize=(14, 7))
for feature_count in df['features'].unique():
    for background in df['background'].unique():
        df_filtered = df[(df['features'] == feature_count) & (df['background'] == background)]
        if background == 'nobg':
            df_filtered.loc[:, 'fold'] = df_filtered['fold'] / (41124/(4000 + 41124))
        plt.plot(df_filtered['fold'], df_filtered['accuracy'], label=f'{feature_count} features, {background} background')
# Add labels and title
plt.xlabel('Fold')
plt.ylabel('Accuracy')
plt.title('Accuracy vs Fold for Different Backgrounds and Features')
plt.legend()
plt.grid(True)
# Show the plot
plt.show()