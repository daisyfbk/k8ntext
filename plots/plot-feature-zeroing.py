"""
find . -type d -name "*gpu" | while read folder; do cat $folder/main.log | cut -f 6- -d "-" | grep Features | uniq; jq -c '.[].core_metrics' $folder/metrics.json; echo; done > metrics

 INFO - Features: 38: ['annotation    nodes near coords align={horizontal},
    every node near coord/.append style={
        font=\tiny,
        /pgf/number format/precision=3,
        /pgf/number format/fixed,
        xshift=3pt
    },rization.k8s.io/decision', 'objectRef.apiGroup', 'objectRef.namespace', 'objectRef.resource', 'objectRef.subresource', 'requestObject.apiVersion', 'requestObject.kind', 'requestObject.metadata.namespace', 'requestObject.metadata.ownerReferences.apiVersion', 'requestObject.metadata.ownerReferences.blockOwnerDeletion', 'requestObject.metadata.ownerReferences.controller', 'requestObject.metadata.ownerReferences.kind', 'requestObject.spec.volumeMode', 'requestObject.volumeBindingMode', 'responseObject.count', 'responseObject.involvedObject.apiVersion', 'responseObject.involvedObject.kind', 'responseObject.involvedObject.namespace', 'responseObject.involvedObject.resource', 'responseObject.involvedObject.subresource', 'responseObject.kind', 'responseObject.metadata.ownerReferences.apiVersion', 'responseObject.metadata.ownerReferences.blockOwnerDeletion', 'responseObject.metadata.ownerReferences.controller', 'responseObject.metadata.ownerReferences.kind', 'responseObject.reason', 'responseObject.reportingComponent', 'responseObject.source.component', 'responseObject.spec.volumeMode', 'responseObject.type', 'responseStatus.code', 'user.groups[0]', 'user.groups[1]', 'user.groups[2]', 'userAgent.extra', 'userAgent.tool', 'userAgent.version', 'verb']
{"accuracy":0.999746652189649,"precision":0.9820577606862705,"recall":0.9981263035486602,"f1":0.98183111992232}
{"accuracy":0.9998371335504886,"precision":0.9896819472318568,"recall":0.9973073864805495,"f1":0.989314372988677}
{"accuracy":0.9997557003257329,"precision":0.9947236446344158,"recall":0.9979194630715634,"f1":0.9941887932031857}
{"accuracy":0.9998190372783207,"precision":0.990712834425152,"recall":0.9990731017512366,"f1":0.9906974721258159}
{"accuracy":0.999710459645313,"precision":0.9770912709919967,"recall":0.997706023817231,"f1":0.9770910031159898}

 INFO - Features: 38: ['annotations.authorization.k8s.io/decision', 'objectRef.apiGroup', 'objectRef.namespace', 'objectRef.resource', 'objectRef.subresource', 'requestObject.apiVersion', 'requestObject.kind', 'requestObject.metadata.namespace', 'requestObject.metadata.ownerReferences.apiVersion', 'requestObject.metadata.ownerReferences.blockOwnerDeletion', 'requestObject.metadata.ownerReferences.controller', 'requestObject.metadata.ownerReferences.kind', 'requestObject.spec.volumeMode', 'requestObject.volumeBindingMode', 'responseObject.count', 'responseObject.involvedObject.apiVersion', 'responseObject.involvedObject.kind', 'responseObject.involvedObject.namespace', 'responseObject.involvedObject.resource', 'responseObject.involvedObject.subresource', 'responseObject.kind', 'responseObject.metadata.namespace', 'responseObject.metadata.ownerReferences.apiVersion', 'responseObject.metadata.ownerReferences.blockOwnerDeletion', 'responseObject.metadata.ownerReferences.controller', 'responseObject.metadata.ownerReferences.kind', 'responseObject.reason', 'responseObject.reportingComponent', 'responseObject.source.component', 'responseObject.spec.volumeMode', 'responseObject.type', 'responseStatus.code', 'user.groups[0]', 'user.groups[1]', 'user.groups[2]', 'userAgent.tool', 'userAgent.version', 'verb']
{"accuracy":0.9997014115092291,"precision":0.9861116428363613,"recall":0.9969634762714078,"f1":0.9851681023455678}
{"accuracy":0.9997376040535649,"precision":0.9972459036155567,"recall":0.9970648130807969,"f1":0.9968887628260741}
{"accuracy":0.9996290264205574,"precision":0.9780167031642051,"recall":0.9932713708742924,"f1":0.9733891432603451}
{"accuracy":0.9998190372783207,"precision":0.989636649661067,"recall":0.9985041011818762,"f1":0.9898257146274676}
{"accuracy":0.9996923633731452,"precision":0.9947367014706401,"recall":0.9981239582357905,"f1":0.9943011124215483}

"""

