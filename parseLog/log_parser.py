import argparse
import configparser
import datetime
import json
import re
import subprocess
from enum import Enum
from typing import Optional

from termcolor import colored

import label_proposer
from common import IGNORED_NAMESPACES, LABEL_UNKNOWN, exists_subkey
from support.log import tqdm

parser = argparse.ArgumentParser(
    prog='parseLog',
    description='This program takes a log as input and removes from it unnecessary content.'
                'The output is then written to a new file.')

config = configparser.ConfigParser()

# Define sets of excluded resources.
blacklisted_requestURIs = {"/readyz", "/livez", "/api", "/apis"}

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

    if json_data.get('stage') != "ResponseComplete":
        return Decision.removed

    # Remove ResponseStarted watch logs
    if config.getboolean('ignore_log', 'response_started_watch'):
        if verb != 'watch' and json_data.get('stage') == "ResponseStarted":
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

    return Decision.white_listed


def get_informative_dict(json_data):
    request_uri = json_data.get('requestURI').split('?')[0]
    verb = json_data.get('verb')
    user_username = json_data.get('user').get('username')
    if json_data.get('objectRef') is not None:
        objectref_resource = json_data.get('objectRef').get('resource')
        objectref_subresource = json_data.get('objectRef').get('subresource')
        objectref_name = json_data.get('objectRef').get('name')
        objectref_namespace = json_data.get('objectRef').get('namespace')
    else:
        raise ValueError(
            "Attempted to get objectRef from a log line without objectRef. Did you light-reduce the logs?")

    request_received_timestamp = json_data.get('requestReceivedTimestamp')
    stage_timestamp = json_data.get('stageTimestamp')

    res = {
        'username': user_username,
        'verb': verb,
        'resource': objectref_resource,
        'subresource': objectref_subresource,
        'namespace': objectref_namespace,
        'name': objectref_name,
        'requestURI': request_uri,
        'requestReceivedTimestamp': request_received_timestamp,
        'stageTimestamp': stage_timestamp
    }

    # ownerReference
    if exists_subkey(json_data, 'responseObject', 'metadata', 'ownerReferences'):
        owner_references = json_data.get('responseObject').get(
            'metadata').get('ownerReferences')
        res['ownerReferences'] = owner_references

    if exists_subkey(json_data, 'responseObject', 'involvedObject'):
        involved_object = json_data.get('responseObject').get('involvedObject')
        if 'uid' in involved_object:
            del involved_object['uid']
        res['involvedObject'] = involved_object

    if exists_subkey(json_data, 'responseObject', 'spec', 'claimRef'):
        claim_ref = json_data.get('responseObject').get('spec').get('claimRef')
        res['claimRef'] = claim_ref

    if exists_subkey(json_data, 'responseObject', 'reason'):
        reason = json_data.get('responseObject').get('reason')
        res['reason'] = reason

    if exists_subkey(json_data, 'responseObject', 'metadata'):
        metadata = json_data.get('responseObject').get('metadata')
        if metadata.get('uid') is not None:
            res['metadata/uid'] = metadata.get('uid')

    return res


