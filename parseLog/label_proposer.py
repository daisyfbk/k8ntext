import argparse
import csv
import functools
import json

from common import IGNORED_NAMESPACES, LABEL_UNKNOWN, LABEL_IGNORE

LABELS_FILE = 'labels.csv'
VERBS_FILE = 'verbs.csv'


def load_labels():
    __labels = {}
    __available_verbs = {}
    __namespaced_labels = {}
    __seen_apigroups = set()

    with open(LABELS_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0].startswith('#'):
                continue
            apigroup, version, uri, __id, sub_id, *rest = row
            __seen_apigroups.add(apigroup)

            namespaced, *rest = rest
            if namespaced == 'true':
                __namespaced_labels[(apigroup, version, uri)] = True
            else:
                __namespaced_labels[(apigroup, version, uri)] = False

            local_available_verbs = set(rest)

            if '' in local_available_verbs:
                local_available_verbs.remove('')

            if (apigroup, version, uri) in __labels:
                raise ValueError(
                    f"Duplicate entry for {apigroup}/{version}/{uri}: {__labels[(apigroup, version, uri)]}")
            if (int(__id), int(sub_id)) in set(__labels.values()):
                raise ValueError(f"Duplicate entry for {apigroup}/{version}/{uri}: {__id}, {sub_id}")

            __available_verbs[(apigroup, version, uri)] = local_available_verbs
            __labels[(apigroup, version, uri)] = (int(__id), int(sub_id))

    return __labels, __available_verbs, __namespaced_labels, __seen_apigroups


def load_verbs():
    __verbs = {}
    with open(VERBS_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0].startswith('#'):
                continue
            verb, __id = row
            __verbs[verb] = int(__id)
    return __verbs


labels, available_verbs, namespaced_labels, seen_apigroups = load_labels()
verbs = load_verbs()

EXTERNAL_CRD = {
    "apiGroup": "unknown.fbk.eu",
    "apiVersion": "noversion",
    "resource": "externalcrd",
    "no_namespace": (666, 0),
    "namespaced": (667, 0),
}


def label_is_crd(label: int) -> bool:
    label_id = (label & 0b1111111111000000000000) >> 12
    return label_id in (EXTERNAL_CRD["no_namespace"][0], EXTERNAL_CRD["namespaced"][0])


def generate_label(verb: str, objectRef: dict) -> int:
    apiGroup = objectRef['apiGroup']
    apiVersion = objectRef['apiVersion']
    resource = objectRef['resource']

    if "subresource" in objectRef and objectRef["subresource"]:
        resource = resource + "/" + objectRef["subresource"]

    if apiGroup not in seen_apigroups:
        apiGroup = EXTERNAL_CRD["apiGroup"]
        apiVersion = EXTERNAL_CRD["apiVersion"]
        resource = EXTERNAL_CRD["resource"]

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

    # print(bin(label[0]), ", ", bin(label[1]), ", ",
    # bin(is_namespaced), ", ", bin(is_single_object), ", ", bin(verb_label))

    is_allowed, _ = validate_operation(apiGroup, apiVersion, resource, verb, is_namespaced == 1)
    if not is_allowed:
        raise KeyError(f"Operation {verb} on {apiGroup}/{apiVersion}/{resource} is not allowed")

    return encode_label(label[0], label[1], is_namespaced, is_single_object, verb_label)


@functools.lru_cache(maxsize=None)
def encode_label(
        label_id: int,
        label_sub_id: int,
        is_namespaced: int,
        is_single_object: int,
        verb_id: int,
) -> int:
    """
    We use 22 bits to encode the label
    A First 10 bits: type (at most 1024 types, I expect 100-200 types, upper range is for less important types)
    B Next 3 bits: sub-type (at most 15 sub-types, I expect 1-2 sub-types per type)
    C Next bit: is the resource namespaced
    D Next bit: is it querying a single object or a list of objects? check if objectRef.name exists
    E Next 3 bits: verb (there are only 8 verbs)
    F Remaining 4 bits: variations (let's keep ample space for variations)
    """

    if label_sub_id >= 2 ** 3 and label_sub_id < 2 ** 5:
        # put the two least significant bits of label_sub_id into the alternate field
        alternate = label_sub_id & 0b11000
        alternate >>= 3
        label_sub_id &= 0b00111
    else:
        alternate = 0

    label = (label_id << 8) | (label_sub_id << 5) | (is_namespaced << 4) | (is_single_object << 3) | verb_id
    label <<= 4
    label |= alternate

    return label


@functools.lru_cache(maxsize=None)
def decode_label(label: int, as_string: bool = False) -> dict | str:
    if label == LABEL_IGNORE:
        return {"error": "Label is ignored"} if not as_string else f"Label is ignored"
    if label == LABEL_UNKNOWN:
        return {"error": "Label is unknown"} if not as_string else f"Label is unknown"

    label_id = (label & 0b1111111111000000000000) >> 12
    label_sub_id = (label & 0b0000000000111000000000) >> 9
    is_namespaced = (label & 0b0000000000000100000000) >> 8
    is_single_object = (label & 0b0000000000000010000000) >> 7
    verb_id = (label & 0b0000000000000001110000) >> 4
    alternate = (label & 0b0000000000000000001111)

    if alternate > 0:
        alternate <<= 3
        label_sub_id |= alternate
        alternate = 0

    try:
        key = [k for k, v in labels.items() if v == (label_id, label_sub_id)][0]
    except IndexError as e:
        return {"error": "Label cannot be decoded",
                "reason": e} if not as_string else f"Label cannot be decoded ({label})"

    apigroup, version, uri = key

    verb = [k for k, v in verbs.items() if v == verb_id][0]

    # print("Raw: ", label, "Label ID: ", label_id, "Sub ID: ", label_sub_id, "is_namespaced: ", is_namespaced, 
    #       "is_single_object: ", is_single_object, "verb_id: ", verb_id, "verb: ", verb)

    if as_string:
        return f"{verb} {apigroup}/{version}/{uri} {'(ns)' if is_namespaced else ''} {'(single)' if is_single_object else '(list)'}".replace(
            "  ", " ")
    else:
        return {
            "apiGroup": apigroup,
            "version": version,
            "uri": uri,
            "is_namespaced": is_namespaced == 1,
            "is_single_object": is_single_object == 1,
            "verb": verb,
            "raw": {
                "label_id": label_id,
                "label_sub_id": label_sub_id,
                "is_namespaced": is_namespaced,
                "is_single_object": is_single_object,
                "verb_id": verb_id,
                "alternate": alternate
            },
        }


