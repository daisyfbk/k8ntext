"""
find . -type d -name "*gpu" | while read folder; do cat $folder/main.log | cut -f 6- -d "-" | grep Features | uniq; jq -c '.[].core_metrics' $folder/metrics.json; echo; done > metrics

 INFO - Features: 38: ['annotations.authorization.k8s.io/decision', 'objectRef.apiGroup', 'objectRef.namespace', 'objectRef.resource', 'objectRef.subresource', 'requestObject.apiVersion', 'requestObject.kind', 'requestObject.metadata.namespace', 'requestObject.metadata.ownerReferences.apiVersion', 'requestObject.metadata.ownerReferences.blockOwnerDeletion', 'requestObject.metadata.ownerReferences.controller', 'requestObject.metadata.ownerReferences.kind', 'requestObject.spec.volumeMode', 'requestObject.volumeBindingMode', 'responseObject.count', 'responseObject.involvedObject.apiVersion', 'responseObject.involvedObject.kind', 'responseObject.involvedObject.namespace', 'responseObject.involvedObject.resource', 'responseObject.involvedObject.subresource', 'responseObject.kind', 'responseObject.metadata.ownerReferences.apiVersion', 'responseObject.metadata.ownerReferences.blockOwnerDeletion', 'responseObject.metadata.ownerReferences.controller', 'responseObject.metadata.ownerReferences.kind', 'responseObject.reason', 'responseObject.reportingComponent', 'responseObject.source.component', 'responseObject.spec.volumeMode', 'responseObject.type', 'responseStatus.code', 'user.groups[0]', 'user.groups[1]', 'user.groups[2]', 'userAgent.extra', 'userAgent.tool', 'userAgent.version', 'verb']
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
    "responseObject.metadata": "(response)",
    "requestObject.metadata": "(request)",
}

# replace long names with shorter ones
for i in range(len(sorted_data)):
    for j in convert.keys():
        if sorted_data[i][0].startswith(j):
            sorted_data[i] = (sorted_data[i][0].replace(j, convert[j]), sorted_data[i][1])

all_features_run = runs[ddel[0]]

# Keep first 5, last 5, put the average of the rest
offset = 5
sorted_data = sorted_data[:offset] + \
    [(" ...", 0)] + \
    [('All features', all_features_run['metrics']['precision'])] + \
    [(" ... ", 0)] + \
    [('Average', np.mean([item[1] for item in sorted_data[offset:]]),)] + \
    [("... ", 0)] + \
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
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig("precision.png")