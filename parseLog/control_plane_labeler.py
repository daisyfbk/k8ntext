# jq -c 'select(.user.username=="system:serviceaccount:kube-system:namespace-controller")' woutlabel | jq ".label = 41376"

import json
from label_proposer import propose_label
import argparse
import subprocess
import os
import sys
from common import LABEL_IGNORE, LABEL_UNKNOWN, tqdm

parser = argparse.ArgumentParser(description='Label control plane logs')
parser.add_argument('-f', '--file', type=str, help='Input file', required=True)

args = parser.parse_args()

if not os.path.exists(args.file):
    print("Input file does not exist")
    sys.exit(1)

labelled = []
unlabelled = []

print("------")
print("Reading input file...")

with open(args.file) as f:
    lines = f.readlines()
    for line in tqdm(lines):
        o = json.loads(line)
        if 'label' in o and o['label'] != LABEL_UNKNOWN:
            labelled.append(line)
        else:
            unlabelled.append(line)

total = len(lines)
print("Total lines read: ", total)
print("Total labelled: ", len(labelled))
print("Total unlabelled: ", len(unlabelled))

print("------")
print("Automatically labelling...")

count = 0
temp_file = subprocess.check_output('mktemp', text=True).strip()

with open(temp_file, 'w') as f:
    for line in tqdm(unlabelled):
        o = json.loads(line)

        if not 'objectRef' in o:
            # if o['requestURI'] in ('/api','/api/v1','/apis'):
            o['label'] = propose_label(o)
        
        # Kube-Scheduler
        elif o['user']['username'] == 'system:kube-scheduler' \
            and o['objectRef']['resource'] == 'leases' \
            and o['verb'] in ('get', 'update', 'patch') \
            and o['objectRef']['namespace'] == 'kube-system':
            # Scheduler renewing leases
            o['label'] = 118976
        elif o['user']['username'] == 'system:kube-scheduler' and \
            o['verb'] in ('watch',) and \
            'namespace' not in o['objectRef']:
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:kube-scheduler' and \
            o['verb'] in ('watch',) and \
            o['objectRef']['namespace'] == 'kube-system' and \
            o['objectRef']['resource'] in ('configmaps',):
            o['label'] = propose_label(o)

        # KCM, API Server
        elif o['user']['username'] == 'system:kube-controller-manager' \
            and o['objectRef']['resource'] == 'leases' \
            and o['verb'] in ('get', 'update', 'patch') \
            and o['objectRef']['namespace'] == 'kube-system':
            # Controller manager renewing leases
            o['label'] = 118976
        elif o['user']['username'] in ('system:apiserver', 'system:kube-controller-manager') \
            and 'namespace' not in o['objectRef'] \
            and 'name' not in o['objectRef'] \
            and o['verb'] in ('watch',):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:apiserver' \
            and o['objectRef']['resource'] in ('endpoints', 'endpointslices') \
            and o['verb'] == 'get' \
            and o['objectRef']['namespace'] == 'default' \
            and o['objectRef']['name'] == 'kubernetes':
            # API server getting endpoints for kubernetes service
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:apiserver' \
            and o['objectRef']['resource'] == 'leases' \
            and o['verb'] in ('update', 'patch') \
            and o['objectRef']['namespace'] == 'kube-system':
            # API server renewing leases
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:apiserver' and \
            o['verb'] in ('list','get') and \
            o['objectRef']['resource'] in ('services',):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:apiserver' and \
            o['verb'] in ('watch',) and \
            o['objectRef']['namespace'] == 'kube-system' and \
            o['objectRef']['resource'] in ('configmaps', 'leases'):
            o['label'] = propose_label(o)

        # Nodes
        elif "system:nodes" in o['user']['groups'] \
            and o['objectRef']['resource'] == 'nodes' \
            and o['verb'] in ('watch', 'get', 'patch'):
            # Node status updates for themselves
            o['label'] = 61632 # 61616 for get
        elif "system:nodes" in o['user']['groups'] \
            and o['objectRef']['resource'] == 'leases' \
            and o['verb'] in ('update', 'patch') \
            and o['objectRef']['namespace'] == 'kube-node-lease':
            # Node renewing leases
            o['label'] = propose_label(o)
        elif "system:nodes" in o['user']['groups'] \
            and 'namespace' not in o['objectRef'] \
            and 'name' not in o['objectRef'] \
            and o['verb'] in ('watch',):
            o['label'] = propose_label(o)
        elif "system:nodes" in o['user']['groups'] \
            and 'namespace' in o['objectRef'] and o['objectRef']['namespace'] == 'kube-system' \
            and o['verb'] in ('watch',):
            o['label'] = propose_label(o)
        # still unsure about the next
        elif "system:nodes" in o['user']['groups'] \
            and o['objectRef']['resource'] == 'serviceaccounts' \
            and o['objectRef']['subresource'] == 'token' \
            and o['verb'] in ('create',):
            # Node creating tokens for service accounts
            o['label'] = propose_label(o) # should be 17808

        # Other
        elif o['user']['username'] == 'system:serviceaccount:kube-system:kube-proxy' \
            and ('namespace' not in o['objectRef'] or o['objectRef']['namespace'] == 'kube-system') \
            and o['verb'] in ('watch',):
            # Proxy watching services, endpoints, and endpoint slices
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:serviceaccount:kube-system:coredns' \
            and 'namespace' not in o['objectRef'] \
            and o['verb'] in ('watch',) \
            and o['objectRef']['resource'] in ('services', 'namespaces', 'endpointslices'):
            o['label'] = propose_label(o)
        elif (
                (o['verb'] == 'create' and 'subresource' in o['objectRef'] and o['objectRef']['subresource'] == 'token') or
                (o['verb'] == 'get')
            ) \
            and o['objectRef']['resource'] == 'serviceaccounts' \
            and ('namespace' in o['objectRef'] and o['objectRef']['namespace'] in ('kube-system',)):
            # mapped to token creation for service accounts
            o['label'] = 17808

        if not 'label' in o or o['label'] == LABEL_UNKNOWN:
            count -= 1
            o['label'] = LABEL_UNKNOWN
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
    user_response = input().lower()
    
    # try:
    #     with open('/dev/tty') as tty:
    #         user_response = tty.readline().strip().lower()
    # except FileNotFoundError:
    #     print("Error: Could not open /dev/tty for input. Defaulting to 'n'.")
    #     user_response = 'n'
    manual_labelled = False
    if input().lower() == 'y':
        manual_labelled = True
        from log_parser import ParsingMode, parse

        old_line_count = len(newly_labelled)
        old_label_count = len([line for line in newly_labelled if json.loads(line)['label'] != LABEL_UNKNOWN])

        tmp2 = subprocess.check_output('mktemp', text=True).strip()
        with open(tmp2, 'w') as f:
            for line in newly_labelled:
                f.write(line)

        out_file = parse(ParsingMode.labelling, input_filename=tmp2)

        with open(out_file) as f:
            newly_labelled = f.readlines()

        new_line_count = len(newly_labelled)
        new_label_count = len([line for line in newly_labelled if json.loads(line)['label'] != LABEL_UNKNOWN])

        print("Total newly labelled after manual labelling: ", new_label_count)
        print(f"Amount of labels: {old_label_count} -> {new_label_count}")
        
        if len(newly_labelled) == old_line_count:
            print("All lines labelled successfully.")
        else:
            print("WARNING: Some lines have been dropped by the manual labelling process. Please check the code and rerun.")

        subprocess.run(['rm', out_file, tmp2])

out_lines = labelled + newly_labelled
out_lines.sort(key=lambda x: json.loads(x)['requestReceivedTimestamp'])

print("Total lines: ", len(out_lines))

if not manual_labelled:
    final_out_file = args.file + "_cplabel"
else:
    final_out_file = args.file + "_cplabel_mnlabel"

if os.path.exists(final_out_file):
    print("Output file already exists. Overwrite? (y/n) ", end='')
    user_response = input().lower()
    if user_response != 'y':
        tmp3 = subprocess.check_output('mktemp', text=True).strip()
        final_out_file = tmp3

with open(final_out_file, 'w') as f:
    for line in out_lines:
        f.write(line)

print("Output written to ", final_out_file)

subprocess.run(['rm', temp_file])