import json

lines = []
with open('/Users/matte/Codice/fbk/k8ntext-impl/models/1_paper_tests/4_feature_selection/zeroing/metrics', 'r') as f:
    lines = f.readlines()

runs = []
RUNS = 20
collected_features = set()

for i in range(0, len(lines), 2 + RUNS):
    run = {}
    llen = int(lines[i].split('s: ')[1].split(': ')[0])
    if llen < 38:
        continue
    run['features'] = lines[i].split(': ')[2]\
        .replace("'", "")\
        .replace("[", "")\
        .replace("]", "")\
        .replace(" ", "")\
        .replace("\n", "")\
        .split(',')
    for feature in run['features']:
        collected_features.add(feature)
    run['metrics'] = {
        'accuracy': 0,
        'precision': 0,
        'recall': 0,
        'f1': 0
    }
    for j in range(1, 1 + RUNS):
        jj = json.loads(lines[i + j].replace('\n', ''))
        for key in jj.keys():
            run['metrics'][key] += jj[key]

    for key in run['metrics'].keys():
        run['metrics'][key] /= RUNS
    
    runs.append(run)

ddel = []
for i in range(len(runs)):
    run = runs[i]
    # print(len(collected_features), len(run['features']))
    run['missing_features'] = collected_features.difference(set(run['features']))
    run['missing_features'] = list(run['missing_features'])
    if len(run['missing_features']) > 1 or len(run['missing_features']) == 0:
        # print(run['missing_features'])
        ddel.append(i)
    del run['features']

if len(ddel) > 1:
    # keep only the first run
    ddel = ddel[0]
    runs[ddel]['missing_features'] = ['All features']

from matplotlib import pyplot as plt
import numpy as np

#['accuracy', 'precision', 'recall', 'f1']

# X axis: missing feature
# Y axis: metric (4 lines)

# print just precision
# Collect data for precision
data = {}
for run in runs:
    if run['missing_features']:
        data[run['missing_features'][0]] = run['metrics']['precision']

# Sort data by precision values
sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)

convert = {
    "responseObject.metadata": "response",
    "requestObject.metadata": "request",
}

# replace long names with shorter ones and handle square brackets
for i in range(len(sorted_data)):
    # Replace long prefixes
    for j in convert.keys():
        if sorted_data[i][0].startswith(j):
            sorted_data[i] = (sorted_data[i][0].replace(j, convert[j]), sorted_data[i][1])
    
    # Replace square brackets that cause issues in LaTeX symbolic coords
    feature_name = sorted_data[i][0]
    feature_name = feature_name.replace('[', '').replace(']', '')
    sorted_data[i] = (feature_name, sorted_data[i][1])

all_features_run = runs[ddel[0]]

    # Keep first 5, last 5, put the average of the rest
offset = 5
    # [("dotdotdot1", 0)] + \
    # [("dotdotdot2", 0)] + \
    # [("dotdotdot3", 0)] + \
sorted_data = sorted_data[:offset] + \
    [('All features', all_features_run['metrics']['precision'])] + \
    [('Average', np.mean([item[1] for item in sorted_data[offset:]]),)] + \
    sorted_data[-offset:]
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


special_colors = {
    "Average": palette['green'],
    "All features": palette['red']
}

# Extract sorted keys and values
features = [item[0] for item in sorted_data]
precisions = [item[1] for item in sorted_data]

# Create the horizontal bar plot
plt.figure(figsize=(7, 4), dpi=300)

plt.rcParams.update({'font.size': 12})

plt.barh(features, precisions, color=[special_colors.get(f, palette['blue']) for f in features])

# reserve space on the left
plt.subplots_adjust(left=0.65, right=0.99)

# Add labels and title
plt.xlabel('F1 score')
#plt.ylabel('Missing Feature')
plt.suptitle('F1 score with Different Missing Features')


# remove the ticks where the ellipses are but keep the labels and shift 45 degrees
plt.tick_params(axis='y', which='both', left=False, right=False, labelleft=True)
plt.xticks(np.arange(0.97, 1, 0.005), rotation=45)


# shift title to the left
plt.xlim(0.97, 1)

# Show the plot
plt.tight_layout(rect=(0, 0, 1, 0.95))
plt.savefig("feature-zeroing.png")

# import matplot2tikz

# Save to TikZ/PGFPlots
# matplot2tikz.save("feature-zeroing-tikz.tex", axis_width='12cm', axis_height='10cm')

