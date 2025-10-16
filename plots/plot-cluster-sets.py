import json
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import argparse
import matplotlib
matplotlib.use('pgf')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import logging as log
import sys

# Configure matplotlib to use PGF backend for LaTeX output
matplotlib.rcParams.update({
    "pgf.texsystem": "pdflatex",
    "font.family": "serif",
    "font.size": 10,
    "text.usetex": True,
    "pgf.rcfonts": False,
    "pgf.preamble": r"\usepackage{amsmath}",
})

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir / "parseLog"))

import parseLog.parameters as pm
from parseLog.support.log import initialize_log

def plot_cluster_sizes(gt_sizes: List[int], pred_sizes: List[int], output_file: str):
    """Plot cluster sizes comparison between ground truth and predicted."""
    
    log.debug(f"Top 20 GT cluster sizes: {sorted(gt_sizes, reverse=True)[:20]}")
    log.debug(f"Top 20 Pred cluster sizes: {sorted(pred_sizes, reverse=True)[:20]}")

    # Use LaTeX textwidth (typically 6.5 inches for two-column, 5 inches for single column)
    # Adjust figsize to fit \textwidth in LaTeX document
    fig, ax1 = plt.subplots(figsize=(6.5, 3))
    # fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Create indices for plotting
    gt_indices = np.arange(len(gt_sizes))
    pred_indices = np.arange(len(pred_sizes))
    
    # Plot 1: Overlay both distributions
    ax1.plot(gt_indices, gt_sizes, 'b-', label='Ground Truth', linewidth=2, alpha=0.7)
    ax1.plot(pred_indices, pred_sizes, 'r-', label='Predicted', linewidth=2, alpha=0.7)
    ax1.set_xlabel('Cluster Index (sorted by size)')
    ax1.set_ylabel('Cluster Size')
    ax1.set_title('Distribution of cluster sizes')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Truncate x-axis to show only the interesting part (from 8500 onwards)
    ax1.set_xlim(8500, None)
    
    # Add axis break indicators on the left side of bottom x-axis to show truncation
    dx = .005  # horizontal extent of diagonal lines (smaller = steeper)
    dy = .020   # vertical extent of diagonal lines (larger = steeper)
    gap = 0.005  # gap between the two break marks
    kwargs = dict(transform=ax1.transAxes, color='k', clip_on=False, linewidth=1.5)
    
    # Draw two steep parallel break marks on left side of x-axis (// style, more vertical)
    ax1.plot((-dx-gap, +dx-gap), (-dy, +dy), **kwargs)   # first break mark
    ax1.plot((-dx+gap, +dx+gap), (-dy, +dy), **kwargs)   # second break mark (parallel, shifted right)
    
    # Clean up spines
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    
    # Plot 2: Normalized comparison
    # max_len = max(len(gt_sizes), len(pred_sizes))
    
    # # Normalize indices to [0, 1] for fair comparison
    # if len(gt_sizes) > 1:
    #     gt_norm_indices = np.linspace(0, 1, len(gt_sizes))
    # else:
    #     gt_norm_indices = [0.5]
    #     
    # if len(pred_sizes) > 1:
    #     pred_norm_indices = np.linspace(0, 1, len(pred_sizes))
    # else:
    #     pred_norm_indices = [0.5]
    
    # ax2.plot(gt_norm_indices, gt_sizes, 'b-', label=f'Ground Truth ({len(gt_sizes)} clusters)', 
    #          linewidth=2, alpha=0.7, marker='o', markersize=3)
    # ax2.plot(pred_norm_indices, pred_sizes, 'r-', label=f'Predicted ({len(pred_sizes)} clusters)', 
    #          linewidth=2, alpha=0.7, marker='s', markersize=3)
    # ax2.set_xlabel('Normalized Cluster Index (0 = smallest, 1 = largest)')
    # ax2.set_ylabel('Cluster Size')
    # ax2.set_title('Normalized Cluster Size Distribution')
    # ax2.legend()
    # ax2.grid(True, alpha=0.3)
    
    # Add statistics text
    # gt_stats = f"GT: min={min(gt_sizes)}, max={max(gt_sizes)}, median={np.median(gt_sizes):.1f}, mean={np.mean(gt_sizes):.1f}"
    # pred_stats = f"Pred: min={min(pred_sizes)}, max={max(pred_sizes)}, median={np.median(pred_sizes):.1f}, mean={np.mean(pred_sizes):.1f}"
    
   #fig.suptitle(f'Cluster Size Analysis') # \n{gt_stats}\n{pred_stats}', fontsize=10)
    
    plt.tight_layout()
    
    # Save as PNG
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    
    # Save as PGF for LaTeX - this will automatically size to fit the figure dimensions
    pgf_file = output_file.replace('.png', '.pgf')
    plt.savefig(pgf_file, bbox_inches='tight')
    
    # Also save as PDF for easier LaTeX inclusion
    pdf_file = output_file.replace('.png', '.pdf')
    plt.savefig(pdf_file, bbox_inches='tight')
    
    plt.close()
    
    log.info(f"Cluster comparison plot saved as '{output_file}', '{pgf_file}', and '{pdf_file}'")


