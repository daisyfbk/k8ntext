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
import parameters as pm
import logging as log

from support.log import initialize_log

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


def get_next_uuid(
        force_control_plane: bool
    ) -> str:
    if force_control_plane:
        return DEFAULT_UUID_CONTROL_PLANE
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
            log.warning(
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

    log.debug(f"Created {len(windows)} time windows for {len(indices)} lines")

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

    # print(candidate_clusters)

    if len(window_lines) in (0, 1):
        raise Exception(
            "Error: Empty or single window_lines passed to clusterize_main_logic")

    clusters.update(candidate_clusters)
    
    # Build a mapping from line index to cluster UUID for already clustered lines
    idx_to_cluster: dict[int, str] = {}
    for uuid, indices in clusters.items():
        for idx in indices:
            idx_to_cluster[idx] = uuid
    
    cluster_metadata: dict[str, dict] = {} 
    for uuid in clusters:
        cluster_metadata[uuid] = _create_empty_cluster_metadata()
        
        # Initialize with triggering action metadata
        for idx in clusters[uuid]:
            _update_cluster_metadata(cluster_metadata[uuid], lines[idx])
    
    # Process remaining lines in order (round-robin assignment)
    unassigned_lines = [idx for idx in window_lines if idx not in idx_to_cluster]
    
    for idx in unassigned_lines:
        line = lines[idx]
        informative_dict = get_informative_dict(line)
        # print(informative_dict)
        
        # Control plane action trigger for keeping them separate or not
        cp = is_control_plane_action(informative_dict)
        # print(cp, merge_control_plane, idx)
        if cp is not None:
            if merge_control_plane:
                cp_uuid = DEFAULT_UUID_CONTROL_PLANE
                line[UUID] = cp_uuid
                if cp_uuid not in clusters:
                    clusters[cp_uuid] = []
                    cluster_metadata[cp_uuid] = _create_empty_cluster_metadata()
                clusters[cp_uuid].append(idx)
                idx_to_cluster[idx] = cp_uuid
                _update_cluster_metadata(cluster_metadata[cp_uuid], line)
                continue
            # else:
            #     cp_uuid = get_next_uuid()
            #     line[UUID] = cp_uuid
            #     clusters[cp_uuid] = [idx]
            #     idx_to_cluster[idx] = cp_uuid
            #     cluster_metadata[cp_uuid] = _create_empty_cluster_metadata()
            #     _update_cluster_metadata(cluster_metadata[cp_uuid], line)
            #     continue
        
        # Try to match this line to an existing cluster
        best_cluster = _find_best_cluster_match(
            line, informative_dict, clusters, cluster_metadata, max_cluster_size
        )
        
        if best_cluster is not None:
            # Assign to existing cluster
            line[UUID] = best_cluster
            clusters[best_cluster].append(idx)
            idx_to_cluster[idx] = best_cluster
            _update_cluster_metadata(cluster_metadata[best_cluster], line)
        else:
            # Create new cluster
            new_uuid = get_next_uuid(force_control_plane=cp is not None and merge_control_plane)
            line[UUID] = new_uuid
            clusters[new_uuid] = [idx]
            idx_to_cluster[idx] = new_uuid
            cluster_metadata[new_uuid] = _create_empty_cluster_metadata()
            _update_cluster_metadata(cluster_metadata[new_uuid], line)

    # print(clusters)
    return clusters


def _create_empty_cluster_metadata() -> dict:
    """Create an empty metadata dictionary for a cluster."""
    return {
        'usernames': set(),
        'resources': set(),
        'uids': set(),
        'owner_uids': set(),
        'involved_objects': set(),
        'claim_refs': set(),
    }


def _update_cluster_metadata(metadata: dict, line: dict) -> None:
    """Update cluster metadata with information from a log line."""
    info = get_informative_dict(line)
    
    # Add username
    if 'username' in info and info['username']:
        metadata['usernames'].add(info['username'])
    
    # Add resource signature
    resource_sig = (
        info.get('resource'),
        info.get('namespace'),
        info.get('name')
    )
    metadata['resources'].add(resource_sig)
    
    # Add metadata UID if present
    if 'metadata/uid' in info and info['metadata/uid']:
        metadata['uids'].add(info['metadata/uid'])
    
    # Add ownerReferences UIDs
    if 'ownerReferences' in info and info['ownerReferences']:
        owner_refs = info['ownerReferences']
        if isinstance(owner_refs, list):
            for owner in owner_refs:
                if isinstance(owner, dict) and 'uid' in owner:
                    metadata['owner_uids'].add(owner['uid'])
        elif isinstance(owner_refs, dict) and 'uid' in owner_refs:
            metadata['owner_uids'].add(owner_refs['uid'])
    
    # Add involvedObject signature
    if 'involvedObject' in info and info['involvedObject']:
        involved = info['involvedObject']
        if isinstance(involved, dict):
            involved_sig = (
                involved.get('kind'),
                involved.get('namespace'),
                involved.get('name'),
                involved.get('resource')
            )
            metadata['involved_objects'].add(involved_sig)
    
    # Add claimRef signature
    if 'claimRef' in info and info['claimRef']:
        claim = info['claimRef']
        if isinstance(claim, dict):
            claim_sig = (
                claim.get('kind'),
                claim.get('namespace'),
                claim.get('name')
            )
            metadata['claim_refs'].add(claim_sig)

    # Hard-coded behaviours:
    # When you create a namespce, the system:apiserver lists limitranges in the same namespace
    if info.get('verb') == 'create' and info.get('resource') == 'namespaces' and info.get('name'):
        namespace_name = info.get('name')
        # Add a pseudo-resource signature for limitranges in this namespace
        limitrange_sig = ('limitranges', namespace_name, None)
        metadata['resources'].add(limitrange_sig)

    # When you delete a namespace, a deletecollection followed by a get on
    # all resources in that namespace is performed
    if info.get('verb') == 'delete' and info.get('resource') == 'namespaces' and info.get('name'):
        namespace_name = info.get('name')
        # Add a marker signature that this cluster has a namespace deletion
        # The namespace field becomes the namespace name, not where the action happens
        ns_delete_sig = ('namespaces', namespace_name, None)
        metadata['resources'].add(ns_delete_sig)


def _find_best_cluster_match(
    line: dict,
    info: dict,
    clusters: ClusterDict,
    cluster_metadata: dict[str, dict],
    max_cluster_size: int | float
) -> Optional[str]:
    username = info.get('username')
    resource_sig = (info.get('resource'), info.get('namespace'), info.get('name'))
    
    line_uid = info.get('metadata/uid')
    line_owner_uids = set()
    if 'ownerReferences' in info and info['ownerReferences']:
        owner_refs = info['ownerReferences']
        if isinstance(owner_refs, list):
            for owner in owner_refs:
                if isinstance(owner, dict) and 'uid' in owner:
                    line_owner_uids.add(owner['uid'])
        elif isinstance(owner_refs, dict) and 'uid' in owner_refs:
            line_owner_uids.add(owner_refs['uid'])
    
    line_involved_sig = None
    if 'involvedObject' in info and info['involvedObject']:
        involved = info['involvedObject']
        if isinstance(involved, dict):
            line_involved_sig = (
                involved.get('kind'),
                involved.get('namespace'),
                involved.get('name'),
                involved.get('resource')
            )
    
    line_claim_sig = None
    if 'claimRef' in info and info['claimRef']:
        claim = info['claimRef']
        if isinstance(claim, dict):
            line_claim_sig = (
                claim.get('kind'),
                claim.get('namespace'),
                claim.get('name')
            )
    
    # Score each cluster
    best_cluster = None
    best_score = 0
    
    for uuid, metadata in cluster_metadata.items():
        # Skip if cluster is at max size
        if len(clusters[uuid]) >= max_cluster_size:
            continue
        
        score = 0
        
        # Priority 1: Username match (weight: 100)
        if username and username in metadata['usernames']:
            score += 50
        
        # Priority 2: ObjectRef match (weight: 50)
        if resource_sig in metadata['resources']:
            score += 100
        
        # Priority 3: UID relationships
        # Check if this line's UID is referenced as an owner in the cluster
        if line_uid and line_uid in metadata['owner_uids']:
            score += 80  # This line created something in the cluster
        
        # Check if this line references an owner that's in the cluster
        if line_owner_uids and line_owner_uids & metadata['uids']:
            score += 80  
        
        # Check involvedObject matches
        if line_involved_sig and line_involved_sig in metadata['involved_objects']:
            score += 60
        
        # Check if involvedObject points to a resource in the cluster
        if line_involved_sig:
            involved_resource_sig = (
                line_involved_sig[3],  # resource
                line_involved_sig[1],  # namespace
                line_involved_sig[2],  # name
            )
            if involved_resource_sig in metadata['resources']:
                score += 70
        
        # Check claimRef matches
        if line_claim_sig and line_claim_sig in metadata['claim_refs']:
            score += 60
        
        # Check if claimRef points to a resource in the cluster
        if line_claim_sig:
            claim_resource_sig = (
                line_claim_sig[0],  # kind as resource approximation
                line_claim_sig[1],  # namespace
                line_claim_sig[2],  # name
            )
            # This is approximate - claimRef may point to PVC/PV
            if any(claim_resource_sig[1] == r[1] and claim_resource_sig[2] == r[2] 
                   for r in metadata['resources']):
                score += 60
        
        # Hard-coded behaviors:
        # When system:apiserver lists limitranges in a namespace,
        # it should be clustered with user actions in that namespace
        # This is a system reaction that happens when users create resources in a namespace
        if (username == 'system:apiserver' and 
            info.get('verb') == 'list' and 
            info.get('resource') == 'limitranges' and 
            info.get('namespace')):
            namespace_name = info.get('namespace')
            # Check if this cluster has any user action (non-system) in the same namespace
            for username_in_cluster in metadata['usernames']:
                if not username_in_cluster.startswith('system:'):
                    for resource_tuple in metadata['resources']:
                        resource, ns, name = resource_tuple
                        if ns == namespace_name:
                            score += 90  
                            break
                    break

        # When a namespace is deleted, the system performs deletecollection and get
        # on all resources in that namespace. Match these to the namespace deletion.
        current_verb = info.get('verb')
        current_resource = info.get('resource')
        current_namespace = info.get('namespace')
        
        if (current_verb in ('deletecollection', 'get') and 
            current_namespace and
            current_resource not in ('namespaces',)): 
            # Check if this cluster has a namespace deletion for this namespace
            namespace_delete_sig = ('namespaces', current_namespace, None)
            if namespace_delete_sig in metadata['resources']:
                score += 95  
        
        if score > best_score:
            best_score = score
            best_cluster = uuid
    
    if best_score >= 50: 
        return best_cluster
    
    return None


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
    # print(f"Clusterizing label cluster with {len(indices)} lines for label '{lines[indices[0]][label_key]}' and {len(tractionlist)} triggering actions")

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
        log.debug(
             f"No triggering actions found for label '{lines[indices[0]][label_key]}' with {len(indices)} lines.")

    # Iterate through windows and assign lines to clusters
    for window in windows:
        start_idx, end_idx = window
        window_lines = [idx for idx in indices if start_idx <= idx <= end_idx]
        log.debug(f"Processing window from line {start_idx} to {end_idx} with {len(window_lines)} lines")
        if len(window_lines) == 0:
            raise Exception(
                f"Warning: Empty window from {start_idx} to {end_idx}. What the heck?")
        if len(window_lines) == 1:
            # Trivially create one cluster
            uuid = get_next_uuid(is_control_plane_action(get_informative_dict(lines[window_lines[0]])) is not None and merge_control_plane)
            lines[window_lines[0]][UUID] = uuid
            clusters[uuid] = [window_lines[0]]
            continue

        # Identify triggering actions in the window.
        # Sometimes there are none, sometimes there are many
        candidate_clusters: ClusterDict = {}
        for traction_idx in tractionlist:
            if start_idx <= traction_idx <= end_idx:
                uuid = get_next_uuid(is_control_plane_action(get_informative_dict(lines[traction_idx])) is not None and merge_control_plane)
                log.debug(f"Found triggering action at line {traction_idx} in window from {start_idx} to {end_idx}, assigning UUID {uuid}")
                # (f"Informative dict: {get_informative_dict(lines[traction_idx])}")
                lines[traction_idx][UUID] = uuid
                candidate_clusters[uuid] = [traction_idx]

        if len(candidate_clusters) == 0:
            log.debug(
                f"No triggering actions found in window from {start_idx} to {end_idx}")
        else:
            log.debug(f"Found {len(candidate_clusters)} triggering actions in window from {start_idx} to {end_idx}")
        
        # Send the tentative clusters and the lines for aggregation
        result_clusters = clusterize_main_logic(
            lines,
            window_lines,
            candidate_clusters,
            max_cluster_size=max_cluster_size,
            merge_control_plane=merge_control_plane
        )
        log.debug(f"Resulted in {len(result_clusters)} clusters from this window")

        # Merge resulting clusters into the main set
        # Check for UUID collisions (happens only if control plane merged)
        for uuid in result_clusters:
            if uuid not in clusters:
                clusters[uuid] = result_clusters[uuid]
            else:
                clusters[uuid].extend(result_clusters[uuid])
        
    log.info(f"Label: '{lines[indices[0]][label_key]}' clustered into {len(clusters)} clusters. Triggering actions: {len(tractionlist)}. Lines: {len(indices)}")
    # input()
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
            log.error(f"Skipping line {i} due to missing label key '{label_key}'")
            continue
        if label not in label_clusters:
            label_clusters[label] = []
        label_clusters[label].append(i)
        if is_triggering_action(line, label_key):
            if label not in triggering_actions:
                triggering_actions[label] = []
            triggering_actions[label].append(i)

    log.info(f"Total label_clusters formed: {len(label_clusters)}")
    log.info(
        f"Total triggering_actions found: {sum([len(triggering_actions[k]) for k in triggering_actions])}")

    final_clusters: ClusterDict = {}

    for label, indices in label_clusters.items():
        # Clusters with 1 element are trivially kept as they are
        if len(indices) == 1:
            uuid = get_next_uuid(is_control_plane_action(get_informative_dict(lines[indices[0]])) is not None and merge_control_plane)
            lines[indices[0]][UUID] = uuid
            final_clusters[uuid] = [indices[0]]
            continue
        if len(indices) == 0:
            log.fatal(f"Empty cluster for label {label}. This should not happen.")
            exit(1)

        tractionlist = triggering_actions.get(label, [])
        if len(tractionlist) == 0:
            log.debug(
                f"Warning: No triggering actions found for label '{label}' with {len(indices)} lines.")

        if len(tractionlist) == len(indices):
            # Health check to see if all the lines are triggering actions
            if set(tractionlist) != set(indices):
                log.fatal(
                    f"Warning: Mismatch in tractionlist and indices for label '{label}'")
                exit(1)
            # All lines are triggering actions, we can cluster them trivially
            for idx in indices:
                uuid = get_next_uuid(is_control_plane_action(get_informative_dict(lines[idx])) is not None and merge_control_plane)
                lines[idx][UUID] = uuid
                final_clusters[uuid] = [idx]
            continue

        # If a triggering action is alone, we cluster it alone
        if len(tractionlist) == 1 and len(indices) > 1:
            uuid = get_next_uuid(is_control_plane_action(get_informative_dict(lines[tractionlist[0]])) is not None and merge_control_plane)
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

        # if label == 41376:
        #     print(f"Label '{label}' with {len(indices)} lines and {len(tractionlist)} triggering actions resulted in {len(output_clusters)} clusters")
        #     print(output_clusters)
        #     input()

        for uuid in output_clusters:
            if uuid not in final_clusters:
                final_clusters[uuid] = output_clusters[uuid]
            else:
                final_clusters[uuid].extend(output_clusters[uuid])


    log.info(f"Total overall clusters formed: {len(final_clusters)}")
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
    initialize_log(log_level=args.log_level, application_type="cluster")

    log_file = args.file
    if not log_file:
        log.fatal("Error: Log file is required.")
        exit(1)

    lines: Sequence[dict[str, str]] = []
    with open(log_file, 'r') as f:
        read: Sequence[str] = f.readlines()
        for i in range(len(read)):
            lines.append(json.loads(read[i]))

        log.info(f"Processing log file: {log_file}")

    if lines is None:
        log.fatal("No lines read from the log file.")
        exit(1)

    clusters: ClusterDict = clusterize_log(lines,
                                           label_key=args.key,
                                           merge_control_plane=args.merge_control_plane)
    
    # Output the full original log with assigned UUIDs if requested
    if True: # args.output_full_log_with_uuid:
        output_file = pm.OUT_FOLDER + "clusterized-log.json"
        # output_file = args.output_file if args.output_file else log_file + ".with_uuid"
        with open(output_file, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + '\n')
        log.info(f"Log with UUIDs written to {output_file}")

    # Output clusters information in JSON format if requested
    if True: # args.output_clusters:
        output_cluster_file = pm.OUT_FOLDER + "clusters.json"
        with open(output_cluster_file, 'w') as f:
            for uuid, indices in clusters.items():
                json.dump(
                {
                    'uuid': uuid,
                    'num_lines': len(indices),
                    'label': lines[indices[0]].get(args.key, 'unknown') if len(indices) > 0 else 'unknown',
                    'indices': indices,
                    'lines': [get_informative_dict(lines[idx]) for idx in indices],
                }, f, separators=(',', ':'))
                f.write('\n')
        log.info(f"Clusters information written to {output_cluster_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='parseLog',
        description='This program clusterizes log files based on their structure and content.')

    parser.add_argument('-l', '--log-level', help='Logging level', default='DEBUG')
    parser.add_argument('-f', '--file', required=True,
                        help='The log input file')
    parser.add_argument('-k', '--key', help='The key to use as label', default=DEFAULT_LABEL_KEY)
    # parser.add_argument('-O', '--output-full-log-with-uuid', action='store_true',
    #                     help='Whether to output the full original log with assigned UUIDs', default=False)
    # parser.add_argument('-o', '--output-file', 
    #                     help='Output file for the log with UUIDs')
    # parser.add_argument('-A', '--output-clusters', 
    #                     help='Whether to output clusters information in JSON format', action='store_true', default=False)
    # parser.add_argument('-a', '--output-cluster-file',
    #                     help='Output file for the clusters information in JSON format')
    parser.add_argument('-C', '--merge-control-plane', action='store_true',
                        help='Merge control plane actions into a single cluster', default=False)
    parsed_args = parser.parse_args()

    main(parsed_args)
