# {"kind": "Event", "apiVersion": "audit.k8s.io/v1", "level": "RequestResponse", "auditID": "711e70a1-14da-4278-aded-3b3e39e50ce8", "stage": "ResponseComplete", "requestURI": "/api/v1/pods?allowWatchBookmarks=true&fieldSelector=spec.nodeName%3Dkubeadm-worker1&resourceVersion=2219850&timeoutSeconds=556&watch=true", "verb": "watch", "user": {"username": "system:node:kubeadm-worker1", "groups": ["system:nodes", "system:authenticated"]}, "sourceIPs": ["192.168.38.11"], "userAgent": "kubelet/v1.28.6 (linux/amd64) kubernetes/be3af46", "objectRef": {"resource": "pods", "apiVersion": "v1", "namespace": null, "apiGroup": "core"}, "responseStatus": {"metadata": {}, "code": 200}, "requestReceivedTimestamp": "2024-05-28T09:15:35.367095Z", "stageTimestamp": "2024-05-28T09:24:51.369969Z", "annotations": {"authorization.k8s.io/decision": "allow", "authorization.k8s.io/reason": ""}, "label": 4176, "cplabel": true, "predicted_label": 4496}

import json
import sys
from label_proposer import decode_label, propose_label

file = sys.argv[1]
labels = {}
tr = 0
triggering = {}
is_cp = {}
with open(file) as f:
    i = 0
    for line in f:
        i += 1
        data = json.loads(line)
        label = data.get('label')
        if label:
            labels[label] = labels.get(label, 0) + 1
        else:
            print("Label not found in the line: " + line)
            continue
        decoded = decode_label(label)
        if decoded['apiGroup'] == 'unknown.fbk.eu':
            continue
        proposed = propose_label(data)
        if proposed == label:
            triggering[label] = triggering.get(label, 0) + 1
            if data.get('cplabel') == True:
                is_cp[label] = is_cp.get(label, 0) + 1
            tr += 1
        

    print("Total triggering events: ", tr)
    print("Total lines: ", i)
label_after_cluster = {}
            
print(triggering.keys())
# 119232%kube-node-lease%db6a67cd-b742-4291-a2ca-2861b2968a37,"{'username': 'system:node:kubeadm-worker1', 'verb': 'update', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-node-lease', 'name': 'kubeadm-worker1', 'requestReceivedTimestamp': '2024-05-28T09:24:12.745411Z', 'stageTimestamp': '2024-05-28T09:24:12.752851Z', 'ownerReferences': [{'apiVersion': 'v1', 'kind': 'Node', 'name': 'kubeadm-worker1', 'uid': 'db6a67cd-b742-4291-a2ca-2861b2968a37'}], 'metadata/uid': '535ef3e4-70b6-4e00-8d2c-f71aad03087d', 'UUID': 'a58d31e6-8481-45be-9353-24df88d782f3'}"

file2 = sys.argv[2]
with open(file2) as f:
    for line in f:
        label = line.split('%')[0]
        label = int(label)
        label_after_cluster[label] = label_after_cluster.get(label, 0) + 1

# join the two
joined = {}
for label in labels:
    if label in label_after_cluster:
        joined[label] = {
            "line": labels[label],
            "cluster": label_after_cluster[label],
            "triggering": triggering[label]
        }

for label in labels:
    if label not in joined:
        joined[label] = {
            "line": labels[label],
            "cluster": 1,
            "triggering": 1
        }

# both on x and y axis 
print(joined)
averages = {}
for label in joined:
    if decode_label(label)['apiGroup'] == 'unknown.fbk.eu':
        continue
    averages[label] = joined[label]['line'] / (joined[label]['triggering'])
averages = dict(sorted(averages.items(), key=lambda item: item[1], reverse=True))
print("Averages: ", averages)

import matplotlib.pyplot as plt

plt.figure(figsize=(10, 4))
plt.rcParams.update({'font.size': 12})

# binned plot
# y axis: number of labels for that bin
# x axis: bins separated by how many labels are in that bin
#inverse_count = {
#    
#}
#for k, v in averages.items():
#    if v not in inverse_count:
#        inverse_count[v] = []
#    inverse_count[v].append(k)
#
#print(inverse_count)
#plt.bar(inverse_count.keys(), [len(v) for v in inverse_count.values()])
#plt.show()
#exit(1)


bins = {
    "[1, 5)": 0,
    "[5, 10)": 0,
    "[10, 20)": 0,
    "[20, 50)": 0,
    "[50, 100)": 0,
    "[100, +Inf)": 0
}
for label in averages:
    if averages[label] < 5:
        bins["[1, 5)"] += 1
    elif averages[label] < 10:
        bins["[5, 10)"] += 1
    elif averages[label] < 20:
        bins["[10, 20)"] += 1
    elif averages[label] < 50:
        bins["[20, 50)"] += 1
    elif averages[label] < 100:
        bins["[50, 100)"] += 1
    else:
        bins["[100, +Inf)"] += 1
 
for __b in bins:
    print(__b)
    print(bins[__b]/sum(bins.values()))
# Horizontal bar plot
plt.figure(figsize=(10, 4))
plt.barh(list(bins.keys()), list(bins.values()))
plt.title("Number of logs clustered for each label")
plt.ylabel("Average number of clustered logs")
plt.xlabel("Number of labels")
plt.savefig("number_of_logs.png", dpi=300, bbox_inches='tight')