def compare_cluster_sets(ground_truth_file: str, predicted_file: str) -> Dict:
    """
    Compare ground truth clusters with predicted clusters.
    Each line in the JSON file represents a cluster with a unique UUID.
    
    Args:
        ground_truth_file: Path to ground truth clusters JSON file
        predicted_file: Path to predicted clusters JSON file
    
    Returns:
        Dictionary containing comparison metrics and detailed mapping
    """
    
    # Load clusters from both files
    def load_clusters(file_path: str) -> Tuple[Dict[str, Set[int]], Dict[int, str]]:
        """
        Load clusters and create mappings.
        Returns:
            - cluster_map: {uuid (cluster_id): set of line indices}
            - index_to_cluster: {line_index: uuid (cluster_id)}
        """
        cluster_map = defaultdict(set)
        index_to_cluster = {}
        
        with open(file_path, 'r') as f:
            for line in f:
                cluster = json.loads(line.strip())
                uuid = cluster['uuid']  # Use uuid as cluster identifier
                indices = cluster['indices']
                
                cluster_map[uuid].update(indices)
                for idx in indices:
                    index_to_cluster[idx] = uuid
        
        return dict(cluster_map), index_to_cluster
    
    # Load ground truth and predicted clusters
    gt_clusters, gt_index_map = load_clusters(ground_truth_file)
    pred_clusters, pred_index_map = load_clusters(predicted_file)
    
    # Track which predicted clusters are used by multiple GT clusters (for merge detection)
    pred_cluster_usage = defaultdict(list)  # pred_label -> list of gt_labels that map to it
    
    # Compare clusters
    comparison_results = {
        'ground_truth_clusters': len(gt_clusters),
        'predicted_clusters': len(pred_clusters),
        'cluster_mappings': [],
        'summary': {
            'perfect_matches': 0,  # True 1-to-1 matches
            'splits': 0,           # GT cluster split into multiple predicted clusters
            'merges': 0,           # GT cluster merged with others into one predicted cluster
            'split_and_merge': 0   # GT cluster both split and merged
        }
    }
    
    # For each ground truth cluster, see where its lines ended up
    for gt_label, gt_indices in gt_clusters.items():
        gt_size = len(gt_indices)
        
        # Track where each line from this GT cluster ended up
        predicted_distribution = defaultdict(set)
        
        for idx in gt_indices:
            if idx in pred_index_map:
                pred_label = pred_index_map[idx]
                predicted_distribution[pred_label].add(idx)
            else:
                # Line not found in predictions (shouldn't happen normally)
                predicted_distribution['MISSING'].add(idx)
        
        # Calculate split information
        mapping_info = {
            'gt_label': gt_label,
            'gt_size': gt_size,
            'split_into': len(predicted_distribution),
            'distribution': []
        }
        
        for pred_label, shared_indices in predicted_distribution.items():
            shared_size = len(shared_indices)
            pred_total_size = len(pred_clusters.get(pred_label, shared_indices))
            
            mapping_info['distribution'].append({
                'pred_label': pred_label,
                'shared_lines': shared_size,
                'percentage_of_gt': round(100 * shared_size / gt_size, 2),
                'pred_cluster_size': pred_total_size,
                'percentage_of_pred': round(100 * shared_size / pred_total_size, 2) if pred_total_size > 0 else 0,
                'shared_indices': sorted(list(shared_indices))[:10]  # Show first 10 for reference
            })
        
        # Sort by shared lines (descending)
        mapping_info['distribution'].sort(key=lambda x: x['shared_lines'], reverse=True)
        comparison_results['cluster_mappings'].append(mapping_info)
        
        # Track predicted cluster usage for merge detection
        for pred_label in predicted_distribution.keys():
            if pred_label != 'MISSING':
                pred_cluster_usage[pred_label].append(gt_label)
    
    # Add debugging: track which pred clusters are claimed as perfect matches
    perfect_match_pred_clusters = []
    
    # Now categorize each GT cluster based on complete analysis
    for mapping_info in comparison_results['cluster_mappings']:
        gt_label = mapping_info['gt_label']
        num_pred_clusters = mapping_info['split_into']
        
        # Check if this GT cluster is involved in merges
        involved_in_merge = False
        for dist in mapping_info['distribution']:
            pred_label = dist['pred_label']
            if pred_label != 'MISSING' and len(pred_cluster_usage[pred_label]) > 1:
                involved_in_merge = True
                break
        
        # Categorize the mapping
        if num_pred_clusters == 1 and not involved_in_merge:
            # Check if it's a true perfect match (exact count match, not just rounded percentages)
            dist = mapping_info['distribution'][0]
            pred_label = dist['pred_label']
            
            # Use actual counts to avoid rounding issues
            gt_size = mapping_info['gt_size']
            pred_size = len(pred_clusters.get(pred_label, [])) if pred_label != 'MISSING' else 0
            shared_size = dist['shared_lines']
            
            if shared_size == gt_size and shared_size == pred_size and pred_size > 0:
                # True 1-to-1 perfect match
                comparison_results['summary']['perfect_matches'] += 1
                mapping_info['category'] = 'perfect_match'
                perfect_match_pred_clusters.append(pred_label)
            else:
                # GT cluster maps to one pred, but they're not identical (shouldn't happen if not involved_in_merge)
                comparison_results['summary']['merges'] += 1
                mapping_info['category'] = 'merge'
        elif num_pred_clusters == 1 and involved_in_merge:
            comparison_results['summary']['merges'] += 1
            mapping_info['category'] = 'merge'
        elif num_pred_clusters > 1 and not involved_in_merge:
            comparison_results['summary']['splits'] += 1
            mapping_info['category'] = 'split'
        else:  # num_pred_clusters > 1 and involved_in_merge
            comparison_results['summary']['split_and_merge'] += 1
            mapping_info['category'] = 'split_and_merge'
    
    # Sort by GT cluster size (descending)
    comparison_results['cluster_mappings'].sort(key=lambda x: x['gt_size'], reverse=True)
    
    # Add sanity check information
    comparison_results['summary']['unique_perfect_match_pred_clusters'] = len(set(perfect_match_pred_clusters))
    comparison_results['summary']['total_perfect_match_claims'] = len(perfect_match_pred_clusters)
    
    # Debug: check for duplicates
    if len(perfect_match_pred_clusters) != len(set(perfect_match_pred_clusters)):
        log.warning(f"WARNING: {len(perfect_match_pred_clusters) - len(set(perfect_match_pred_clusters))} predicted clusters are claimed as perfect matches by multiple GT clusters!")
        from collections import Counter
        duplicates = [item for item, count in Counter(perfect_match_pred_clusters).items() if count > 1]
        log.warning(f"Duplicate pred clusters: {duplicates[:10]}")
    
    return comparison_results


