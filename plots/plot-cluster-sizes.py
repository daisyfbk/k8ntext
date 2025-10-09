#!/usr/bin/env python3

import json
import sys
import matplotlib.pyplot as plt
import argparse

def plot_cluster_statistics(stats_file):
    """
    Plot statistics about the average number of logs per cluster.
    
    Args:
        stats_file (str): Path to the JSON statistics file
    """
    # Load statistics
    clusters = []
    with open(stats_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            clusters.append(json.loads(line))

    # List of lines that look like this
    # {"uuid":"dc042b0f-828c-419b-b53b-793240d28199","num_lines":20,"label":61632,"indices":[1698,1727,1758,1787,1816,1855,1886,1917,1958,1992,2021,2054,2084,2115,2144,2180,2209,2244,2277,2308],"lines":[{"username":"system:node:kubeadm-worker2","verb":"get","resource":"nodes","subresource":null,"namespace":null,"name":"kubeadm-worker2","requestURI":"/api/v1/nodes/kubeadm-worker2","requestReceivedTimestamp":"2024-05-29T09:00:53.677265Z","stageTimestamp":"2024-05-29T09:00:53.679098Z","metadata/uid":"da9a4c6f-2c75-41ef-b0b4-a25694dc8ede"},{"username":"system:node:kubeadm-worker2","verb":"get","resource":"nodes","subresource":null,"namespace":null,"name":"kubeadm-worker2","requestURI":"/api/v1/nodes/kubeadm-worker2","requestReceivedTimestamp":"2024-05-29T09:01:03.956523Z","stageTimestamp":"2024-05-29T09:01:03.958796Z","metadata/uid":"da9a4c6f-2c75-41ef-b0b4-a25694dc8ede"},{"username":"system:node:kubeadm-worker2","verb":"get","resource":"nodes","subresource":null,"namespace":null,"name":"kubeadm-worker2","requestURI":"/api/v1/nodes/kubeadm-worker2","requestReceivedTimestamp":"2024-05-29T09

    labels = {}
    for cluster in clusters:
        label = cluster["label"]
        if label not in labels:
            labels[label] = (0, 0) # (total lines, number of clusters)
        labels[label] = (labels[label][0] + cluster["num_lines"], labels[label][1] + 1)

    
    # Extract data for plotting
    averages = {}
    for label, lines in labels.items():
        averages[label] = lines[0] / lines[1]  # average logs per cluster
    
    # Sort by average value
    averages = dict(sorted(averages.items(), key=lambda item: item[1], reverse=True))
    
    print(f"Total labels with clusters: {len(averages)}")
    
    # Create binned data for plotting
    bins = {
        "1": 0,
        "(1, 5)": 0,
        "[5, 10)": 0,
        "[10, 20)": 0,
        "[20, 50)": 0,
        "[50, +Inf)": 0,
    }
    
    for label in averages:
        if averages[label] == 1:
            bins["1"] += 1
        elif averages[label] < 5:
            bins["(1, 5)"] += 1
        elif averages[label] < 10:
            bins["[5, 10)"] += 1
        elif averages[label] < 20:
            bins["[10, 20)"] += 1
        elif averages[label] < 50:
            bins["[20, 50)"] += 1
        else:
            bins["[50, +Inf)"] += 1
    
    # Print percentage for each bin
    total = sum(bins.values())
    for bin_name in bins:
        percentage = (bins[bin_name] / total) * 100
        print(f"{bin_name}: {bins[bin_name]} labels ({percentage:.2f}%)")
    
    # Create horizontal bar plot
    plt.figure(figsize=(10, 4))
    plt.rcParams.update({'font.size': 12})
    plt.barh(list(bins.keys()), list(bins.values()), color='#3070c8')
    plt.title("Number of logs clustered for each label")
    plt.ylabel("Average number of logs per cluster")
    plt.xlabel("Number of labels")
    
    # Add text labels on the bars
    for i, v in enumerate(bins.values()):
        plt.text(v + 0.5, i, str(v), va='center')
    
    # Save and display
    output_file = "cluster_distribution.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to {output_file}")
    
    # Create a second plot showing the distribution of average cluster sizes
    plt.figure(figsize=(12, 6))
    plt.hist(list(averages.values()), bins=50, color='#3070c8', edgecolor='black')
    plt.title("Distribution of average logs per cluster")
    plt.xlabel("Average logs per cluster")
    plt.ylabel("Number of labels")
    plt.yscale('log')  # Log scale for better visualization
    plt.grid(True, alpha=0.3)
    plt.savefig("cluster_size_histogram.png", dpi=300, bbox_inches='tight')
    print("Histogram saved to cluster_size_histogram.png")
    
    # Generate TikZ version
    generate_tikz(bins)

def generate_tikz(bins):
    """
    Generate TikZ/PGFPlots code for the cluster distribution chart.
    
    Args:
        bins (dict): Dictionary with bin names as keys and counts as values
    """
    # Helper function to escape underscores and special characters for LaTeX
    def escape_latex(text):
        text = text.replace('_', r'\_')
        text = text.replace('[', r'[')
        text = text.replace(')', r')')
        text = text.replace('(', r'(')
        text = text.replace('+Inf', r'+$\infty$')
        return text
    
    # Create a list of bin labels and values
    bin_labels = [escape_latex(label) for label in bins.keys()]
    bin_values = list(bins.values())
    
    tikz_header = r"""\documentclass[border=5pt]{standalone}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}

\begin{document}

\definecolor{plotblue}{HTML}{3070c8}

\begin{tikzpicture}
\begin{axis}[
    width=0.9\linewidth,
    xmajorgrids=true,
    major grid style={dotted, very thick},
    xlabel={Number of labels},
    xmin=0,"""
    
    # Calculate appropriate xmax based on data
    xmax = max(bin_values) * 1.1
    
    yticks = ", ".join([str(i) for i in range(len(bin_labels))])
    ylabels = ", ".join(["{" + label + "}" for label in bin_labels])
    
    tikz_middle = f"""
    xmax={xmax:.0f},
    ytick={{{yticks}}},
    yticklabels={{{ylabels}}},
    bar width=5pt,
    enlarge y limits=0.05,
    nodes near coords,
    nodes near coords align={{horizontal}},
    every node near coord/.append style={{
        font=\\small,
        xshift=8pt
    }},
    title={{Number of logs clustered for each label}},
    tick label style={{font=\\small}},
    label style={{font=\\small}},
    ytick pos=left,
]

"""
    
    # Generate coordinates for the bars
    tikz_plots = ""
    for i, (label, value) in enumerate(bins.items()):
        tikz_plots += f"""\\addplot[xbar, fill=plotblue, draw=none] coordinates {{
    ({value},{i})
}};

"""
    
    tikz_footer = r"""\end{axis}
\end{tikzpicture}

\end{document}
"""
    
    tikz_content = tikz_header + tikz_middle + tikz_plots + tikz_footer
    
    with open("cluster-sizes-tikz.tex", "w") as f:
        f.write(tikz_content)
    
    print("TikZ file generated: cluster-sizes-tikz.tex")

def main():
    parser = argparse.ArgumentParser(description="Plot cluster sizes from JSON file")
    parser.add_argument('stats_file', help='The JSON clusters file generated by clusterizer_stats.py')
    
    args = parser.parse_args()
    plot_cluster_statistics(args.stats_file)

if __name__ == "__main__":
    main()