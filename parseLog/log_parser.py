import json
import argparse
import re
import configparser
from enum import Enum
import label_proposer
from termcolor import colored
from common import IGNORED_NAMESPACES, LABEL_UNKNOWN, tqdm

parser = argparse.ArgumentParser(
    prog='parseLog',
    description='This program takes a log as input and removes from it unnecessary content.'
                'The output is then written to a new file.')

config = configparser.ConfigParser()

# Define sets of excluded resources.
blacklisted_requestURIs = {"/readyz", "/livez", "/api", "/apis"}

blacklisted_resources_liv2 = {"daemonsets", "deployments", "replicasets", "statefulsets", "cronjobs", "jobs"}
blacklisted_resources_liv3 = {"persistentvolumeclaims", "persistentvolumes"}
blacklisted_resources_liv4 = {"endpointslices", "ingressclasses", "ingresses", "services"}
blacklisted_resources_liv7 = {"leases", "networkpolicies", "priorityclasses", "storageclasses", "csidrivers",
                              "csinodes", "csistoragecapacities", "volumeattachments", "limitranges", "podtemplates"}
blacklisted_resources_liv9 = {"mutatingwebhookconfigurations", "validatingwebhookconfigurations", "controllerrevisions",
                              "runtimeclasses", "events"}
blacklisted_resources_liv10 = {"customresourcedefinitions", "apiservices", "tokenreviews", "horizontalpodautoscalers",
                               "flowschemas", "prioritylevelconfigurations", "poddisruptionbudgets"}
blacklisted_resources_liv20 = {"bindings", "componentstatuses", "endpoints", "replicationcontrollers"}

# Resources that we do not exclude a priori but according to the user who performs them
blacklisted_resources_user_based = {"configmaps", "clusterroles", "namespaces", "serviceaccounts", "resourcequotas",
                                    "clusterrolebindings", "rolebindings", "secrets", "nodes", "pods", "roles"}


class Decision(Enum):
    white_listed = 1
    black_listed = 2
    removed = 3


class ParsingMode(Enum):
    labelling = 1
    reduction = 2
    light_reduction = 3


def take_a_decision_about_log_line(json_data):
    request_uri = json_data.get('requestURI')

    # Blacklist Endpoints api/apis
    if request_uri in blacklisted_requestURIs \
            or 'objectRef' not in json_data \
            or request_uri == "/api/v1" or \
            bool(re.search(r"/api(s)*\?timeout", request_uri)) or \
            bool(re.search(r"/openapi/v[2-3].*$", request_uri)):
        return Decision.removed

    verb = json_data.get('verb')
    user_username = json_data.get('user').get('username')
    objectref_namespace = json_data.get('objectRef').get('namespace')
    objectref_name = json_data.get('objectRef').get('name')
    objectref_resource = json_data.get('objectRef').get('resource')

    # Remove ResponseStarted watch logs
    if config.getboolean('ignore_log', 'response_started_watch'):
        if verb == 'watch' and json_data.get('stage') == "ResponseStarted":
            return Decision.removed

    # Remove CNI and external namespaces
    if config.getboolean('ignore_log', 'cni_and_external_namespaces'):
        if objectref_namespace in IGNORED_NAMESPACES or \
                user_username == "system:serviceaccount:kube-flannel:flannel":
            return Decision.removed

    # Blacklist logs done by API Server watching objects
    if config.getboolean('ignore_log', 'api_server_watching_objects'):
        if verb == "watch" and (objectref_resource in blacklisted_resources_user_based) and \
                user_username == "system:apiserver":
            return Decision.black_listed

    # Blacklist logs done by Kube Controller Manager watching objects
    if config.getboolean('ignore_log', 'kube_controller_watching_objects'):
        if verb == "watch" and (objectref_resource in blacklisted_resources_user_based or
                                objectref_resource == "certificatesigningrequests") and \
                user_username == "system:kube-controller-manager":
            return Decision.black_listed

    # Blacklist logs done by Kube Scheduler watching objects
    if config.getboolean('ignore_log', 'kube_scheduler_watching_objects'):
        if verb == "watch" and (objectref_resource in {"pods", "nodes", "namespaces"}) and \
                user_username == "system:kube-scheduler":
            return Decision.black_listed

    # Blacklist logs done by Extension-apiserver-authentication
    if config.getboolean('ignore_log', 'extension_apiserver_authentication'):
        if verb == "watch" and objectref_resource == "configmaps" and \
                objectref_name == "extension-apiserver-authentication" and user_username == "system:kube-scheduler":
            return Decision.black_listed

    # Blacklist logs done by Nodes watching Pods and Nodes
    if config.getboolean('ignore_log', 'nodes_watching_pods_and_nodes'):
        if (verb == "watch" and (objectref_resource in {"pods", "nodes"}) and
                bool(re.search("system:node:", user_username))):
            return Decision.black_listed

    # Blacklist logs done by Nodes watching ConfigMaps
    if config.getboolean('ignore_log', 'nodes_watching_configmaps'):
        if (verb == "watch" and objectref_resource == "configmaps" and
                objectref_namespace == "kube-system" and bool(re.search("system:node:", user_username))):
            return Decision.black_listed

    # Blacklist logs done by Nodes creating tokens for SAs in the kube-system namespace
    if config.getboolean('ignore_log', 'nodes_creating_sas_token'):
        if (verb == "create" and objectref_resource == "serviceaccounts" and
                bool(re.search("system:node:", user_username)) and
                json_data.get('objectRef').get('subresource') == "token"):
            return Decision.black_listed

    # Blacklist logs done by CoreDNS watching namespaces
    if config.getboolean('ignore_log', 'coredns_watching_namespaces'):
        if (verb == "watch" and objectref_resource == "namespaces" and
                user_username == "system:serviceaccount:kube-system:coredns"):
            return Decision.black_listed

    # Blacklist logs done by Kube-proxy watching nodes
    if config.getboolean('ignore_log', 'kube_proxy_watching_nodes'):
        if (verb == "watch" and objectref_resource == "nodes" and
                user_username == 'system:serviceaccount:kube-system:kube-proxy'):
            return Decision.black_listed

    # Blacklist logs done by Nodes getting their own status
    if config.getboolean('ignore_log', 'nodes_getting_their_own_status'):
        if (verb == "get" and objectref_resource == "nodes" and
                bool(re.search("system:node:", user_username))):
            return Decision.black_listed

    # Blacklist logs done by Nodes patching their status to update conditions
    if config.getboolean('ignore_log', 'nodes_patching_their_own_status'):
        if (verb == "patch" and objectref_resource == "nodes" and
                bool(re.search("system:node:", user_username))):
            return Decision.black_listed

    # Blacklist logs done by Kube-controller-manager getting and creating tokens for GC and RQ controllers
    if config.getboolean('ignore_log', 'kube_controller_gc_and_rq_token'):
        if ((verb == "create" or verb == "get")
                and objectref_resource == "serviceaccounts" and
                user_username == "system:kube-controller-manager" and
                (objectref_name == "generic-garbage-collector" or objectref_name == "resourcequota-controller")):
            return Decision.black_listed

