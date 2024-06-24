# jq -c 'select(.user.username=="system:serviceaccount:kube-system:namespace-controller")' woutlabel | jq ".label = 41376"

import json
from label_proposer import propose_label

# missing code for splitting the log file into woutlabel and withlabel

out_lines = []
with open('woutlabel') as f:
    lines = f.readlines()
    for line in lines:
        o = json.loads(line)
        if 'objectRef' in o and o['objectRef']["resource"] == 'leases' \
            and o['verb'] in ('get', 'update'):
            o['label'] = 119232
        if o['user']['username'] == 'system:serviceaccount:kube-system:namespace-controller':
            o['label'] = 41376
        elif o['user']['username'] == 'system:apiserver' \
            and o['verb'] == 'watch' \
            and (not 'namespace' in o['objectRef'] or o['objectRef']['namespace'] == None):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:kube-controller-manager' \
            and o['verb'] == 'watch' \
            and (not 'namespace' in o['objectRef'] or o['objectRef']['namespace'] == None):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:kube-scheduler' \
            and o['verb'] == 'watch' \
            and (not 'namespace' in o['objectRef'] or o['objectRef']['namespace'] == None):
            o['label'] = propose_label(o)
        elif o['user']['username'] == 'system:kube-scheduler' \
            and o['verb'] == 'create' \
            and o['objectRef']['resource'] == 'events':
            o['label'] = 4496
        elif o['user']['username'] == 'system:kube-controller-manager' \
            and o['verb'] in ('get', 'create') \
            and o['objectRef']['resource'] == 'serviceaccounts':
            o['label'] = 17808
        elif "system:nodes" in o['user']['groups'] and \
            o['verb'] in ('create',) and \
            o['objectRef']['resource'] == 'events':
            if o['requestObject']['involvedObject']['kind'] == 'Pod':
                o['label'] = 4496
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('get',) and \
            o['objectRef']['resource'] == 'nodes':
            o['label'] = 61616
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('patch',) and \
            o['objectRef']['resource'] == 'nodes':
            o['label'] = 62144
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('create',) and \
            o['objectRef']['resource'] == 'serviceaccounts' and \
            o['objectRef']['subresource'] == 'token':
            o['label'] = propose_label(o)
        elif 'system:nodes' in o['user']['groups'] and \
            o['verb'] in ('patch', 'get') and \
            o['objectRef']['resource'] == 'pods':
            o['label'] = 4496
        else:
            o['label'] = propose_label(o)

        if o['label'] is None:
            o['label'] = -2
        
        out_lines.append(json.dumps(o, separators=(',', ':')) + '\n')

print("Total labelled lines: ", len(out_lines))

with open('withlabel', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        out_lines.append(line)

    print("Total already labeled: ", len(lines))

out_lines.sort(key=lambda x: json.loads(x)['requestReceivedTimestamp'])

print("Total lines: ", len(out_lines))

with open('result', 'w') as f:
    for line in out_lines:
        f.write(line)