def print_comparison_report(comparison: Dict):
    """Print a human-readable comparison report."""
    
    log.info(f"Ground Truth Clusters: {comparison['ground_truth_clusters']}")
    log.info(f"Predicted Clusters: {comparison['predicted_clusters']}")
    log.info(f"Categorization:")
    log.info(f"  Perfect Matches (1-to-1): {comparison['summary']['perfect_matches']}")
    log.info(f"  Merges (many GT -> 1 pred): {comparison['summary']['merges']}")
    log.info(f"  Splits (1 GT -> many pred): {comparison['summary']['splits']}")
    log.info(f"  Split+Merge (complex): {comparison['summary']['split_and_merge']}")
    
    # Show sanity check
    if 'unique_perfect_match_pred_clusters' in comparison['summary']:
        log.info(f"")
        log.info(f"Sanity check:")
        log.info(f"  Perfect match claims: {comparison['summary']['total_perfect_match_claims']}")
        log.info(f"  Unique pred clusters: {comparison['summary']['unique_perfect_match_pred_clusters']}")
    
    total_categories = (comparison['summary']['perfect_matches'] + 
                       comparison['summary']['merges'] + 
                       comparison['summary']['splits'] + 
                       comparison['summary']['split_and_merge'])
    log.info(f"  Total: {total_categories}")
    
    # log.info(f"{'='*80}")
    # log.info(f"DETAILED CLUSTER MAPPINGS (showing top 20)")
    # log.info(f"{'='*80}")
    