#     if (config.getboolean('ignore_log','blacklisted_resources_liv2') and objectref_resource in blacklisted_resources_liv2) or \
#             (config.getboolean('ignore_log','blacklisted_resources_liv3') and objectref_resource in blacklisted_resources_liv3) or \
#             (config.getboolean('ignore_log','blacklisted_resources_liv4') and objectref_resource in blacklisted_resources_liv4) or \
#             (config.getboolean('ignore_log','blacklisted_resources_liv7') and objectref_resource in blacklisted_resources_liv7) or \
#             (config.getboolean('ignore_log','blacklisted_resources_liv9') and objectref_resource in blacklisted_resources_liv9) or \
#             (config.getboolean('ignore_log','blacklisted_resources_liv10') and objectref_resource in blacklisted_resources_liv10) or \
#             (config.getboolean('ignore_log','blacklisted_resources_liv20') and objectref_resource in blacklisted_resources_liv20):
#         return Decision.white_listed

    return Decision.white_listed


def get_informative_string(json_data):
    request_uri = json_data.get('requestURI').split('?')[0]
    verb = json_data.get('verb')
    user_username = json_data.get('user').get('username')
    objectref_resource = json_data.get('objectRef').get('resource')
    objectref_name = json_data.get('objectRef').get('name')
    objectref_namespace = json_data.get('objectRef').get('namespace')
    requestReceivedTimestamp = json_data.get('requestReceivedTimestamp')

    return {
        'username': user_username,
        'verb': verb,
        'resource': objectref_resource,
        'namespace': objectref_namespace,
        'name': objectref_name,
        'requestURI': request_uri,
        'requestReceivedTimestamp': requestReceivedTimestamp
    }


