import argparse
from common import LABEL_UNKNOWN, LABEL_IGNORE
from label_proposer import propose_label
from model_features import FEATURES as model_features
from typing import Sequence, Optional
import uuid
import json
import math
import datetime
from log_parser import get_informative_dict
from clusterizer_cp import is_control_plane_action

ClusterDict = dict[str, list[int]]

# Main variables
# ACTION_KEY_SEPARATOR = "%"
UUID = "uuid_new"
DEFAULT_LABEL_KEY = "label"
BASE_LABEL = "1010"
DEFAULT_UUID_CONTROL_PLANE = "2020"

# Cluster limits
DEFAULT_CLUSTER_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_CLUSTER_MAX_LINES = 1000
TIMESTAMP_KEY = "requestReceivedTimestamp"

Unknown = dict | list | str | int | float | None  # Placeholder for actual type


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


# def cluster...


def get_timestamp_seconds(line: dict) -> Optional[float]:
    """Extract timestamp from line and convert to seconds since epoch."""
    timestamp = line.get(TIMESTAMP_KEY, '')
    if not timestamp:
        return None

    try:
        if timestamp.endswith('Z'):
            timestamp = timestamp[:-1] + '+00:00'
        time_obj = datetime.datetime.fromisoformat(timestamp)
        return time_obj.timestamp()
    except Exception:
        return None


def create_time_windows(lines: list[dict],
                        indices: list[int],
                        time_window_seconds: int,
                        max_window_lines: int) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []

    current_window: tuple[Optional[int], Optional[int]] = (None, None)
    window_start_time = None
    window_line_count = 0

    for i in range(len(indices)):
        idx: int = indices[i]
        line: dict = lines[idx]
        timestamp = get_timestamp_seconds(line)
        if timestamp is None:
            print(
                f"Warning: Line {idx} missing timestamp key '{TIMESTAMP_KEY}'. Skipping.")
            continue

        if window_start_time is None:
            window_start_time = timestamp
            current_window = (idx, idx)
            window_line_count = 1
            continue

        time_diff = timestamp - window_start_time
        if time_diff <= time_window_seconds and window_line_count < max_window_lines:
            # Extend current window
            current_window = (current_window[0], idx)
            window_line_count += 1
        elif time_diff > time_window_seconds or window_line_count >= max_window_lines:
            # Close current window and start a new one
            if current_window[0] is not None and current_window[1] is not None:
                windows.append(current_window)  # type: ignore
            else:
                raise Exception(
                    "Logic error: current_window is None when closing window")
            current_window = (idx, idx)
            window_start_time = timestamp
            window_line_count = 1

    # Append the last window if it exists
    if current_window[0] is not None and current_window[1] is not None:
        windows.append(current_window)  # type: ignore
    else:
        raise Exception(
            "Logic error: current_window is None when appending last window")

    if len(windows) == 0:
        raise Exception("Error: No windows created, something went wrong.")

    print(f"Created {len(windows)} time windows for {len(indices)} lines")
    # print(windows)

    return windows


def clusterize_main_logic(lines: list[dict],
                          window_lines: list[int],
                          candidate_clusters: ClusterDict,
                          max_cluster_size: int | float = math.inf,
                          merge_control_plane: bool = False
                          ) -> ClusterDict:
    # candidate clusters are either:
    # - empty: no triggering actions in the window
    # - one: one triggering action in the window
    # - many: multiple triggering actions in the window

    clusters: ClusterDict = {}

    print(candidate_clusters)

    if len(window_lines) in (0, 1):
        raise Exception(
            "Error: Empty or single window_lines passed to clusterize_main_logic")

    for idx in window_lines:
        line = lines[idx]
        informative_dict = get_informative_dict(line)
        print(informative_dict)
        # Hard-coded behaviours

        # Control plane action trigger for keeping them separate or not
        cp = is_control_plane_action(informative_dict)
        print(cp, merge_control_plane, idx)
        if cp is not None:
            if merge_control_plane:
                cp_uuid = DEFAULT_UUID_CONTROL_PLANE
                line[UUID] = cp_uuid
                if cp_uuid not in clusters:
                    clusters[cp_uuid] = []
                clusters[cp_uuid].append(idx)
                continue
            else:
                cp_uuid = get_next_uuid()
                line[UUID] = cp_uuid
                clusters[cp_uuid] = [idx]
                continue

    # Remaining logic
    # If we have 

    exit(1)
    return clusters