#    for mapping in comparison['cluster_mappings'][:20]:  # Show top 20
#        log.info(f"{'─'*80}")
#        log.info(f"Ground Truth Cluster: {mapping['gt_label']} (Size: {mapping['gt_size']} lines) [{mapping.get('category', 'unknown')}]")
#        log.info(f"Split into {mapping['split_into']} predicted cluster(s):")
#        
#        for dist in mapping['distribution']:
#            log.info(f"  → Predicted Cluster: {dist['pred_label']} (Total size: {dist['pred_cluster_size']})")
#            log.info(f"    Shared lines: {dist['shared_lines']} ({dist['percentage_of_gt']}% of GT)")
#            log.info(f"    Represents {dist['percentage_of_pred']}% of predicted cluster")
#            if dist['shared_indices']:
#                log.info(f"    Sample indices: {dist['shared_indices'][:5]}")
#

# Usage example
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Compare ground truth and predicted clusters from JSON files')
    parser.add_argument('ground_truth', help='Ground truth clusters JSON file')
    parser.add_argument('predicted', help='Predicted clusters JSON file')
    parser.add_argument('--plot', action='store_true', help='Generate visualization plots')
    parser.add_argument('--top-n', type=int, default=20,
                        help='Number of top clusters to show in heatmap (default: 20)')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level (default: INFO)')
    args = parser.parse_args()

    initialize_log(log_level=args.log_level, application_type="compare_clusters",
                   create_out_subfolders=True)
    
    import sys
    params_module = sys.modules.get('parameters')
    if params_module is None:
        params_module = sys.modules.get('parseLog.parameters')
    if params_module is None:
        params_module = pm  # Fallback to original import
    base_output_file = params_module.OUT_FOLDER

    output = f"{base_output_file}/cluster_comparison_results.json"

    log.info(f"Comparing clusters...")
    log.info(f"  Ground truth: {args.ground_truth}")
    log.info(f"  Predicted: {args.predicted}")
    
    results = compare_cluster_sets(
        ground_truth_file=args.ground_truth,
        predicted_file=args.predicted
    )
    
    print_comparison_report(results)
    
    # Save detailed results to JSON
    with open(output, 'w') as f:
        json.dump(results, f, indent=2)
    log.info(f"Detailed results saved to '{output}'")
    
    # Generate plots if requested
    if args.plot:
        log.info("Generating visualization plots...")
        
        # Load cluster data again to get sizes
        def get_cluster_sizes(file_path: str) -> List[int]:
            cluster_sizes = []
            with open(file_path, 'r') as f:
                for line in f:
                    cluster = json.loads(line.strip())
                    # Each uuid is a separate cluster
                    cluster_sizes.append(cluster['num_lines'])
            return sorted(cluster_sizes)
        
        gt_sizes = get_cluster_sizes(args.ground_truth)
        pred_sizes = get_cluster_sizes(args.predicted)
        
        # Generate all plots
        plot_cluster_sizes(gt_sizes, pred_sizes,
                            output_file=f"{base_output_file}/cluster_size_comparison.png")