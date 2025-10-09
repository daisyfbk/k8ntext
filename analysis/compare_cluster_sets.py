import json
from collections import defaultdict
from typing import Dict, Tuple, List
import argparse
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics.cluster import adjusted_rand_score, adjusted_mutual_info_score

def load_uuid_clusters(filename: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Load JSON lines file and group audit IDs by UUID."""
    auditid_to_uuid = {}
    clusters = set()
    
    with open(filename, 'r') as f:
        for line in f:
            entry = json.loads(line)
            ###### TEST
            # if entry['label'] == 2727984 or ('predicted_label' in entry and entry['predicted_label'] == 2727984):
            #    continue
            #### TEST
            #### TEST 2
            #if 'cplabel' in entry and entry['cplabel']:
            #    continue
            if 'UUID' in entry and 'auditID' in entry:
                if entry['UUID'] == '1010':
                    continue
                auditid_to_uuid[entry['auditID']] = entry['UUID']
                clusters.add(entry['UUID'])

    print(f"Loaded {len(auditid_to_uuid)} audit IDs across {len(clusters)} clusters from {filename}")

    uuid_to_clusters = defaultdict(list)
    for audit_id, uuid in auditid_to_uuid.items():
        uuid_to_clusters[uuid].append(audit_id)

    return dict(auditid_to_uuid), dict(uuid_to_clusters)

def plot_cluster_sizes(gt_sizes: List[int], pred_sizes: List[int]):
    """Plot cluster sizes comparison between ground truth and predicted."""
    # Remove all size 1s for better visualization
    # gt_sizes = [size for size in gt_sizes if size > 1]
    # pred_sizes = [size for size in pred_sizes if size > 1]

    print(sorted(gt_sizes, reverse=True)[:20])
    print(sorted(pred_sizes, reverse=True)[:20])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Create indices for plotting
    gt_indices = np.arange(len(gt_sizes))
    pred_indices = np.arange(len(pred_sizes))
    
    # Plot 1: Overlay both distributions
    ax1.plot(gt_indices, gt_sizes, 'b-', label='Ground Truth', linewidth=2, alpha=0.7)
    ax1.plot(pred_indices, pred_sizes, 'r-', label='Predicted', linewidth=2, alpha=0.7)
    ax1.set_xlabel('Cluster Index (sorted by size)')
    ax1.set_ylabel('Cluster Size')
    ax1.set_title('Cluster Size Distribution Comparison')
    ax1.legend()
    __max_gt = max(gt_sizes)
    gt_magnitude = 10 ** (len(str(__max_gt)) - 1)
    ax1.set_xlim(__max_gt - 5 * gt_magnitude, None)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Side-by-side comparison with different x-axis scales
    max_len = max(len(gt_sizes), len(pred_sizes))
    
    # Normalize indices to [0, 1] for fair comparison
    if len(gt_sizes) > 1:
        gt_norm_indices = np.linspace(0, 1, len(gt_sizes))
    else:
        gt_norm_indices = [0.5]
        
    if len(pred_sizes) > 1:
        pred_norm_indices = np.linspace(0, 1, len(pred_sizes))
    else:
        pred_norm_indices = [0.5]
    
    ax2.plot(gt_norm_indices, gt_sizes, 'b-', label=f'Ground Truth ({len(gt_sizes)} clusters)', 
             linewidth=2, alpha=0.7, marker='o', markersize=3)
    ax2.plot(pred_norm_indices, pred_sizes, 'r-', label=f'Predicted ({len(pred_sizes)} clusters)', 
             linewidth=2, alpha=0.7, marker='s', markersize=3)
    ax2.set_xlabel('Normalized Cluster Index (0 = smallest, 1 = largest)')
    ax2.set_ylabel('Cluster Size')
    ax2.set_title('Normalized Cluster Size Distribution')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Add statistics text
    gt_stats = f"GT: min={min(gt_sizes)}, max={max(gt_sizes)}, median={np.median(gt_sizes):.1f}, mean={np.mean(gt_sizes):.1f}"
    pred_stats = f"Pred: min={min(pred_sizes)}, max={max(pred_sizes)}, median={np.median(pred_sizes):.1f}, mean={np.mean(pred_sizes):.1f}"
    
    fig.suptitle(f'Cluster Size Analysis\n{gt_stats}\n{pred_stats}', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('cluster_comparison.png', dpi=300, bbox_inches='tight')
    # plt.show()
    
    print(f"Cluster comparison plot saved as 'cluster_comparison.png'")

def calculate_mapping_accuracy(ground_truth: Dict[str, str], 
                            predicted: Dict[str, str],
                            gt_inverse: Dict[str, List[str]],
                            pred_inverse: Dict[str, List[str]]
                            ) -> float:
    """
    Calculate average Jaccard similarity between clusters that share audit IDs.
    Jaccard similarity = |intersection| / |union| between two sets.
    """
    seen = set()
    total_similarity = 0.0
    num_comparisons = 0

    if set(ground_truth.keys()) != set(predicted.keys()):
        print("Warning: AuditIDs in ground truth and predicted do not match!")
        return 0.0
        
    audit_ids = list(ground_truth.keys())
    
    for audit_id in audit_ids:
        if audit_id in seen:
            continue
            
        # Get the clusters this audit_id belongs to
        gt_uuid = ground_truth[audit_id]
        pred_uuid = predicted[audit_id]
        
        # Get all auditIDs in those clusters
        gt_cluster = set(gt_inverse[gt_uuid])
        pred_cluster = set(pred_inverse[pred_uuid])
        
        # Calculate Jaccard similarity
        intersection = len(gt_cluster & pred_cluster)
        union = len(gt_cluster | pred_cluster)
        
        if union > 0:  # Avoid division by zero
            similarity = intersection / union
            total_similarity += similarity
            num_comparisons += 1
            
        # Mark all IDs in these clusters as seen to avoid duplicate comparisons
        seen.update(gt_cluster)
    
    if num_comparisons == 0:
        return 1.0 

    print(f"Compared {num_comparisons} clusters.")
    print(f"Total similarity: {total_similarity:.3f}")
        
    return total_similarity / num_comparisons


def main():
    parser = argparse.ArgumentParser(description='Compare UUID clusters between two JSON line files')
    parser.add_argument('ground_truth', help='Ground truth JSON lines file')
    parser.add_argument('predicted', help='Predicted JSON lines file')
    args = parser.parse_args()

    # Load clusters
    gt_clusters, gt_inverse = load_uuid_clusters(args.ground_truth)
    pred_clusters, pred_inverse = load_uuid_clusters(args.predicted)
    
    # Calculate basic statistics
    print(f"Ground truth AuditIDs: {len(gt_clusters)}")
    print(f"Predicted AuditIDs: {len(pred_clusters)}")

    if set(gt_clusters.keys()) != set(pred_clusters.keys()):
        print("Warning: Audit IDs in ground truth and predicted do not match! Using intersection only.")
        common_uuids = set(gt_clusters.keys()) & set(pred_clusters.keys())
        gt_clusters_filt = {uuid: gt_clusters[uuid] for uuid in common_uuids}
        pred_clusters_filt = {uuid: pred_clusters[uuid] for uuid in common_uuids}
        print(f"Using {len(common_uuids)} common Audit IDs.")
        print(f"Scrapped a total of {len(set(gt_clusters.keys()) - common_uuids)} ground truth Audit IDs and "
              f"{len(set(pred_clusters.keys()) - common_uuids)} predicted Audit IDs.")
    else:
        gt_clusters_filt = gt_clusters
        pred_clusters_filt = pred_clusters

    # Get and sort cluster sizes
    gt_sizes = sorted([len(v) for k, v in gt_inverse.items()])
    pred_sizes = sorted([len(v) for k, v in pred_inverse.items()])
    
    #print(f"Ground truth cluster sizes (sorted): {gt_sizes}")
    #print(f"Predicted cluster sizes (sorted): {pred_sizes}")
    
    # Plot cluster sizes comparison
    plot_cluster_sizes(gt_sizes, pred_sizes)
    
    # Calculate mapping accuracy
    accuracy = calculate_mapping_accuracy(gt_clusters_filt, pred_clusters_filt,
                                            gt_inverse, pred_inverse)
                    
    print(f"\nMapping accuracy: {accuracy:.3f}")
    

if __name__ == "__main__":
    main()