def label_whitelisted_log_line(whitelisted_lines):
    previous_line = ""
    current_line = ""
    next_line = ""
    previous_label = ""

    for x in range(len(whitelisted_lines)):
        line = whitelisted_lines[x]
        if 'label' in line and line['label'] != LABEL_UNKNOWN:
            continue

        current_line = get_informative_string(line)
        if x < len(whitelisted_lines) - 1:
            next_line = get_informative_string(whitelisted_lines[x + 1])
        else:
            next_line = None

        print("\033[H\033[J")
        print(colored("previous ->", 'dark_grey'), colored(previous_line, 'dark_grey'))
        print("current -> {", end="")
        for key, value in current_line.items():
            print(f"'{key}': '", end="")
            print(colored(value, 'light_yellow', 'on_magenta', ['bold']), end="', ")
        print("}")
        print(colored("next ->", 'dark_grey'), colored(next_line, 'dark_grey'))
        print("\n")

        proposal = label_proposer.propose_label(line)
        if proposal is None:
            proposal = LABEL_UNKNOWN

        # Try proposing a label of the equivalent of the current,
        # but with the 'create' verb instead of 'watch'
        line_copy = line.copy()
        line_copy['verb'] = 'create'
        create_proposal = label_proposer.propose_label(line_copy)
        if create_proposal is None:
            create_proposal = LABEL_UNKNOWN

        print("Progress: ", x + 1, "/", len(whitelisted_lines))
        print("Labels: ")
        print("[a/ENTER] previous (default):\t", previous_label)
        print("[b]       proposed:\t\t", proposal)
        print("[c]       create equivalent:\t", create_proposal)
        print("[s]       suspend")
        print("[number]  type it directly")

        while True:
            case = input("Choose {a, b, type it, ENTER to default}: ").lower()

            match case:
                case "a":
                    input_label = previous_label
                    if previous_label is None or previous_label == "":
                        print("Previous label is empty, please choose another one")
                        continue
                case "b":
                    input_label = proposal
                case "c":
                    input_label = create_proposal
                case "s":
                    input_label = ""
                    return
                case _:
                    if case == "":
                        input_label = previous_label
                        if previous_label is None or previous_label == "":
                            print("Previous label is empty, please choose another one")
                            continue
                    else:
                        try:
                            input_label = int(case)
                            if input_label < 0:
                                print("Invalid input")
                                continue
                        except ValueError:
                            print("Invalid input")
                            continue
            break

        print()

        line['label'] = input_label # add label to json

        previous_line = current_line
        previous_label = input_label


def parse(mode: ParsingMode, input_filename: str = None):
    config.read('config.ini')

    if mode == ParsingMode.labelling:
        output_filename = input_filename + "_labelled"
    elif mode == ParsingMode.reduction:
        output_filename = input_filename + "_reduced"
    elif mode == ParsingMode.light_reduction:
        output_filename = input_filename + "_apionly"
    else:
        raise ValueError("Invalid mode")

    whitelisted_lines = []
    blacklisted_lines = []
    with (open(input_filename, 'r') as input_file):
        print("Filtering logs...")
        for line in tqdm(input_file):
            # each line is a json, load it
            json_data = json.loads(line)

            output_decision = take_a_decision_about_log_line(json_data)

            if mode == ParsingMode.labelling:
                if output_decision == Decision.white_listed:
                    whitelisted_lines.append(json_data)
                else: # in labelling we do not trash any logs
                    blacklisted_lines.append(json_data)
            elif mode == ParsingMode.reduction or mode == ParsingMode.light_reduction:
                if output_decision == Decision.white_listed:
                    whitelisted_lines.append(json_data)
                elif output_decision == Decision.black_listed:
                    blacklisted_lines.append(json_data)

    if mode == ParsingMode.labelling:
        whitelisted_lines.sort(key=lambda x: x['requestReceivedTimestamp'])
        label_whitelisted_log_line(whitelisted_lines)

        output_lines = blacklisted_lines + whitelisted_lines
    elif mode == ParsingMode.reduction:
        output_lines = whitelisted_lines
    elif mode == ParsingMode.light_reduction:
        output_lines = whitelisted_lines + blacklisted_lines

    # sort the output_lines array by the requestReceivedTimestamp
    output_lines.sort(key=lambda x: x['requestReceivedTimestamp'])

    with open(output_filename, 'w') as output_file:
        for line in output_lines:
            output_file.write(json.dumps(line, separators=(',', ':')) + "\n")

    return output_filename


if __name__ == "__main__":
    parser.add_argument('-f', required=True, help='The log input file')

    action = parser.add_mutually_exclusive_group()
    action.add_argument('--labelling', required=False,
                        help='Labelling mode: interactive labelling of the log file',
                        action='store_true', default=False)
    action.add_argument('--reduction', required=False,
                        help='Reduction mode: remove unnecessary content and blacklisted logs',
                        action='store_true', default=False)
    action.add_argument('--light-reduction', required=False,
                        help='Light reduction mode: take out unnecessary content only',
                        action='store_true', default=False)

    args = parser.parse_args()

    if sum([args.labelling, args.reduction, args.light_reduction]) != 1:
        parser.print_help()
        exit(1)

    if args.labelling:
        mode = ParsingMode.labelling
    elif args.reduction:
        mode = ParsingMode.reduction
    elif args.light_reduction:
        mode = ParsingMode.light_reduction
    else:
        raise ValueError("Invalid mode")

    output_file = parse(mode=mode, input_filename=args.f)

    print(f"Output written to {output_file}")
