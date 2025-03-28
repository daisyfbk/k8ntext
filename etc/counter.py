# {"kind": "Event", "apiVersion": "audit.k8s.io/v1", "level": "RequestResponse", "auditID": "711e70a1-14da-4278-aded-3b3e39e50ce8", "stage": "ResponseComplete", "requestURI": "/api/v1/pods?allowWatchBookmarks=true&fieldSelector=spec.nodeName%3Dkubeadm-worker1&resourceVersion=2219850&timeoutSeconds=556&watch=true", "verb": "watch", "user": {"username": "system:node:kubeadm-worker1", "groups": ["system:nodes", "system:authenticated"]}, "sourceIPs": ["192.168.38.11"], "userAgent": "kubelet/v1.28.6 (linux/amd64) kubernetes/be3af46", "objectRef": {"resource": "pods", "apiVersion": "v1", "namespace": null, "apiGroup": "core"}, "responseStatus": {"metadata": {}, "code": 200}, "requestReceivedTimestamp": "2024-05-28T09:15:35.367095Z", "stageTimestamp": "2024-05-28T09:24:51.369969Z", "annotations": {"authorization.k8s.io/decision": "allow", "authorization.k8s.io/reason": ""}, "label": 4176, "cplabel": true, "predicted_label": 4496}

import json
import sys

file = sys.argv[1]
labels = {}
with open(file) as f:
    for line in f:
        data = json.loads(line)
        label = data.get('predicted_label')
        if label:
            labels[label] = labels.get(label, 0) + 1

label_after_cluster = {}
            
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
            "cluster": label_after_cluster[label]
        }

for label in labels:
    if label not in joined:
        joined[label] = {
            "line": labels[label],
            "cluster": 1
        }

averages = []
for label in joined:
    averages.append(joined[label]['line'] / joined[label]['cluster'])

averages.sort()

print(averages)
import matplotlib.pyplot as plt

# y log
    
plt.hist(averages, bins=100)
plt.show()


print(joined)