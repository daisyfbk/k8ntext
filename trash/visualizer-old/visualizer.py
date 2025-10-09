import json
import argparse
import csv
import uuid
from datetime import datetime
from label_proposer import decode_label
from log_parser import get_informative_dict
from visualizer_graph import AuditGraph
from termcolor import colored
from common import LABEL_UNKNOWN, LABEL_IGNORE

ACTION_KEY_SEPARATOR = "%"
UUID = "UUID"
DEFAULT_LABEL_KEY = "label"
BASE_LABEL = "1010"
CONTROL_PLANE_UUID = [
    str(i) for i in range(2000, 2030)
]

# Cluster limits
DEFAULT_CLUSTER_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_CLUSTER_MAX_LINES = 1000
TIMESTAMP_KEY = "requestReceivedTimestamp"


# This function returns two dictionary:
# 1) actions_dict: the dictionary that contains the single actions performed with their corresponding informative_dict
# 2) dict_divided_by_label: a dictionary that contains all the informative_dict grouped by label
def get_actions_and_labels_dicts(input_filename,
                                 label_key=DEFAULT_LABEL_KEY):
    verbs_dict = {}
    with open('verbs.csv', 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            verbs_dict[row.get('#verb')] = row.get('id')

    actions_dict = {}
    dict_divided_by_label = {}

    with (open(input_filename, 'r') as input_file):
        line_index = 0

        for line in input_file:
            line_index += 1
            # each line is a json, load it
            json_data = json.loads(line)
            if label_key not in json_data:
                print("At line", line_index, "label key not found in json data; ignoring line")
                continue
            if json_data.get(label_key) is None:
                print("At line", line_index, "label key is None; ignoring line")
                continue

            label = json_data.get(label_key)

            if label != LABEL_UNKNOWN and label != LABEL_IGNORE:
                informative_dict = get_informative_dict(json_data)
                informative_dict.pop('requestURI', None)
                informative_dict.pop('requestReceivedTimestamp', None)

                informative_dict['line_index'] = line_index  # add line index to add uuid later

                # add line dict_divided_by_label
                if label not in dict_divided_by_label:
                    dict_divided_by_label[label] = []
                dict_divided_by_label[label].append(informative_dict)

                # the following code is used to extract the individual actions performed
                decoded = decode_label(label)
                if 'uri' not in decoded:
                    print(f"Decoded label does not contain 'uri' key: {decoded}, {line}")
                    continue

                # decoded_resource, decoded_subresource, *_ = decoded.get('uri').split("/") + [None]  # trick to get None if the subresource is not present
                # decoded_verb = decoded.get('verb')

                # useful to debug
                # decoded_string = f"{label} -> {decoded['uri']} {decoded['verb']}"
                # print(decoded_string, informative_dict)

                # if (informative_dict.get('resource') == decoded_resource and
                #     informative_dict.get('subresource') == decoded_subresource and
                #     verbs_dict.get(informative_dict.get('verb')) == verbs_dict.get(decoded_verb)):
                #     # compare verbs number instead of verbs directly

                action_key = str(label) + ACTION_KEY_SEPARATOR

                if informative_dict['namespace'] is None and informative_dict['name'] is None:
                    # since namespace and name are both empty, use the username to create the key
                    action_key += informative_dict['username']
                else:
                    action_key += str(informative_dict['namespace']) + ACTION_KEY_SEPARATOR
                    owner_refs = informative_dict.get('ownerReferences')
                    if owner_refs is not None and isinstance(owner_refs, list) and len(owner_refs) > 0 and owner_refs[0] is not None:
                        action_key += owner_refs[0].get('uid')
                    else:
                        action_key += str(informative_dict['name'])

                if action_key not in actions_dict:
                    actions_dict[action_key] = {}

                if not actions_dict.get(action_key):  # if action is empty
                    action_detail = get_informative_dict(json_data)  # get new dict, not the same as before
                    action_detail.pop('requestURI', None)
                    action_detail[UUID] = str(uuid.uuid4())
                    actions_dict[action_key] = action_detail
                    
    return actions_dict, dict_divided_by_label


def print_actions_dict_to_csv(actions_dict, input_filename):
    output_file_name = input_filename.split('/')[-1] + "_actions.csv"
    
    fieldnames = set()
    for val in actions_dict.values():
        fieldnames.update(val.keys())
    
    with open(output_file_name, "w") as output_file:
        w = csv.DictWriter(output_file, fieldnames)
        
        w.writeheader()
        for key, val in actions_dict.items():
            row = {}
            row.update(val)
            w.writerow(row)


def get_value_by_owner_reference(log_line, action_value):
    action_owner_ref = action_value.get('ownerReferences')
    log_owner_ref = log_line.get('ownerReferences')

    if action_owner_ref is not None:
        if log_line.get('name') is not None:
            if log_line.get('name').startswith(action_owner_ref[0].get('name')):
                return action_value.get(UUID)

        if log_owner_ref is not None:
            if log_owner_ref[0].get('name').startswith(action_owner_ref[0].get('name')):
                return action_value.get(UUID)
            if log_owner_ref[0].get('uid') == action_owner_ref[0].get('uid'):
                return action_value.get(UUID)

    if log_owner_ref is not None:
        if action_value.get('name') is not None and log_owner_ref[0].get('name').startswith(action_value.get('name')):
            return action_value.get(UUID)
        if log_owner_ref[0].get('uid') == action_value.get('metadata/uid'):
            return action_value.get(UUID)

    return None


# This function returns the uuid of the action to which it corresponds
def get_associate_action_uuid(candidate_actions, log_line):
    if len(candidate_actions) == 1:
        return next(iter(candidate_actions.values())).get(UUID)
    else:
        for key, action_val in candidate_actions.items():
            if log_line.get('name') == action_val.get('name') and log_line.get('name') is not None:
                return action_val.get(UUID)

            value_by_owner_reference = get_value_by_owner_reference(log_line, action_val)
            if value_by_owner_reference is not None:
                return value_by_owner_reference

        # ---
        # hard-coded behaviours
        # ---
        if log_line.get('verb') == 'get' and log_line.get('resource') == "namespaces":
            # actions are ordered by time. Consequently, here, we assume that when we encounter a log line that doesn't
            # match any action we assign to it the first uuid we encounter. Then, the second and so on.
            for key, action_values in candidate_actions.items():
                if log_line.get('username') == action_values.get('username') and \
                        log_line.get('namespace') == action_values.get('namespace') and \
                        action_values.get('notMatchingNamespaceAlreadyAssigned') is None:
                    action_values['notMatchingNamespaceAlreadyAssigned'] = True  # add it in order to skip at next iteration
                    return action_values.get(UUID)

        if log_line.get('resource') == "events":
            for key, action_values in candidate_actions.items():
                if log_line.get('involvedObject') is not None:
                    if log_line.get('involvedObject').get('name') == action_values.get('name'):
                        return action_values.get(UUID)
                    if action_values.get('ownerReferences') is not None and \
                            log_line.get('involvedObject').get('name') == action_values.get('ownerReferences')[0].get('name'):
                        return action_values.get(UUID)

        for key, action_val in candidate_actions.items():
            if log_line.get('name') is not None and action_val.get('name') is not None:
                if log_line.get('name').startswith(action_val.get('name')) or \
                        action_val.get('name').startswith(log_line.get('name')):
                    return action_val.get(UUID)

            # delete namespaces rule
            if (action_val.get('verb') == 'delete' or action_val.get('verb') == 'create') and \
                    action_val.get('resource') == 'namespaces':
                if log_line.get('namespace') == action_val.get('name'):
                    return action_val.get(UUID)

        if log_line.get('resource') == 'persistentvolumeclaims' and log_line.get('verb') != "list" and \
                log_line.get('name') is not None:
            # try to match the name of the statefulset with the name of the pvc
            pvc_prefix, ss, *_ = log_line.get('name').split("-")
            for key, action_val in candidate_actions.items():
                if action_val.get('name') == ss and \
                        action_val.get('resource') == 'statefulsets':
                    return action_val.get(UUID)

        if log_line.get('resource') == 'persistentvolumes' and log_line.get('verb') != "list" and \
                log_line.get('claimRef') is not None:
            pv = log_line.get('claimRef').get('name')
            pv_prefix, ss, *_ = pv.split("-")
            for key, action_val in candidate_actions.items():
                if action_val.get('name') == pv:
                    return action_val.get(UUID)
                if action_val.get('name') == ss and \
                        action_val.get('resource') == 'statefulsets':
                    return action_val.get(UUID)

        if log_line.get('resource') == 'events' and log_line.get('involvedObject') is not None:
            involved_name = log_line.get('involvedObject').get('name')
            try:
                prefix, resource_name, *_ = involved_name.split("-")
                for key, action_val in candidate_actions.items():
                    if action_val.get('name') == resource_name:
                        return action_val.get(UUID)
            except ValueError:
                pass

        # Control plane actions
        # ** API Server watching objects
        # The API server monitors core components with a 10minute
        # timeout. It remains unclear what the API server watches in other groups:
        # we probably need to deploy more components to see what the API server
        # watches.
        # - Verb: =watch=
        # - Users: =system:apiserver=
        # - Objects: =configmaps=, =clusterroles=, =namespaces=, =serviceaccounts=,
        #   =resourcequotas=, =clusterrolebindings=, =rolebindings=, =secrets=,
        #   =nodes=, =pods=, =roles=
        # - Namespaces: none, apart from =configmaps= in =kube-system=. Additionally,
        #   if legacy service accounts areused, the API server also watches
        #   =kube-apiserver-legacy-service-account-token-tracking=, a CM in =kube-system=.
        #if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:apiserver':
        #    api_server_watched_objects = [
        #        'configmaps', 'clusterroles', 'namespaces', 'serviceaccounts',
        #        'resourcequotas', 'clusterrolebindings', 'rolebindings',
        #        'secrets', 'nodes', 'pods', 'roles'
        #    ]
        #    if log_line.get('resource') in api_server_watched_objects:
        #        return CONTROL_PLANE_UUID[0]
        # ** =kube-controller-manager= watching objects
        # The =kube-system= namespace watches objects, similar to the API server.
        # However, ConfigMaps are watched over non-namespaced objects and also
        # =certificateigningrequests= are watched.
        # 
        # I believe that the objects watched by the Kube Controller Manager are
        # specific to what is deployed in the cluster. For example, if the
        # cluster has a deployment, the Kube Controller Manager will watch
        # also =deployments=.
        # 
        # - Verb: =watch=
        # - Users: =system:kube-controller-manager=
        # - Objects: same as the API server, plus =certificateigningrequests=
        # - Namespaces: none
        # if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:kube-controller-manager':
            # kcm_watched_objects = [
                # 'configmaps', 'clusterroles', 'namespaces', 'serviceaccounts',
                # 'resourcequotas', 'clusterrolebindings', 'rolebindings',
                # 'secrets', 'nodes', 'pods', 'roles', 'certificateigningrequests'
            # ]
            # if log_line.get('resource') in kcm_watched_objects:
                # return CONTROL_PLANE_UUID[1]
        # # ** =kube-controller-manager= getting and creating tokens for GC and RQ controllers
        # # The =kube-controller-manager= gets every less than an hour the serviceaccounts
        # # =/api/v1/namespaces/kube-system/serviceaccounts/generic-garbage-collector= and
        # # =/api/v1/namespaces/kube-system/serviceaccounts/resourcequota-controller=.
        # # It then creates tokens for them, which expire in an hour.
        # # *** 1
        # # - Verb: =get=
        # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
        # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/generic-garbage-collector=
        # if log_line.get('verb') == 'get' and log_line.get('username') == 'system:kube-controller-manager':
            # if log_line.get('resource') == 'serviceaccounts' and \
                    # log_line.get('namespace') == 'kube-system' and \
                    # log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
                # return CONTROL_PLANE_UUID[2]
        # # *** 2
        # # - Verb: =get=
        # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
        # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/resourcequota-controller=
        # if log_line.get('verb') == 'get' and log_line.get('username') == 'system:kube-controller-manager':
            # if log_line.get('resource') == 'serviceaccounts' and \
                    # log_line.get('namespace') == 'kube-system' and \
                    # log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
                # return CONTROL_PLANE_UUID[3]
        # # *** 3
        # # - Verb: =create=
        # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
        # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/generic-garbage-collector/token=
        # if log_line.get('verb') == 'create' and log_line.get('username') == 'system:kube-controller-manager':
            # if log_line.get('resource') == 'serviceaccounts' and \
                    # log_line.get('namespace') == 'kube-system' and \
                    # log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
                # return CONTROL_PLANE_UUID[4]
        # # *** 4
        # # - Verb: =create=
        # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
        # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/resourcequota-controller/token=
        # if log_line.get('verb') == 'create' and log_line.get('username') == 'system:kube-controller-manager':
            # if log_line.get('resource') == 'serviceaccounts' and \
                    # log_line.get('namespace') == 'kube-system' and \
                    # log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
                # return CONTROL_PLANE_UUID[5]
        # # ** Kube Scheduler watching objects
        # # The Kube Scheduler watches pods, nodes, namespaces, always with
        # # a 10-minute timeout.
        # # - Verb: =watch=
        # # - Users: =system:kube-scheduler=
        # # - Objects: =pods=, =nodes=, =namespaces=
        # # - Namespaces: none
        # if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:kube-scheduler':
            # kube_scheduler_watched_objects = [
                # 'pods', 'nodes', 'namespaces'
            # ]
            # if log_line.get('resource') in kube_scheduler_watched_objects:
                # return CONTROL_PLANE_UUID[6]
        # # *** Extension-apiserver-authentication
        # # This object is also watched by the Kube Scheduler.
        # # - Verb: =watch=
        # # - Users: =system:kube-scheduler=
        # # - Object: =configmaps/extension-apiserver-authentication=
        # # - Namespaces: =kube-system=
        # if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:kube-scheduler':
            # if log_line.get('resource') == 'configmaps' and \
                    # log_line.get('namespace') == 'kube-system' and \
                    # log_line.get('name') == 'extension-apiserver-authentication':
                # return CONTROL_PLANE_UUID[7]
        # # ** Nodes watching objects
        # # Each node in the cluster watches pods (non-namespaced), nodes
        # # (themselves), and some configmaps.
        # # *** Pods
        # # - Verb: =watch=
        # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
        # # - Objects: =pods=
        # # - Namespaces: none
        # if log_line.get('verb') == 'watch' and log_line.get('username', '').startswith('system:node:'):
            # if log_line.get('resource') == 'pods':
                # return CONTROL_PLANE_UUID[8]
        # # *** Nodes
        # # - Verb: =watch=
        # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
        # # - Objects: =nodes/{node-name}=
        # # - Namespaces: none
        # if log_line.get('verb') == 'watch' and log_line.get('username', '').startswith('system:node:'):
            # if log_line.get('resource') == 'nodes':
                # return CONTROL_PLANE_UUID[9]
        # # *** ConfigMaps
        # # Every node hosting some Pod of any namespace will be in charge of watching
        # # the serviceaccounts of the Pods that are running.
        # # 
        # # The CMs being watched are =kube-flannel-cfg=, =kube-proxy=, =kube-root-ca.crt=,
        # # and =coredns=. They of course depend on the components deployed in the cluster.
        # # Let's keep this generic.
        # # 
        # # - Verb: =watch=
        # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
        # # - Objects: =configmaps/kube-system/configmaps/{serviceaccount}=
        # # - Namespace: =kube-system=
        # if log_line.get('verb') == 'watch' and log_line.get('username', '').startswith('system:node:'):
            # if log_line.get('resource') == 'configmaps' and log_line.get('namespace') == 'kube-system':
                # return CONTROL_PLANE_UUID[10]
        # # ** Nodes creating tokens
        # # *** Nodes creating tokens for SAs in the kube-system namespace
        # # Since nodes watch the configmaps of the Pods they are running, as the
        # # tokens of their service accounts expire, they will recreate them.
        # # - Verb: =create=
        # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
        # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/{serviceaccount}/token=
        # if log_line.get('verb') == 'create' and log_line.get('username', '').startswith('system:node:'):
            # if log_line.get('resource') == 'serviceaccounts' and log_line.get('namespace') == 'kube-system':
                # return CONTROL_PLANE_UUID[11]
        # # ** Nodes getting their own status
        # # Nodes poll their own status every ten seconds.
        # # - Verb: =get=
        # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
        # # - Objects: =/api/v1/nodes/{the same node}=
        # if log_line.get('verb') == 'get' and log_line.get('username', '').startswith('system:node:'):
            # if log_line.get('resource') == 'nodes':
                # return CONTROL_PLANE_UUID[12]
        # # ** Nodes patching their status to update conditions
        # # Nodes update their status (e.g., MemoryPressure, DiskPressure, PIDPressure) by patching their own status
        # # every five minutes.
        # # - Verb: =patch=
        # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
        # # - Objects: =/api/v1/nodes/{the same node}=
        # if log_line.get('verb') == 'patch' and log_line.get('username', '').startswith('system:node:'):
            # if log_line.get('resource') == 'nodes':
                # return CONTROL_PLANE_UUID[13]
        # # ** CoreDNS watching namespaces 
        # # - Verb: =watch=
        # # - Users: =system:serviceaccount:kube-system:coredns=
        # # - Objects: =namespaces=
        # if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:serviceaccount:kube-system:coredns':
            # if log_line.get('resource') == 'namespaces':
                # return CONTROL_PLANE_UUID[14]
        # # ** Kube-proxy watching nodes
        # # - Verb: =watch=
        # # - Users: =system:serviceaccount:kube-system:kube-proxy=
        # # - Objects: =nodes=
        # if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:serviceaccount:kube-system:kube-proxy':
            # if log_line.get('resource') == 'nodes':
                # return CONTROL_PLANE_UUID[15]

    return BASE_LABEL  # if no action is found, return the base label UUID


# This functions, given a set of lines grouped by label, search foreach line the action to which it corresponds
def assign_uuid_to_lines(actions_dict, dict_divided_by_label, cluster_timeout=DEFAULT_CLUSTER_TIMEOUT_SECONDS, cluster_max_lines=DEFAULT_CLUSTER_MAX_LINES):
    b = 0   
    c = 0
    problematic = {}
    cplabeled = {}
    a4496 = set()
    
    # Track cluster information: {uuid: {first_timestamp, line_count, lines}}
    cluster_info = {}
    
    for label, log_lines in dict_divided_by_label.items():
        possible_actions = {}

        # search for actions that match the current label
        for action_key in actions_dict.keys():
            if action_key.split(ACTION_KEY_SEPARATOR)[0] == str(label):
                possible_actions[action_key] = actions_dict.get(action_key)

        # add the correct action uuid to each line
        for log_line in log_lines:
            uuid_value = get_associate_action_uuid(possible_actions, log_line)
            
            if uuid_value == BASE_LABEL:
                b += 1
                problematic[label] = problematic.get(label, 0).__add__(1)
                log_line[UUID] = uuid_value
            elif uuid_value in CONTROL_PLANE_UUID:
                c += 1
                cplabeled[label] = cplabeled.get(label, 0).__add__(1)
                log_line[UUID] = uuid_value
            else:
                # Check if this cluster should be split due to size or timeout limits
                timestamp = log_line.get('stageTimestamp') or log_line.get('requestReceivedTimestamp', '')
                
                if uuid_value not in cluster_info:
                    cluster_info[uuid_value] = {
                        'first_timestamp': timestamp,
                        'line_count': 0,
                        'lines': []
                    }
                
                cluster = cluster_info[uuid_value]
                # Check if cluster exceeds limits
                should_split = False
                
                # Check size limit
                if cluster['line_count'] >= cluster_max_lines:
                    should_split = True
                    
                # Check timeout limit  
                if timestamp and cluster['first_timestamp']:
                    try:
                        first_time = datetime.fromisoformat(cluster['first_timestamp'].replace('Z', '+00:00'))
                        current_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_diff = (current_time - first_time).total_seconds()
                        if time_diff > cluster_timeout:
                            should_split = True
                    except (ValueError, AttributeError):
                        pass  # Ignore timestamp parsing errors
                
                if should_split:
                    # Create new cluster for this line
                    new_uuid = str(uuid.uuid4())
                    # print(f"Splitting cluster {uuid_value} (size: {cluster['line_count']}, creating new: {new_uuid})")
                    
                    cluster_info[new_uuid] = {
                        'first_timestamp': timestamp,
                        'line_count': 1,
                        'lines': [log_line]
                    }
                    log_line[UUID] = new_uuid
                else:
                    # Add to existing cluster
                    cluster['line_count'] += 1
                    cluster['lines'].append(log_line)
                    log_line[UUID] = uuid_value

        print(a4496, len(a4496))

    # Print cluster statistics
    cluster_sizes = [info['line_count'] for info in cluster_info.values()]
    print(f"Found {b} unassigned lines out of {sum(len(v) for v in dict_divided_by_label.values())} total lines")
    print(f"Found {c} control-plane lines")
    print(f"Created {len(cluster_info)} clusters")
    print(f"Problematic labels: {sorted(problematic.items(), key=lambda item: item[1], reverse=True)}")


def dump_intermediate_results(actions_dict, dict_divided_by_label):
    with open('actions_dict.json', 'w') as file:
        file.write(json.dumps(actions_dict))
        file.write("\n")
        file.write(json.dumps(dict_divided_by_label))
    with open('dict_divided_by_label.csv', 'w') as file:
        csv_writer = csv.writer(file)
        for key, value in actions_dict.items():
            csv_writer.writerow([key, value])

def main(args):
    actions_dict, dict_divided_by_label = \
        get_actions_and_labels_dicts(args.file, args.key)

    if args.csv:
        print_actions_dict_to_csv(actions_dict, args.file)

    if args.intermediate:
        dump_intermediate_results(actions_dict, dict_divided_by_label)

    cluster_timeout = getattr(args, 'cluster_timeout', DEFAULT_CLUSTER_TIMEOUT_SECONDS)
    cluster_max_lines = getattr(args, 'cluster_max_lines', DEFAULT_CLUSTER_MAX_LINES)
    
    print(f"Using cluster limits: max_lines={cluster_max_lines}, timeout={cluster_timeout}s")
    assign_uuid_to_lines(actions_dict, dict_divided_by_label, cluster_timeout, cluster_max_lines)

    # visualize log without uuid
    if args.dump:
        for key, values in dict_divided_by_label.items():
            for value2 in values:
                uuid_value = value2.get(UUID)
                if uuid_value == BASE_LABEL:
                # if uuid_value == BASE_LABEL and value2.get('verb') != 'list' and value2.get('verb') != 'watch' \
                #     and value2.get('verb') != 'get':
                # if uuid_value == BASE_LABEL and value2.get('verb') == 'get':
                    value2.pop('stageTimestamp', None)
                    value2.pop('metadata/uid', None)
                    value2.pop('UUID', None)
                    print(colored(str(key) + " " + str(value2), 'yellow', 'on_magenta'))

    # Output full original log with UUIDs
    if args.output_full_log_with_uuid:
        # Build a mapping from (label, line_index) to UUID
        label_lineidx_to_uuid = {}
        for label, log_lines in dict_divided_by_label.items():
            for log_line in log_lines:
                label_lineidx_to_uuid[(label, log_line.get('line_index'))] = log_line.get(UUID)

        output_file_name = "with_uuids.json"
        with open(args.file, 'r') as infile, open(output_file_name, 'w') as outfile:
            line_index = 0
            for line in infile:
                line_index += 1
                json_data = json.loads(line)
                label = json_data.get(args.key, None)
                uuid_value = label_lineidx_to_uuid.get((label, line_index))
                if uuid_value:
                    json_data[UUID] = uuid_value
                outfile.write(json.dumps(json_data, separators=(',', ':')) + "\n")
        print(f"Full log with UUIDs written to {output_file_name}")

    if args.plot:
        audit_graph = AuditGraph(actions_dict, dict_divided_by_label, args.query)
        audit_graph.plot_graph()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='parseLog',
        description='This program visualizes labelled logs.')

    parser.add_argument('-f', '--file', required=True, help='The log input file')
    parser.add_argument('-d', '--dump', action='store_true', help='Dump the unclassified logs to the terminal', default=False)
    parser.add_argument('-c', '--csv', action='store_true', help='Dump all actions to a csv file', default=False)
    parser.add_argument('-i', '--intermediate', action='store_true', help='Dump intermediate results to a file', default=False)
    parser.add_argument('-p', '--plot', action='store_true', help='Plot graph', default=False)
    parser.add_argument('-k', '--key', help='The key to use as label', default=DEFAULT_LABEL_KEY)
    parser.add_argument('-q', '--query', help='The query to filter results', default="")
    parser.add_argument('--output-full-log-with-uuid', action='store_true', help='Output the full original log with assigned UUIDs', default=False)
    parser.add_argument('--cluster-timeout', type=int, help='Maximum time in seconds before splitting a cluster', default=DEFAULT_CLUSTER_TIMEOUT_SECONDS)
    parser.add_argument('--cluster-max-lines', type=int, help='Maximum number of lines in a cluster before splitting it', default=DEFAULT_CLUSTER_MAX_LINES)
    parsed_args = parser.parse_args()

    main(parsed_args)
