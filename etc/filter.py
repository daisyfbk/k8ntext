import json
import sys

def filter_json_lines(paths):
    for line in sys.stdin:
        try:
            json_obj = json.loads(line)
            uri = json_obj.get('requestURI')
            path, *rest = uri.split('?')
            if path in paths:
                continue
            print(json_obj)
        except json.JSONDecodeError:
            print(f"Unable to parse line: {line}")

paths = ['/readyz', '/healthz',
         '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-scheduler',
         '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-controller-manager'
]
filter_json_lines(paths)