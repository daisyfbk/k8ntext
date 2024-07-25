IGNORED_NAMESPACES = {
    "falco",
    "kube-flannel"
}
LABEL_UNKNOWN = -1
LABEL_IGNORE = -2


def exists_subkey(__object, *keys):
    exists = True
    for key in keys:
        if key not in __object:
            exists = False
            break
        __object = __object[key]

    return exists

def flatten_object(_object: dict) -> dict:
    keys = _object.keys()
    queue = []
    for k in keys:
        queue.append((k, _object[k]))

    res = {}
    while len(queue) > 0:
        k, v = queue.pop(0)
        if isinstance(v, dict):
            for k2, v2 in v.items():
                queue.append((f"{k}.{k2}", v2))
            continue
        elif isinstance(v, list):
            for i, v2 in enumerate(v):
                queue.append((f"{k}[{i}]", v2))
            continue
        else:
            res[k] = v

    return res
