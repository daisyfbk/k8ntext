import json
import argparse
import re
import configparser

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


def is_whitelisted_request_uri(request_uri):
    if request_uri in blacklisted_requestURIs or request_uri == "/api/v1" or \
            bool(re.search(r"/api(s)*\?timeout", request_uri)) or \
            bool(re.search(r"/openapi/v3\?timeout", request_uri)):
        return False
    else:
        return True


def is_whitelisted_objectref_resource(objectref_resource, json_data):
    verb = json_data['verb']
    user_username = json_data['user']['username']
    objectref_name = json_data.get('objectRef').get('name')  # can be None
    objectref_namespace = json_data.get('objectRef').get('namespace')  # can be None

    # Filter ResponseStarted watch logs
    if config.getboolean('ignore_log', 'response_started_watch'):
        if verb == 'watch' and json_data['stage'] == "ResponseStarted":
            return False

    # Filter CNI and external namespaces
    if config.getboolean('ignore_log', 'cni_and_external_namespaces'):
        if objectref_namespace in {"falco", "kube-flannel"} or \
            user_username == "system:serviceaccount:kube-flannel:flannel":
            return False

    # Filter logs done by API Server watching objects
    if config.getboolean('ignore_log', 'api_server_watching_objects'):
        if verb == "watch" and (objectref_resource in blacklisted_resources_user_based) and \
                user_username == "system:apiserver":
            return False

    # Filter logs done by Kube Controller Manager watching objects
    if config.getboolean('ignore_log', 'kube_controller_watching_objects'):
        if verb == "watch" and (objectref_resource in blacklisted_resources_user_based or
                                objectref_resource == "certificatesigningrequests") and \
                user_username == "system:kube-controller-manager":
            return False

    # Filter logs done by Kube Scheduler watching objects
    if config.getboolean('ignore_log', 'kube_scheduler_watching_objects'):
        if verb == "watch" and (objectref_resource in {"pods", "nodes", "namespaces"}) and \
                user_username == "system:kube-scheduler":
            return False

    # Filter logs done by Extension-apiserver-authentication
    if config.getboolean('ignore_log', 'extension_apiserver_authentication'):
        if verb == "watch" and objectref_resource == "configmaps" and \
                objectref_name == "extension-apiserver-authentication" and user_username == "system:kube-scheduler":
            return False

    # Filter logs done by Nodes watching Pods and Nodes
    if config.getboolean('ignore_log', 'nodes_watching_pods_and_nodes'):
        if (verb == "watch" and (objectref_resource in {"pods", "nodes"}) and
                bool(re.search("system:node:", user_username))):
            return False

    # Filter logs done by Nodes watching ConfigMaps
    if config.getboolean('ignore_log', 'nodes_watching_configmaps'):
        if (verb == "watch" and objectref_resource == "configmaps" and
                objectref_namespace == "kube-system" and bool(re.search("system:node:", user_username))):
            return False

    # Filter logs done by Nodes creating tokens for SAs in the kube-system namespace
    if config.getboolean('ignore_log', 'nodes_creating_sas_token'):
        if (verb == "create" and objectref_resource == "serviceaccounts" and
                bool(re.search("system:node:", user_username)) and
                json_data.get('objectRef').get('subresource') == "token"):
            return False

    # Filter logs done by CoreDNS watching namespaces
    if config.getboolean('ignore_log', 'coredns_watching_namespaces'):
        if (verb == "watch" and objectref_resource == "namespaces" and
                user_username == "system:serviceaccount:kube-system:coredns"):
            return False

    # Filter logs done by Kube-proxy watching nodes
    if config.getboolean('ignore_log', 'kube_proxy_watching_nodes'):
        if (verb == "watch" and objectref_resource == "nodes" and
                user_username == 'system:serviceaccount:kube-system:kube-proxy'):
            return False

    # Filter logs done by Nodes getting their own status
    if config.getboolean('ignore_log', 'nodes_getting_their_own_status'):
        if (verb == "get" and objectref_resource == "nodes" and
                bool(re.search("system:node:", user_username))):
            return False

    # Filter logs done by Nodes patching their status to update conditions
    if config.getboolean('ignore_log', 'nodes_patching_their_own_status'):
        if (verb == "patch" and objectref_resource == "nodes" and
                bool(re.search("system:node:", user_username))):
            return False

    # Filter logs done by Kube-controller-manager getting and creating tokens for GC and RQ controllers
    if config.getboolean('ignore_log', 'kube_controller_gc_and_rq_token'):
        if ((verb == "create" or verb == "get")
                and objectref_resource == "serviceaccounts" and
                user_username == "system:kube-controller-manager" and
                (objectref_name == "generic-garbage-collector" or objectref_name == "resourcequota-controller")):
            return False

    if (config.getboolean('ignore_log','blacklisted_resources_liv2') and objectref_resource in blacklisted_resources_liv2) or \
            (config.getboolean('ignore_log','blacklisted_resources_liv3') and objectref_resource in blacklisted_resources_liv3) or \
            (config.getboolean('ignore_log','blacklisted_resources_liv4') and objectref_resource in blacklisted_resources_liv4) or \
            (config.getboolean('ignore_log','blacklisted_resources_liv7') and objectref_resource in blacklisted_resources_liv7) or \
            (config.getboolean('ignore_log','blacklisted_resources_liv9') and objectref_resource in blacklisted_resources_liv9) or \
            (config.getboolean('ignore_log','blacklisted_resources_liv10') and objectref_resource in blacklisted_resources_liv10) or \
            (config.getboolean('ignore_log','blacklisted_resources_liv20') and objectref_resource in blacklisted_resources_liv20):
        return False
    else:
        return True


def main():
    parser.add_argument('-f', required=True, help='The log input file')
    args = parser.parse_args()

    config.read('config.ini')

    input_filename = args.f;
    output_filename = input_filename + "_edited"

    output_lines = []
    with (open(input_filename, 'r') as input_file):
        i = 0

        for line in input_file:
            i += 1
            # each line is a json, load it
            json_data = json.loads(line)

            # get the requestURI and filter out the unwanted ones
            request_uri = json_data['requestURI']
            if is_whitelisted_request_uri(request_uri):
                try:
                    # get the resource and filter out the unwanted ones
                    objectref_resource = json_data['objectRef']['resource']
                    if is_whitelisted_objectref_resource(objectref_resource, json_data):
                        output_lines.append(json_data)

                except KeyError:
                    # some unexpected log appears. Print a warning
                    print("Unmanaged log line. Check line: ", i)

    # sort the output_lines array by the requestReceivedTimestamp
    output_lines.sort(key=lambda x: x['requestReceivedTimestamp'])

    with open(output_filename, 'w') as output_file:
        for line in output_lines:
            output_file.write(json.dumps(line, separators=(',', ':')) + "\n")


if __name__ == "__main__":
    main()