def label_whitelisted_log_line(whitelisted_lines):
    previous_line = ""
    current_line = ""
    next_line = ""
    previous_label = ""

    temporary_backup_filename = subprocess.check_output(
        "mktemp", shell=True).decode().strip()

    for x in range(len(whitelisted_lines)):
        line = whitelisted_lines[x]
        if 'label' in line and line['label'] != LABEL_UNKNOWN:
            continue

        current_line = get_informative_dict(line)
        if x < len(whitelisted_lines) - 1:
            next_line = get_informative_dict(whitelisted_lines[x + 1])
        else:
            next_line = None

        print("\033[H\033[J")
        print(colored("previous ->", 'dark_grey'),
              colored(previous_line, 'dark_grey'))
        print("current -> {", end="")
        for key, value in current_line.items():
            print(f"'{key}': '", end="")
            print(colored(value, 'light_yellow',
                          'on_magenta', ['bold']), end="', ")
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

        # Do the same with delete
        line_copy['verb'] = 'delete'
        delete_proposal = label_proposer.propose_label(line_copy)
        if delete_proposal is None:
            delete_proposal = LABEL_UNKNOWN

        # Also with watch
        line_copy['verb'] = 'watch'
        watch_proposal = label_proposer.propose_label(line_copy)
        if watch_proposal is None:
            watch_proposal = LABEL_UNKNOWN

        # Also with patch
        line_copy['verb'] = 'patch'
        patch_proposal = label_proposer.propose_label(line_copy)
        if patch_proposal is None:
            patch_proposal = LABEL_UNKNOWN

        next_watch = LABEL_UNKNOWN
        next_watch_info = ""
        for i in range(1, min(20, len(whitelisted_lines) - x)):
            next_line = get_informative_dict(whitelisted_lines[x + i])
            if next_line['verb'] == 'watch':
                next_watch = label_proposer.propose_label(
                    whitelisted_lines[x + i])
                next_watch_info += f" after {i} lines, "
                next_watch_info += f"{{'verb': '{next_line['verb']}', 'resource': '{next_line['resource']}'}}"
                break

        next_create = LABEL_UNKNOWN
        next_create_info = ""
        for i in range(1, min(20, len(whitelisted_lines) - x)):
            next_line = get_informative_dict(whitelisted_lines[x + i])
            if next_line['verb'] == 'create':
                next_create = label_proposer.propose_label(
                    whitelisted_lines[x + i])
                next_create_info += f" after {i} lines, "
                next_create_info += f"{{'verb': '{next_line['verb']}', 'resource': '{next_line['resource']}'}}"
                break

        next_patch = LABEL_UNKNOWN
        next_patch_info = ""
        for i in range(1, min(20, len(whitelisted_lines) - x)):
            next_line = get_informative_dict(whitelisted_lines[x + i])
            if next_line['verb'] in ('patch', 'update'):
                next_patch = label_proposer.propose_label(
                    whitelisted_lines[x + i])
                next_patch_info += f" after {i} lines, "
                next_patch_info += f"{{'verb': '{next_line['verb']}', 'resource': '{next_line['resource']}'}}"
                break

        next_delete = LABEL_UNKNOWN
        next_delete_info = ""
        for i in range(1, min(20, len(whitelisted_lines) - x)):
            next_line = get_informative_dict(whitelisted_lines[x + i])
            if next_line['verb'] in ('delete', 'deletecollection'):
                next_delete = label_proposer.propose_label(
                    whitelisted_lines[x + i])
                next_delete_info += f" after {i} lines, "
                next_delete_info += f"{{'verb': '{next_line['verb']}', 'resource': '{next_line['resource']}'}}"
                break

        next_noncp_action = LABEL_UNKNOWN
        next_noncp_action_info = ""
        for i in range(1, min(40, len(whitelisted_lines) - x)):
            if 'cplabel' in whitelisted_lines[x + i] and whitelisted_lines[x + i]['cplabel']:
                continue
            next_line = get_informative_dict(whitelisted_lines[x + i])
            username = next_line['username']
            if username.startswith("system:"):
                continue
            next_noncp_action = label_proposer.propose_label(
                whitelisted_lines[x + i])
            next_noncp_action_info += f" after {i} lines, "
            next_noncp_action_info += f"{{'verb': '{next_line['verb']}', 'resource': '{next_line['resource']}'}}"
            break

        # Delta of the previous and next 5 lines
        # for the user to have a better context
        deltas = []

        def parse_ts(ts1, ts2):
            return f"{abs(datetime.datetime.strptime(ts1, '%Y-%m-%dT%H:%M:%S.%fZ') - datetime.datetime.strptime(ts2, '%Y-%m-%dT%H:%M:%S.%fZ'))} {ts1}"

        if x >= 0:
            deltas.append(parse_ts(whitelisted_lines[x - 1]['requestReceivedTimestamp'],
                                   current_line['requestReceivedTimestamp']))
        else:
            deltas.append("-")

        for i in range(1, min(5, len(whitelisted_lines) - x)):
            ai = whitelisted_lines[x + i]['requestReceivedTimestamp']
            deltas.append(
                parse_ts(ai, current_line['requestReceivedTimestamp']))
        for i in range(min(5, len(whitelisted_lines) - x), 5):
            deltas.append("-")

        print(f"\t({x - 1}) {deltas[0]}")
        print(colored(f"De   -> ({x}) 0:00:00.000000 {current_line['requestReceivedTimestamp']}\n", 'light_yellow',
                      'on_magenta', ['bold']), end='  ')
        for i in range(1, 5):
            print(f"\t({x + i}) {deltas[i]}")
        print()

        print("Progress: ", x + 1, "/", len(whitelisted_lines))
        print("Last 5 labels: ", [x['label']
                                  for x in whitelisted_lines[x - min(5, x):x]])
        print()

        print("Labels: ")
        print("[a/ENTER] previous (default):\t", previous_label)
        print("[b]       proposed:\t\t", proposal)
        print("[nc]      next create:\t\t", next_create, next_create_info)
        print("[nw]      next watch:\t\t", next_watch, next_watch_info)
        print("[np]      next patch:\t\t", next_patch, next_patch_info)
        print("[nd]      next delete:\t\t", next_delete, next_delete_info)
        print("[ec]      equivalent create:\t", create_proposal)
        print("[ew]      equivalent watch:\t", watch_proposal)
        print("[ep]      equivalent patch:\t", patch_proposal)
        print("[ed]      equivalent delete:\t", delete_proposal)
        print("[m]       next non-cp action:\t",
              next_noncp_action, next_noncp_action_info)
        print("[s]       skip")
        print("[q]       quit")
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
                case "nc":
                    input_label = next_create
                case "nw":
                    input_label = next_watch
                case "np":
                    input_label = next_patch
                case "nd":
                    input_label = next_delete
                case "ec":
                    input_label = create_proposal
                case "ew":
                    input_label = watch_proposal
                case "ep":
                    input_label = patch_proposal
                case "ed":
                    input_label = delete_proposal
                case "m":
                    input_label = next_noncp_action
                case "s":
                    input_label = LABEL_UNKNOWN
                case "q":
                    print("Quitting...")
                    input_label = ""
                    return
                case _:
                    if case == "":
                        input_label = previous_label
                        if previous_label is None or previous_label == "":
                            print(
                                "Previous label is empty, please choose another one")
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

        if input_label is None or input_label == "":
            print("Invalid input, putting default label")
            input_label = previous_label

        line['label'] = input_label  # add label to json
        with open(temporary_backup_filename, 'a') as temp_file:
            temp_file.write(json.dumps(line, separators=(',', ':')) + "\n")

        previous_line = current_line
        previous_label = input_label


