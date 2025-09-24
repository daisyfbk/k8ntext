import argparse
from common import LABEL_UNKNOWN, LABEL_IGNORE
from label_proposer import propose_label
from model_features import FEATURES as model_features
from typing import Sequence
import uuid
import json

# Main variables
# ACTION_KEY_SEPARATOR = "%"
UUID = "uuid_new"
DEFAULT_LABEL_KEY = "label"
BASE_LABEL = "1010"
# CONTROL_PLANE_UUID = [
#     str(i) for i in range(2000, 2030)
# ]

# Cluster limits
DEFAULT_CLUSTER_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_CLUSTER_MAX_LINES = 1000
TIMESTAMP_KEY = "requestReceivedTimestamp"

Unknown = dict | list | str | int | float | None # Placeholder for actual type


def get_next_uuid() -> str:
    return str(uuid.uuid4())


def is_triggering_action(line: dict, label_key: str = DEFAULT_LABEL_KEY) -> bool:
    if label_key not in line:
        return False
    label = line[label_key]

    if label in [LABEL_UNKNOWN, LABEL_IGNORE]:
        return False
    
    proposed_label = propose_label(line)
    if proposed_label != label:
        return False
    return True


def clusterize_labelcluster(lines: list[dict],
                            indices: list[int],
                            tractionlist: list[int],
                            label_key: str = DEFAULT_LABEL_KEY) -> Unknown:
    print(f"Clusterizing label cluster with {len(indices)} lines for label '{lines[indices[0]][label_key]}' and {len(tractionlist)} triggering actions")

    # Each cluster starts with a triggering action
    clusters: dict[str, list[int]] = {}
    for traction_idx in tractionlist:
        uuid = get_next_uuid()
        lines[traction_idx][UUID] = uuid
        clusters[uuid] = [traction_idx]

    pass



def clusterize_log(lines: list[dict], label_key: str = DEFAULT_LABEL_KEY) -> Unknown:
    label_clusters: dict[str, list[int]] = {}
    triggering_actions: dict[str, list[int]] = {}

    for i in range(len(lines)):
        line = lines[i]
        label = line.get(label_key, None)
        if label is None:
            print(f"Skipping line {i} due to missing label key '{label_key}'")
            continue
        if label not in label_clusters:
            label_clusters[label] = []
        label_clusters[label].append(i)
        if is_triggering_action(line, label_key):
            if label not in triggering_actions:
                triggering_actions[label] = []
            triggering_actions[label].append(i)

    print(f"Total label_clusters formed: {len(label_clusters)}")
    print(f"Total triggering_actions found: {sum([len(triggering_actions[k]) for k in triggering_actions])}")

    final_clusters: dict[str, list[int]] = {}

    for label, indices in label_clusters.items():
        # Clusters with 1 element are trivially kept as they are
        if len(indices) == 1:
            uuid = get_next_uuid()
            lines[indices[0]][UUID] = uuid
            final_clusters[uuid] = [indices[0]]
            continue
        if len(indices) == 0:
            print(f"Warning: Empty cluster for label {label}. What the heck?")
            exit(1)

        tractionlist = triggering_actions.get(label, [])
        if len(tractionlist) == 0:
            print(f"Warning: No triggering actions found for label '{label}' with {len(indices)} lines.")
            exit(1)

        if len(tractionlist) == len(indices):
            # Health check to see if all the lines are triggering actions
            if set(tractionlist) != set(indices):
                print(f"Warning: Mismatch in tractionlist and indices for label '{label}'")
                exit(1)
            # All lines are triggering actions, we can cluster them trivially
            for idx in indices:
                uuid = get_next_uuid()
                lines[idx][UUID] = uuid
                final_clusters[uuid] = [idx]
            continue

        # If a triggering action is alone, we cluster it alone
        if len(tractionlist) == 1 and len(indices) > 1:
            uuid = get_next_uuid()
            for idx in indices:
                lines[idx][UUID] = uuid
            final_clusters[uuid] = indices
            continue
        
        # For larger clusters, we can do more advanced processing
        _ = clusterize_labelcluster(lines, indices, tractionlist, label_key=label_key)

    print(f"Total final clusters formed: {len(final_clusters)}")
        # Further processing can be done here for larger clusters
        # For example, checking for triggering actions
        #for idx in indices:
        #    line = lines[idx]
        #    pass
    
       # if is_triggering_action(line, label_key):
        #    pass #print(f"Triggering action found: {line[label_key]}")


def main(args: argparse.Namespace):
    log_file = args.file
    if not log_file:
        print("Error: Log file is required.")
        exit(1)

    lines: Sequence[dict[str, str]] = []
    with open(log_file, 'r') as f:
        read: Sequence[str] = f.readlines()
        for i in range(len(read)):
            lines.append(json.loads(read[i]))
        
        print(f"Processing log file: {log_file}")

    if lines is None:
        print("No lines read from the log file.")
        exit(1)
    
    _ = clusterize_log(lines, label_key=args.key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='parseLog',
        description='This program clusterizes log files based on their structure and content.')

    parser.add_argument('-f', '--file', required=True, help='The log input file')
    parser.add_argument('-k', '--key', help='The key to use as label', default=DEFAULT_LABEL_KEY)
    parser.add_argument('-d', '--output-full-log-with-uuid', action='store_true', help='Output the full original log with assigned UUIDs', default=False)
    # parser.add_argument('--cluster-timeout', type=int, help='Maximum time in seconds before splitting a cluster', default=DEFAULT_CLUSTER_TIMEOUT_SECONDS)
    # parser.add_argument('--cluster-max-lines', type=int, help='Maximum number of lines in a cluster before splitting it', default=DEFAULT_CLUSTER_MAX_LINES)
    parsed_args = parser.parse_args()

    main(parsed_args)