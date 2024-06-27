# jq -c 'select(.user.username=="system:serviceaccount:kube-system:namespace-controller")' woutlabel | jq ".label = 41376"

import json
from label_proposer import propose_label
import argparse
import subprocess
import os
import sys
from tqdm import tqdm
from common import LABEL_IGNORE, LABEL_UNKNOWN

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
        o = json.loads(line)
        if 'label' in o and o['label'] != LABEL_UNKNOWN:
            labelled.append(line)
        else:
            unlabelled.append(line)

total = len(lines)
print("Total lines: ", total)
print("Total labelled: ", len(labelled))
print("Total unlabelled: ", len(unlabelled))

count = 0
temp_file = subprocess.check_output('mktemp', text=True).strip()

with open(temp_file, 'w') as f:
    for line in tqdm(unlabelled):
        o = json.loads(line)

        if not 'objectRef' in o:
            # if o['requestURI'] in ('/api','/api/v1','/apis'):
            o['label'] = propose_label(o)
        elif o['objectRef']["resource"] == 'leases' \
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
        elif "system:nodes" in o['user']['groups'] and \
            o['verb'] in ('patch',) and \
            o['objectRef']['resource'] == 'events':
            o['label'] = propose_label(o)
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
        elif o['user']['username'] == 'system:apiserver' and \
            o['verb'] in ('watch',) and \
            o['objectRef']['resource'] == 'leases' and \
            o['objectRef']['namespace'] == 'kube-system':
            # API server watching leases
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:apiserver' and \
            o['verb'] in ('list','get') and \
            o['objectRef']['resource'] in ('services', 'limitranges','endpoints','endpointslices'):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:apiserver' and \
            o['verb'] in ('watch',) and \
            o['objectRef']['namespace'] == 'kube-system' and \
            o['objectRef']['resource'] in ('configmaps', 'secrets'):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:kube-scheduler' and \
            o['verb'] in ('watch',) and \
            o['objectRef']['namespace'] == 'kube-system' and \
            o['objectRef']['resource'] in ('configmaps', 'secrets'):
            o['label'] = propose_label(o)

        if not 'label' in o or o['label'] == LABEL_UNKNOWN:
            count -= 1
        else:
            o['cplabel'] = True
        
        f.write(json.dumps(o, separators=(',', ':')) + '\n')

with open(temp_file) as f:
    newly_labelled = f.readlines()

print("Total parsed: ", len(newly_labelled))
print("Total newly labelled: ", len(newly_labelled) + count)

if count == 0:
    print("All lines labelled automatically.")
else:
    print("Fancy labelling manually the remaining lines? (y/n) ", end='')
    if input().lower() == 'y':
        from main import ParsingMode, main

        old_line_count = len(newly_labelled)

        tmp2 = subprocess.check_output('mktemp', text=True).strip()
        with open(tmp2, 'w') as f:
            for line in newly_labelled:
                f.write(line)

        out_file = main(ParsingMode.labelling, input_filename=tmp2)

        with open(out_file) as f:
            newly_labelled = f.readlines()

        print("Total newly labelled after manual labelling: ", len(newly_labelled))

        if len(newly_labelled) == old_line_count:
            print("All lines labelled successfully.")
        else:
            print("WARNING: Some lines have been dropped by the manual labelling process. Please check the code and rerun.")

        subprocess.run(['rm', out_file, temp_file])

out_lines = labelled + newly_labelled
out_lines.sort(key=lambda x: json.loads(x)['requestReceivedTimestamp'])

print("Total lines: ", len(out_lines))

with open(args.output, 'w') as f:
    for line in out_lines:
        f.write(line)

subprocess.run(['rm', temp_file])
