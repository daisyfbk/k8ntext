#!/usr/bin/env python3
"""
Script to analyze and display indecisions in predicted labels from model inference results.

This script reads the inference.json file containing model predictions and shows
detailed information about cases where the model had difficulty making a decision
(i.e., where multiple labels had similar weights).
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
from collections import Counter


def load_inference_data(file_path: str) -> Dict[str, Any]:
    """Load inference data from JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{file_path}': {e}")
        sys.exit(1)


def identify_indecisions(sequence_weights: Dict[str, Dict[str, float]], 
                        predicted_sequence: List[str],
                        confidence_threshold: float = 5.0) -> Dict[str, Tuple]:
    """
    Identify indecisions based on sequence weights and predictions.
    
    An indecision is a sequence where:
    1. Multiple labels have non-trivial weights
    2. The confidence difference between top candidates is small
    
    Args:
        sequence_weights: Dict mapping sequence_id -> {label: weight}
        predicted_sequence: List of predicted labels indexed by position  
        confidence_threshold: Minimum difference between top 2 weights to be considered decisive
    
    Returns:
        Dict mapping sequence_id -> (predicted_label, weights_dict)
    """
    indecisions = {}
    
    for seq_id, weights in sequence_weights.items():
        if len(weights) <= 1:
            continue
            
        # Sort weights by value (descending)
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        # Check if this is an indecision based on confidence threshold
        if len(sorted_weights) >= 2:
            confidence_diff = sorted_weights[0][1] - sorted_weights[1][1]
            
            if confidence_diff < confidence_threshold:
                # Get predicted label from list (convert seq_id to int index)
                try:
                    seq_idx = int(seq_id)
                    if seq_idx < len(predicted_sequence):
                        predicted_label = predicted_sequence[seq_idx]
                    else:
                        predicted_label = sorted_weights[0][0]  # fallback to highest weight
                except (ValueError, IndexError):
                    predicted_label = sorted_weights[0][0]  # fallback to highest weight
                
                indecisions[seq_id] = (predicted_label, weights)
    
    return indecisions


def analyze_indecisions(indecisions: Dict[str, Tuple]) -> None:
    """Analyze and display detailed information about indecisions."""
    
    if not indecisions:
        print("No indecisions found in the data.")
        return
    
    print(f"Total number of indecisions: {len(indecisions)}")
    print("=" * 80)
    
    # Statistics about sequence weights
    all_weights = []
    weight_counts = []
    confidence_diffs = []
    
    for seq_id, (predicted, weights) in indecisions.items():
        weight_counts.append(len(weights))
        all_weights.extend(weights.values())
        
        # Calculate confidence difference
        sorted_weights = sorted(weights.values(), reverse=True)
        if len(sorted_weights) >= 2:
            confidence_diffs.append(sorted_weights[0] - sorted_weights[1])
    
    print(f"Average number of candidate labels per indecision: {sum(weight_counts) / len(weight_counts):.2f}")
    print(f"Maximum number of candidate labels: {max(weight_counts)}")
    print(f"Minimum number of candidate labels: {min(weight_counts)}")
    
    if confidence_diffs:
        print(f"Average confidence difference: {sum(confidence_diffs) / len(confidence_diffs):.3f}")
        print(f"Minimum confidence difference: {min(confidence_diffs):.3f}")
        print(f"Maximum confidence difference: {max(confidence_diffs):.3f}")
    print()
    
    # Count frequency of predicted labels
    predicted_labels = Counter()
    
    for seq_id, (predicted, weights) in indecisions.items():
        predicted_labels[predicted] += 1
    
    print("Most common predicted labels in indecisions:")
    for label, count in predicted_labels.most_common(10):
        print(f"  {label}: {count} times")
    print()


def show_indecisions_detailed(indecisions: Dict[str, Tuple], 
                            limit: Optional[int] = None,
                            min_candidates: Optional[int] = None,
                            sort_by: str = 'sequence_id') -> None:
    """Show detailed information about each indecision."""
    
    if not indecisions:
        print("No indecisions to display.")
        return
    
    # Filter by minimum number of candidates if specified
    if min_candidates:
        filtered_indecisions = {
            seq_id: data for seq_id, data in indecisions.items()
            if len(data[1]) >= min_candidates
        }
        print(f"Filtered to {len(filtered_indecisions)} indecisions with >= {min_candidates} candidates")
    else:
        filtered_indecisions = indecisions
    
    # Sort indecisions
    if sort_by == 'sequence_id':
        sorted_items = sorted(filtered_indecisions.items(), key=lambda x: int(x[0]))
    elif sort_by == 'num_candidates':
        sorted_items = sorted(filtered_indecisions.items(), key=lambda x: len(x[1][1]), reverse=True)
    elif sort_by == 'confidence':
        # Sort by the difference between top 2 weights (lower difference = more uncertain)
        def get_confidence_diff(weights):
            sorted_weights = sorted(weights.values(), reverse=True)
            if len(sorted_weights) < 2:
                return 0
            return sorted_weights[0] - sorted_weights[1]
        
        sorted_items = sorted(filtered_indecisions.items(), 
                            key=lambda x: get_confidence_diff(x[1][1]))
    else:
        sorted_items = list(filtered_indecisions.items())
    
    # Apply limit if specified
    if limit:
        sorted_items = sorted_items[:limit]
        print(f"Showing first {len(sorted_items)} indecisions")
    
    print("\nDetailed Indecision Analysis:")
    print("=" * 80)
    
    for seq_id, (predicted, weights) in sorted_items:
        print(f"\nSequence ID: {seq_id}")
        print(f"Predicted Label: {predicted}")
        print(f"Number of candidates: {len(weights)}")
        
        # Sort weights by value (descending)
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        print("Label weights (sorted by confidence):")
        total_weight = sum(weights.values())
        for i, (label, weight) in enumerate(sorted_weights):
            percentage = (weight / total_weight) * 100 if total_weight > 0 else 0
            marker = "★" if label == predicted else " "
            print(f"  {marker} {label}: {weight:.3f} ({percentage:.1f}%)")
        
        # Calculate confidence metrics
        if len(sorted_weights) >= 2:
            confidence_diff = sorted_weights[0][1] - sorted_weights[1][1]
            confidence_ratio = sorted_weights[0][1] / sorted_weights[1][1] if sorted_weights[1][1] > 0 else float('inf')
            print(f"Confidence difference (top 2): {confidence_diff:.3f}")
            print(f"Confidence ratio (top/second): {confidence_ratio:.2f}")
        
        print("-" * 40)