def clusterize_labels(lines: list[dict],
                      indices: list[int],
                      tractionlist: list[int],
                      label_key: str = DEFAULT_LABEL_KEY,
                      max_cluster_size: int | float = math.inf,
                      time_window_seconds: int = DEFAULT_CLUSTER_TIMEOUT_SECONDS,
                      max_window_lines: int = DEFAULT_CLUSTER_MAX_LINES,
                      merge_control_plane: bool = False
                      ) -> ClusterDict:
    clusters: ClusterDict = {}
    print(
        f"Clusterizing label cluster with {len(indices)} lines for label '{lines[indices[0]][label_key]}' and {len(tractionlist)} triggering actions")

    # Assume the log is already sorted by timestamp,
    # given that the model does that usually

    # Create time- and line-based windows
    windows = create_time_windows(
        lines, indices,  # tractionlist,
        time_window_seconds=time_window_seconds,
        max_window_lines=max_window_lines
    )

    # Check if no triggering actions in this label
    if len(tractionlist) == 0:
        print(
            f"Warning: No triggering actions found for label '{lines[indices[0]][label_key]}' with {len(indices)} lines.")

    # Iterate through windows and assign lines to clusters
    for window in windows:
        start_idx, end_idx = window
        window_lines = [idx for idx in indices if start_idx <= idx <= end_idx]
        print(
            f"Processing window from line {start_idx} to {end_idx} with {len(window_lines)} lines")
        if len(window_lines) == 0:
            raise Exception(
                f"Warning: Empty window from {start_idx} to {end_idx}. What the heck?")
        if len(window_lines) == 1:
            # Trivially create one cluster
            uuid = get_next_uuid()
            lines[window_lines[0]][UUID] = uuid
            clusters[uuid] = [window_lines[0]]
            continue

        # Identify triggering actions in the window.
        # Sometimes there are none, sometimes there are many
        candidate_clusters: ClusterDict = {}
        for traction_idx in tractionlist:
            if start_idx <= traction_idx <= end_idx:
                uuid = get_next_uuid()
                lines[traction_idx][UUID] = uuid
                candidate_clusters[uuid] = [traction_idx]

        if len(candidate_clusters) == 0:
            print(
                f"No triggering actions found in window from {start_idx} to {end_idx}")
        else:
            print(
                f"Found {len(candidate_clusters)} triggering actions in window from {start_idx} to {end_idx}")

        # Send the tentative clusters and the lines for aggregation
        result_clusters = clusterize_main_logic(
            lines,
            window_lines,
            candidate_clusters,
            max_cluster_size=max_cluster_size,
            merge_control_plane=merge_control_plane
        )

        clusters.update(result_clusters)

    return clusters


def clusterize_log(lines: list[dict],
                   label_key: str = DEFAULT_LABEL_KEY,
                   merge_control_plane: bool = False) -> ClusterDict:
    label_clusters: ClusterDict = {}
    triggering_actions: ClusterDict = {}

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
    print(
        f"Total triggering_actions found: {sum([len(triggering_actions[k]) for k in triggering_actions])}")

    final_clusters: ClusterDict = {}

    for label, indices in label_clusters.items():

        # TODO TODO TODO TODO TODO TODO TODO TODO TODO 
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO 
        if label in (61632, 119232):
            continue
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO


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
            print(
                f"Warning: No triggering actions found for label '{label}' with {len(indices)} lines.")
            exit(1)

        if len(tractionlist) == len(indices):
            # Health check to see if all the lines are triggering actions
            if set(tractionlist) != set(indices):
                print(
                    f"Warning: Mismatch in tractionlist and indices for label '{label}'")
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
        output_clusters = clusterize_labels(
            lines, indices, tractionlist,
            label_key=label_key,
            max_cluster_size=math.inf,
            time_window_seconds=DEFAULT_CLUSTER_TIMEOUT_SECONDS,
            max_window_lines=DEFAULT_CLUSTER_MAX_LINES,
            merge_control_plane=merge_control_plane
        )

        final_clusters.update(output_clusters)

    print(f"Total final clusters formed: {len(final_clusters)}")
    # Further processing can be done here for larger clusters
    # For example, checking for triggering actions
    # for idx in indices:
    #    line = lines[idx]
    #    pass

    # if is_triggering_action(line, label_key):
    #    pass #print(f"Triggering action found: {line[label_key]}")

    return final_clusters


def main(args: argparse.Namespace) -> None:
    """

    Main function to process the log file and clusterize it.

    Args:
        args (argparse.Namespace): Parsed command-line arguments
            from an argparse.ArgumentParser instance.
    """
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

    clusters: ClusterDict = clusterize_log(lines,
                                           label_key=args.key,
                                           merge_control_plane=args.merge_control_plane)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='parseLog',
        description='This program clusterizes log files based on their structure and content.')

    parser.add_argument('-f', '--file', required=True,
                        help='The log input file')
    parser.add_argument(
        '-k', '--key', help='The key to use as label', default=DEFAULT_LABEL_KEY)
    parser.add_argument('-d', '--output-full-log-with-uuid', action='store_true',
                        help='Output the full original log with assigned UUIDs', default=False)
    parser.add_argument('-C', '--merge-control-plane', action='store_true',
                        help='Merge control plane actions into a single cluster', default=False)
    # parser.add_argument('--cluster-timeout', type=int, help='Maximum time in seconds before splitting a cluster', default=DEFAULT_CLUSTER_TIMEOUT_SECONDS)
    # parser.add_argument('--cluster-max-lines', type=int, help='Maximum number of lines in a cluster before splitting it', default=DEFAULT_CLUSTER_MAX_LINES)
    parsed_args = parser.parse_args()

    main(parsed_args)
