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


def main():
    parser.add_argument('-f', required=True, help='The log input file')
    args = parser.parse_args()

    input_filename = args.f;
    output_filename = input_filename + "_edited"

    with (open(input_filename, 'r') as input_file):
        output_file = open(output_filename, "w")
        i = 0
        for line in input_file:
            i += 1
            # each line is a json, load it
            json_data = json.loads(line)

            # get the requestURI and filter out the unwanted ones
            request_uri = json_data['requestURI']
            if request_uri not in blacklisted_requestURIs and not \
                    bool(re.search("/api(s)*\?timeout", request_uri)) and not \
                    bool(re.search("/openapi/v3\?timeout", request_uri)):
                try:
                    # get the resource and filter out the unwanted ones
                    resource = json_data['objectRef']['resource']
                    if resource not in blacklisted_resources_liv2 and \
                            resource not in blacklisted_resources_liv3 and \
                            resource not in blacklisted_resources_liv4 and \
                            resource not in blacklisted_resources_liv7 and \
                            resource not in blacklisted_resources_liv9 and \
                            resource not in blacklisted_resources_liv10 and \
                            resource not in blacklisted_resources_liv20:
                        print(line, file=output_file, end='')
                except Exception as e:
                    if request_uri == "/api/v1" and bool(re.search("system:serviceaccount", json_data['user']['username'])):
                        continue
                    else:
                        print("Unmanaged log line. Check line: ", i)

        output_file.close()


if __name__ == "__main__":
    main()
