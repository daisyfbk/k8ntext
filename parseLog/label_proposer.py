import csv
import json
import functools
import argparse

LABELS_FILE = 'labels.csv'
VERBS_FILE = 'verbs.csv'
IGNORED_NAMESPACES = ['kube-flannel', 'falco']

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


def generate_label(verb: str, objectRef: dict) -> int:
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

    return encode_label(label[0], label[1], is_namespaced, is_single_object, verb_label)


@functools.lru_cache(maxsize=None)
def encode_label(
    label_id: int,
    label_sub_id: int,
    is_namespaced: int,
    is_single_object: int,
    verb_id: int
) -> int:
    label = (label_id << 8) | (label_sub_id << 5) | (is_namespaced << 4) | (is_single_object << 3) | verb_id
    label = label << 4

    return label


@functools.lru_cache(maxsize=None)
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


def brute_force_label_space():
    for label_id in range(256):
        for label_sub_id in range(8):
            for is_namespaced in range(2):
                for is_single_object in range(2):
                    for verb_id in range(8):
                        try:
                            label = encode_label(label_id, label_sub_id, is_namespaced, is_single_object, verb_id)
                            decoded = decode_label(label)
                            if decoded != "Unknown label":
                                print(f"Label: {label}, {bin(label)}")
                                print(f"Meaning: verb {decoded['verb']} on {decoded['apiGroup']}/{decoded['version']}/{decoded['uri']}; resource is {'namespaced' if decoded['is_namespaced'] else 'not namespaced'}; {'single object' if decoded['is_single_object'] else 'list of objects'}")
                        except:
                            continue


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
    from main import get_informative_string

    parser = argparse.ArgumentParser(
    prog='propose_label',
    description='Manage automated labels')
    parser.add_argument('--brute-force', action='store_true', help='Brute force the label space')

    parser.add_argument("-f", "--file", help="File to read from", type=str)
    parser.add_argument("-e", "--encode", help="Encode a label", action='store_true')

    parser.add_argument("-d", "--decode", help="Decode a label", action='store_true')
    parser.add_argument("-l", "--label", help="Label to decode", type=int)

    args = parser.parse_args()
    if args.brute_force:
        brute_force_label_space()
        exit(0)
    else:
        if args.encode:
            if not args.file:
                print("Please provide a file to read from")
                exit(1)

            with open(args.file, 'r') as f:
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
        elif args.decode:
            if not args.label:
                print("Please provide a label to decode")
                exit(1)
            decoded = decode_label(int(args.label))
            print(f"{args.label} -> {decoded['apiGroup']}/{decoded['version']}/{decoded['uri']} {decoded['verb']}")
            
        else:
            parser.print_help()