def validate_operation(
        apiGroup: str,
        version: str,
        uri: str,
        verb: str,
        is_namespaced: bool,
) -> tuple[bool, str]:
    allowed_operation = False
    match verb:
        case "get" | "list":
            allowed_operation = (
                    "list" in available_verbs[(apiGroup, version, uri)]
                    or "get" in available_verbs[(apiGroup, version, uri)]
            )
            verb = "get/list"
        case "create":
            allowed_operation = "create" in available_verbs[(apiGroup, version, uri)]
        case "update" | "patch":
            allowed_operation = (
                    "update" in available_verbs[(apiGroup, version, uri)]
                    or "patch" in available_verbs[(apiGroup, version, uri)]
            )
            verb = "update/patch"
        case "delete" | "deletecollection":
            allowed_operation = (
                    "delete" in available_verbs[(apiGroup, version, uri)]
                    or "deletecollection" in available_verbs[(apiGroup, version, uri)]
            )
            verb = "delete/deletecollection"
        case "watch":
            allowed_operation = "watch" in available_verbs[(apiGroup, version, uri)]
        case _:
            raise ValueError(f"Unknown verb: {verb}")

    # if verb not in ("watch", "get/list"):
    #     allowed_operation = allowed_operation and is_namespaced == namespaced_labels[(apiGroup, version, uri)]

    return allowed_operation, verb


def brute_force_label_space(print_result: bool = True) -> list[int]:
    labels = []
    for label_id in range(2 ** 10):
        for label_sub_id in range(11):
            for is_namespaced in range(2):
                for is_single_object in range(2):
                    for verb_id in range(8):
                        try:
                            label = encode_label(label_id, label_sub_id, is_namespaced, is_single_object, verb_id)
                            decoded = decode_label(label)

                            verb = decoded['verb']
                            apiGroup = decoded['apiGroup']
                            version = decoded['version']
                            uri = decoded['uri']
                            is_namespaced = decoded['is_namespaced']

                            allowed_operation, verb = validate_operation(apiGroup, version, uri, verb, is_namespaced)

                            if "error" not in decoded and allowed_operation:
                                if print_result:
                                    decoded_str = decode_label(label, as_string=True)
                                    print(label, decoded_str)
                                labels.append(label)
                        except Exception as e:
                            continue

    return labels + [LABEL_UNKNOWN]


def propose_label(j: dict) -> int:
    uri = j['requestURI']

    try:
        objectRef: dict = j['objectRef']
    except KeyError:
        return LABEL_UNKNOWN

    verb = j['verb']

    uri = uri.split('?')[0]
    uri = uri[1:]
    uri = uri.split('/')

    if uri[0] not in ['api', 'apis']:
        # Not an API request
        return LABEL_IGNORE

    if len(uri) <= 2:
        # Probably a request to list all APIs
        # print("Ignoring request to list all APIs")
        return LABEL_IGNORE

    if "namespace" not in objectRef:
        objectRef["namespace"] = None

    if objectRef["namespace"] in IGNORED_NAMESPACES:
        # Ignore requests to some namespaces (they will be flagged
        # as control plane traffic for the moment)
        # print("Ignoring namespace: ", objectRef["namespace"])
        return LABEL_IGNORE

    if "apiGroup" not in objectRef:
        # We tagget the "" apiGroup as core
        objectRef["apiGroup"] = "core"

    try:
        label = generate_label(verb, objectRef)
        # print("Label: ", label)
        # print("Binary: ", format(label, '020b'))
    except KeyError as e:
        # print("KeyError: ", e)
        return LABEL_UNKNOWN

    return label


def main(args):
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

                    if label in [LABEL_IGNORE, LABEL_UNKNOWN]:
                        continue
                    try:
                        # print(bin(label))
                        infstr = get_informative_dict(j)
                        infstr['label'] = label
                        print(json.dumps(infstr))
                    except Exception as e:
                        raise ValueError(f"Error while processing: {j}; {e}")
        elif args.decode:
            if not args.label:
                print("Please provide a label to decode")
                exit(1)
            decoded = decode_label(int(args.label), as_string=True)
            print(args.label, decoded)

        else:
            parser.print_help()


if __name__ == '__main__':
    from log_parser import get_informative_dict

    parser = argparse.ArgumentParser(
        prog='propose_label',
        description='Manage automated labels')
    parser.add_argument('--brute-force', action='store_true', help='Brute force the label space')

    parser.add_argument("-f", "--file", help="File to read from", type=str)
    parser.add_argument("-e", "--encode", help="Encode a label", action='store_true')

    parser.add_argument("-d", "--decode", help="Decode a label", action='store_true')
    parser.add_argument("-l", "--label", help="Label to decode", type=int)

    args = parser.parse_args()

    main(args)