# exit(1)
# Generate TikZ version
def generate_tikz():
    # Helper function to escape underscores for LaTeX
    def escape_latex(text):
        text = text.replace('_', r'\_')
        return text
    
    # Create a list of all features with their indices
    y_labels = [escape_latex(f) for f in features]
    
    tikz_header = r"""\documentclass[border=5pt]{standalone}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}

\begin{document}

\definecolor{plotblue}{HTML}{3070c8}
\definecolor{plotgreen}{HTML}{228833}
\definecolor{plotred}{HTML}{EE6677}

\begin{tikzpicture}
\begin{axis}[
    width=0.5\linewidth,
    xmajorgrids=true,
    major grid style={dotted, very thick},
    xlabel={F1 score},
    xmin=0.97, xmax=1.0,
    xtick={0.97, 0.975, 0.98, 0.985, 0.99, 0.995, 1.0},
    xticklabel style={
        /pgf/number format/fixed,
        /pgf/number format/precision=3,
        rotate=45,
        anchor=east,
    },"""
            
    yticks = ", ".join([str(i) for i in range(len(features))])
    ylabels = ", ".join(["{" + label + "}" for label in y_labels])
    
    tikz_middle = f"""
    ytick={{{yticks}}},
    yticklabels={{{ylabels}}},
    % y dir=reverse,
    bar width=5pt,
    enlarge y limits=0.05,
    """
    tikz_middle += r"""
    nodes near coords={\pgfmathprintnumber[fixed,precision=4]{\pgfplotspointmeta}},
    point meta=x,  % Use x-value (F1 score) for labels instead of y-value (index)
    nodes near coords align={horizontal},
    every node near coord/.append style={
        font=\footnotesize,
        xshift=3pt
    },
    title={F1 score with Different Missing Features},
    %title style={yshift=5pt},
    tick label style={font=\small},
    label style={font=\small},
    ytick pos=left,
    %xticklabel style={rotate=45, anchor=east, align=right, text width=6cm},
]

"""
    
    # Generate coordinates grouped by color
    tikz_plots = ""
    
    # Top 5 (blue)
    top5_coords = []
    for i, (f, p) in enumerate(sorted_data[:5]):
        # Format as (value, index)
        top5_coords.append(f"({p:.4f},{i})")
        tikz_plots += f"""% {f} (blue)
\\addplot[xbar, fill=plotblue, draw=none] coordinates {{
    ({p:.4f},{i})
}};
"""
    
#    # Spacer (no need for symbolic coordinates now, just use the index)
#    spacer_index = 5
#    tikz_plots += f"""% Spacer
# \\addplot[draw=none, forget plot] coordinates {{(0,{spacer_index})}}; 
#"""
    
    # All features (red)
    all_feat_index = 5 # 8
    all_feat_data = [item for item in sorted_data if item[0] == "All features"][0]
    tikz_plots += f"""% All features (red)
\\addplot[xbar, fill=plotred, draw=none] coordinates {{
    ({all_feat_data[1]:.4f},{all_feat_index})
}};

"""
    
    # Average (green)
    avg_index = 6 # 6
    avg_data = [item for item in sorted_data if item[0] == "Average"][0]
    tikz_plots += f"""% Average (green)
\\addplot[xbar, fill=plotgreen, draw=none] coordinates {{
    ({avg_data[1]:.4f},{avg_index})
}};

"""
    
#     # Spacer
#     spacer_index2 = 7
#     tikz_plots += f"""% Spacer
# \\addplot[draw=none, forget plot] coordinates {{(0,{spacer_index2})}};
# 
# """
    
    
#     # Spacer
#     spacer_index3 = 9
#     tikz_plots += f"""% Spacer
# \\addplot[draw=none, forget plot] coordinates {{(0,{spacer_index3})}};
# 
# """
    
    # Bottom 5 (blue)
    bottom5_coords = []
    for i in range(7, 12): # 10, 15):
        # Map to the correct sorted_data index (last 5 items)
        data_index = i - 7 + len(sorted_data) - 5
        f, p = sorted_data[data_index]
        # Format as (value, index)
        bottom5_coords.append(f"({p:.4f},{i})")
        tikz_plots += f"""% {f} (blue)
\\addplot[xbar, fill=plotblue, draw=none] coordinates {{
    ({p:.4f},{i})
}};

"""
    
    tikz_footer = r"""\end{axis}
\end{tikzpicture}

\end{document}
"""
    
    with open("feature-zeroing-tikz.tex", "w") as f:
        f.write(tikz_header + tikz_middle + tikz_plots + tikz_footer)
    
    print("TikZ file generated: feature-zeroing-tikz.tex")

generate_tikz()