def show_sequence_weights_stats(sequence_weights: Dict[str, Dict[str, float]]) -> None:
    """Show overall statistics about sequence weights."""
    
    print("Overall Sequence Weights Statistics:")
    print("=" * 80)
    
    single_candidate = 0
    multi_candidate = 0
    candidate_counts = Counter()
    all_confidence_diffs = []
    
    for seq_id, weights in sequence_weights.items():
        num_candidates = len(weights)
        candidate_counts[num_candidates] += 1
        
        if num_candidates == 1:
            single_candidate += 1
        else:
            multi_candidate += 1
            
            # Calculate confidence difference for multi-candidate sequences
            sorted_weights = sorted(weights.values(), reverse=True)
            if len(sorted_weights) >= 2:
                all_confidence_diffs.append(sorted_weights[0] - sorted_weights[1])
    
    total_sequences = len(sequence_weights)
    print(f"Total sequences: {total_sequences}")
    print(f"Single candidate sequences: {single_candidate} ({single_candidate/total_sequences*100:.1f}%)")
    print(f"Multi-candidate sequences: {multi_candidate} ({multi_candidate/total_sequences*100:.1f}%)")
    print()
    
    print("Distribution of candidate counts:")
    for count in sorted(candidate_counts.keys()):
        sequences = candidate_counts[count]
        percentage = sequences / total_sequences * 100
        print(f"  {count} candidates: {sequences} sequences ({percentage:.1f}%)")
    print()
    
    if all_confidence_diffs:
        print("Confidence difference statistics (for multi-candidate sequences):")
        print(f"  Mean: {sum(all_confidence_diffs) / len(all_confidence_diffs):.3f}")
        print(f"  Min: {min(all_confidence_diffs):.3f}")
        print(f"  Max: {max(all_confidence_diffs):.3f}")
        
        # Show distribution of confidence differences
        low_conf = sum(1 for diff in all_confidence_diffs if diff < 1.0)
        med_conf = sum(1 for diff in all_confidence_diffs if 1.0 <= diff < 5.0)
        high_conf = sum(1 for diff in all_confidence_diffs if diff >= 5.0)
        
        print(f"  Very uncertain (diff < 1.0): {low_conf} ({low_conf/len(all_confidence_diffs)*100:.1f}%)")
        print(f"  Somewhat uncertain (1.0 <= diff < 5.0): {med_conf} ({med_conf/len(all_confidence_diffs)*100:.1f}%)")
        print(f"  Confident (diff >= 5.0): {high_conf} ({high_conf/len(all_confidence_diffs)*100:.1f}%)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and display indecisions in predicted labels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python show_indecisions.py inference.json
  python show_indecisions.py inference.json --limit 10
  python show_indecisions.py inference.json --min-candidates 5 --sort-by confidence
  python show_indecisions.py inference.json --confidence-threshold 2.0 --limit 20
        """
    )
    
    parser.add_argument('inference_file', 
                       help='Path to the inference.json file')
    parser.add_argument('--limit', '-l', type=int, 
                       help='Limit the number of indecisions to display')
    parser.add_argument('--min-candidates', '-m', type=int,
                       help='Show only indecisions with at least this many candidates')
    parser.add_argument('--sort-by', '-s', 
                       choices=['sequence_id', 'num_candidates', 'confidence'],
                       default='sequence_id',
                       help='Sort indecisions by: sequence_id, num_candidates, or confidence')
    parser.add_argument('--summary-only', action='store_true',
                       help='Show only summary statistics, not detailed indecisions')
    parser.add_argument('--confidence-threshold', '-t', type=float, default=5.0,
                       help='Confidence threshold for identifying indecisions (default: 5.0)')
    parser.add_argument('--show-stats', action='store_true',
                       help='Show overall sequence weights statistics')
    
    args = parser.parse_args()
    
    # Load data
    data = load_inference_data(args.inference_file)
    
    # Extract sequence weights
    if 'sequence_weights' not in data:
        print("Error: No 'sequence_weights' key found in the data.")
        print(f"Available keys: {list(data.keys())}")
        sys.exit(1)
    
    sequence_weights = data['sequence_weights']
    predicted_sequence = data.get('predicted_sequence', [])
    
    # Show overall statistics if requested
    if args.show_stats:
        show_sequence_weights_stats(sequence_weights)
    
    # Identify indecisions
    indecisions = identify_indecisions(sequence_weights, predicted_sequence, args.confidence_threshold)
    
    print(f"Using confidence threshold: {args.confidence_threshold}")
    print()
    
    # Show analysis
    analyze_indecisions(indecisions)
    
    if not args.summary_only:
        show_indecisions_detailed(
            indecisions, 
            limit=args.limit,
            min_candidates=args.min_candidates,
            sort_by=args.sort_by
        )


if __name__ == "__main__":
    main()