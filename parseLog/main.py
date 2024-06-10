import json
import argparse
import re

parser = argparse.ArgumentParser(
    prog='parseLog',
    description='This program takes a log as input and removes from it unnecessary content.'
                'The output is then written to a new file.')

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
blacklisted_resources_user_based = {"configmaps", "nodes", "pods", "namespaces", "serviceaccounts", "rolebindings",
                                    "resourcequotas", "clusterroles", "secrets", "clusterrolebindings", "roles",
                                    "certificatesigningrequests"}


def is_whitelisted_request_uri(request_uri, json_data):
    if request_uri not in blacklisted_requestURIs and not \
            bool(re.search(r"/api(s)*\?timeout", request_uri)) and not \
            bool(re.search(r"/openapi/v3\?timeout", request_uri)) and not \
            (request_uri == "/api/v1" and bool(re.search("system:serviceaccount", json_data['user']['username']))):
        return True
    else:
        return False


def is_whitelisted_objectref_resource(objectref_resource, json_data):
    # Filter logs done by system performing "watch" verb
    verb = json_data['verb']
    user_username = json_data['user']['username']
    if verb == "watch" and (objectref_resource in blacklisted_resources_user_based) and \
            (user_username == "system:apiserver" or
             user_username == "system:kube-scheduler" or
             user_username == "system:kube-controller-manager" or
             bool(re.search("system:node:", user_username))):
        return False

    # Further specialize the filter on some resource
    if (verb == "watch" and objectref_resource == "namespaces" and
            user_username == "system:serviceaccount:kube-system:coredns"):
        return False

    if (verb == "watch" and objectref_resource == "nodes" and
            (user_username == "system:serviceaccount:kube-flannel:flannel" or
             user_username == 'system:serviceaccount:kube-system:kube-proxy')):
        return False

    if objectref_resource not in blacklisted_resources_liv2 and \
            objectref_resource not in blacklisted_resources_liv3 and \
            objectref_resource not in blacklisted_resources_liv4 and \
            objectref_resource not in blacklisted_resources_liv7 and \
            objectref_resource not in blacklisted_resources_liv9 and \
            objectref_resource not in blacklisted_resources_liv10 and \
            objectref_resource not in blacklisted_resources_liv20:
        return True
    else:
        return False


def main():
    parser.add_argument('-f', required=True, help='The log input file')
    args = parser.parse_args()

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
            if is_whitelisted_request_uri(request_uri, json_data):
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
