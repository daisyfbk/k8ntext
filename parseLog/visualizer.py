import json
import argparse
import csv

from label_proposer import decode_label
from log_parser import get_informative_dict


def main():
    input_filename = parsed_args.f;

    verbs_dict = {}
    with open('verbs.csv', 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            verbs_dict[row.get('#verb')] = row.get('id')

    actions_dict = {}

    with (open(input_filename, 'r') as input_file):

        for line in input_file:
            # each line is a json, load it
            json_data = json.loads(line)

            label = json_data.get('label')

            if not json_data.get('cplabel') and label != -1:
                informative_dict = get_informative_dict(json_data)
                informative_dict.pop("requestURI", None)

                decoded = decode_label(label)
                decoded_resource, decoded_subresource, *_ = decoded.get('uri').split("/") + [None]  # trick to get None if the subresource is not present
                decoded_verb = decoded.get('verb')

                # useful to debug
                # decoded_string = f"{label} -> {decoded['uri']} {decoded['verb']}"
                # print(decoded_string, informative_dict)

                if (informative_dict.get('resource') == decoded_resource and
                        informative_dict.get('subresource') == decoded_subresource and
                        verbs_dict.get(informative_dict.get('verb')) == verbs_dict.get(decoded_verb)):  # compare verbs number instead of verbs directly

                    action_key = str(label) + "_"
                    if informative_dict['namespace'] is None and informative_dict['name'] is None:  # since namespace and name are both empty, use the username to create the key
                        action_key += informative_dict['username']
                    else:
                        action_key += str(informative_dict['namespace']) + "_" + str(informative_dict['name'])

                    if action_key not in actions_dict:
                        actions_dict[action_key] = {}

                    if not actions_dict.get(action_key):  # if action is empty
                        actions_dict[action_key] = informative_dict

    with open("test_output.csv", "w") as output_file:
        w = csv.DictWriter(output_file, informative_dict.keys())
        for key, val in sorted(actions_dict.items()):
            row = {}
            row.update(val)
            w.writerow(row)

    # print(json.dumps(actions_dict, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='parseLog',
        description='This program visualizes labelled logs.')

    parser.add_argument('-f', required=True, help='The log input file')
    parsed_args = parser.parse_args()

    main()
