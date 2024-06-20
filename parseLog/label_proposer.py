import csv
import json

LABELS_FILE = 'labels.csv'
VERBS_FILE = 'verbs.csv'
IGNORED_NAMESPACES = ['kube-system', 'kube-public', 'kube-node-lease', 'kube-flannel', 'falco']

def load_labels():
    labels = {}
    with open(LABELS_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0].startswith('#'):
                continue
            apigroup, version, uri, __id, sub_id = row
            labels[(apigroup, version, uri)] = (int(__id), int(sub_id))
    return labels


def load_verbs():
    verbs = {}
    with open(VERBS_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0].startswith('#'):
                continue
            verb, __id = row
            verbs[verb] = int(__id)
    return verbs

labels = load_labels()
verbs = load_verbs()


def generate_label(verb: str, objectRef: dict):
    """
    We use 20 bits to encode the label
    A First 8 bits: type (at most 255 types, I expect less than 100 types in total)
    B Next 3 bits: sub-type (at most 15 sub-types, I expect 1-2 sub-types per type)
    C Next bit: is the resource namespaced
    D Next bit: is it querying a single object or a list of objects? check if objectRef.name exists
    E Next 3 bits: verb (there are only 8 verbs)
    F Remaining 4 bits: variations (let's keep ample space for variations)
    """

    apiGroup = objectRef['apiGroup']
    apiVersion = objectRef['apiVersion']
    resource = objectRef['resource']

    if "subresource" in objectRef and objectRef["subresource"]:
        resource = resource + "/" + objectRef["subresource"]

    label = labels[(apiGroup, apiVersion, resource)]
    verb_label = verbs[verb]

    if "namespace" in objectRef and objectRef["namespace"]:
        is_namespaced = 1
    else:
        is_namespaced = 0

    if "name" in objectRef and objectRef["name"]:
        is_single_object = 1
    else:
        is_single_object = 0

    # print(bin(label[0]), ", ", bin(label[1]), ", ", bin(is_namespaced), ", ", bin(is_single_object), ", ", bin(verb_label))

    label = (label[0] << 8) | (label[1] << 5) | (is_namespaced << 4) | (is_single_object << 3) | verb_label
    label = label << 4

    return label


def decode_label(label: int):
    if label == -1:
        return "Unknown label"

    label_id = (label >> 12) & 0xFF
    label_sub_id = (label >> 9) & 0x7
    is_namespaced = (label >> 8) & 0x1
    is_single_object = (label >> 7) & 0x1
    verb_id = (label >> 4) & 0x7

    # print(bin(label_id), ", ", bin(label_sub_id), ", ", bin(is_namespaced), ", ", bin(is_single_object), ", ", bin(verb_id))

    key = [k for k, v in labels.items() if v == (label_id, label_sub_id)][0]
    apigroup, version, uri = key

    verb = [k for k, v in verbs.items() if v == verb_id][0]

    return {
        "apiGroup": apigroup,
        "version": version,
        "uri": uri,
        "label_id": label_id,
        "label_sub_id": label_sub_id,
        "is_namespaced": is_namespaced,
        "is_single_object": is_single_object,
        "verb": verb,
        "verb_id": verb_id
    }


def propose_label(j: dict):
    uri = j['requestURI']

    try:
        objectRef = j['objectRef']
    except KeyError:
        objectRef = None

    verb = j['verb']

    uri = uri.split('?')[0]
    uri = uri[1:]
    uri = uri.split('/')

    if uri[0] not in ['api', 'apis']:
        # Not an API request
        return None

    if len(uri) <= 2:
        # Probably a request to list all APIs
        return None

    if "namespace" not in objectRef:
        objectRef["namespace"] = None
    
    if objectRef["namespace"] in IGNORED_NAMESPACES:
        # Ignore requests to some namespaces (they will be flagged
        # as control plane traffic for the moment)
        return None
    
    if "apiGroup" not in objectRef:
        # We tagget the "" apiGroup as core
        objectRef["apiGroup"] = "core"

    try:
        label = generate_label(verb, objectRef)
        # print("Label: ", label)
        # print("Binary: ", format(label, '020b'))
    except KeyError:
        return None

    return label


if __name__ == '__main__':
    import sys
    from main import get_informative_string

    file = sys.argv[1]
    with open(file, 'r') as f:
        for line in f:
            j = json.loads(line)
            label = propose_label(j)

            if label is None:
                continue
            try:
                # print(bin(label))
                print(f"{label} <- {get_informative_string(j)}")
            except:
                pass

            # undecoded = decode_label(label)
            # uri = undecoded["apiGroup"] + "/" + undecoded["version"] + "/" + undecoded["uri"]
            # print(f"{label} -> {uri} {undecoded['verb']}")