def parse(mode: ParsingMode, input_filename: Optional[str] = None):
    config.read('config/config.ini')

    if input_filename is None:
        raise ValueError("Input filename is required")

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
                else:  # in labelling we do not trash any logs
                    blacklisted_lines.append(json_data)
            elif mode == ParsingMode.reduction or mode == ParsingMode.light_reduction:
                if output_decision == Decision.white_listed:
                    whitelisted_lines.append(json_data)
                elif output_decision == Decision.black_listed:
                    blacklisted_lines.append(json_data)

    if mode == ParsingMode.labelling:
        whitelisted_lines.sort(key=lambda x: x['requestReceivedTimestamp'])
        # Filter out lines already labelled
        whitelisted_already_labelled = [
            x for x in whitelisted_lines if 'label' in x and x['label'] != LABEL_UNKNOWN]
        whitelisted_to_label = [
            x for x in whitelisted_lines if 'label' not in x or x['label'] == LABEL_UNKNOWN]

        label_whitelisted_log_line(whitelisted_to_label)
        whitelisted_lines = whitelisted_already_labelled + whitelisted_to_label

        output_lines = blacklisted_lines + whitelisted_lines
    elif mode == ParsingMode.reduction:
        output_lines = whitelisted_lines
    elif mode == ParsingMode.light_reduction:
        output_lines = whitelisted_lines + blacklisted_lines
    else:
        raise ValueError("Invalid mode.")

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
