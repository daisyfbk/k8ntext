# jq -c 'select(.user.username=="system:serviceaccount:kube-system:namespace-controller")' woutlabel | jq ".label = 41376"

import json
from label_proposer import propose_label
import argparse
import subprocess
import os, sys
from tqdm import tqdm

parser = argparse.ArgumentParser(description='Label control plane logs')
parser.add_argument('-f', '--file', type=str, help='Input file', required=True)
parser.add_argument('-o', '--output', type=str, help='Output file', required=True)

args = parser.parse_args()

if not os.path.exists(args.file):
    print("Input file does not exist")
    sys.exit(1)

if os.path.exists(args.output):
    print("Output file already exists, refusing to overwrite.")
    sys.exit(1)

labelled = []
unlabelled = []

with open(args.file) as f:
    lines = f.readlines()
    for line in tqdm(lines):
        if '"label":' in line:
            labelled.append(line)
        else:
            unlabelled.append(line)

print("Total labelled: ", len(labelled))
print("Total unlabelled: ", len(unlabelled))

count = 0
temp_file = subprocess.check_output('mktemp', text=True).strip()

with open(temp_file, 'w') as f:
    for line in tqdm(unlabelled):
        o = json.loads(line)
        if 'objectRef' in o and o['objectRef']["resource"] == 'leases' \
            and o['verb'] in ('get', 'update', 'patch'):
            # Routine lease renewals
            # mapped to patch events on leases
            o['label'] = 119232
        elif o['user']['username'] == 'system:serviceaccount:kube-system:namespace-controller':
            # Namespace controller deleting things
            # mapped to delete events on namespaces
            o['label'] = 41376
        elif o['user']['username'] == 'system:kube-scheduler' \
            and o['verb'] == 'create' \
            and o['objectRef']['resource'] == 'events':
            # Scheduler creating events after pods are created
            # mapped to create events on pods
            o['label'] = 4496
        elif o['user']['username'] == 'system:kube-controller-manager' \
            and o['verb'] in ('get', 'create') \
            and o['objectRef']['resource'] == 'serviceaccounts':
            # mapped to token creation for service accounts
            o['label'] = 17808
        elif "system:nodes" in o['user']['groups'] and \
            o['verb'] in ('create',) and \
            o['objectRef']['resource'] == 'events':
            # Event creation after pods are created
            # mapped to create events on pods
            if o['requestObject']['involvedObject']['kind'] == 'Pod':
                o['label'] = 4496
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('patch', 'get') and \
            o['objectRef']['resource'] == 'pods':
            # Pod status updates
            # Mapped as a pod update
            o['label'] = 4544 # 4496
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('get',) and \
            o['objectRef']['resource'] == 'nodes':
            # Node status updates for themselves
            o['label'] = 61616
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('patch',) and \
            o['objectRef']['resource'] == 'nodes':
            # Node status updates for themselves
            o['label'] = 62144
        elif o['verb'] == 'watch' \
            and (not 'namespace' in o['objectRef'] or o['objectRef']['namespace'] == None):
            # Watch events on cluster-wide resources
            # Usually nodes, kube-proxy, etc.
            o['label'] = propose_label(o)
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('watch',) and \
            o['objectRef']['resource'] == 'configmaps':
            # Nodes watching configmaps for token expiry
            o['label'] = propose_label(o)
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('create','watch') and \
            o['objectRef']['resource'] == 'serviceaccounts' and \
            o['objectRef']['subresource'] == 'token':
            # Nodes renewing tokens for SAs they monitor
            o['label'] = propose_label(o)

        if not 'label' in o:
            count -= 1
        
        f.write(json.dumps(o, separators=(',', ':')) + '\n')

newly_labelled = []
with open(temp_file) as f:
    newly_labelled = f.readlines()

print("Total parsed: ", len(newly_labelled))
print("Total newly labelled: ", len(newly_labelled) + count)

out_lines = labelled + newly_labelled
out_lines.sort(key=lambda x: json.loads(x)['requestReceivedTimestamp'])

print("Total lines: ", len(out_lines))

with open(args.output, 'w') as f:
    for line in out_lines:
        f.write(line)

subprocess.run(['rm', temp_file])
