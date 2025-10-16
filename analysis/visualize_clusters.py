import sys
from pathlib import Path

import argparse
import json
import logging as log
from typing import Optional
import os

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir / "parseLog"))

import parseLog.parameters as pm
from parseLog.label_proposer import propose_label
from parseLog.log_parser import get_informative_dict
from parseLog.support.log import initialize_log
from parseLog.parameters import LABEL_FEATURE as DEFAULT_LABEL_KEY


def is_triggering_action(line: dict, label_key: str = DEFAULT_LABEL_KEY) -> bool:
    """Check if a line is a triggering action."""
    if label_key not in line:
        log.debug(f"Label key '{label_key}' not found in line. Available keys: {list(line.keys())}")
        return False
    label = line[label_key]

    proposed_label = propose_label(line)
    is_trigger = (proposed_label == label)
    if log.getLogger().isEnabledFor(log.DEBUG):
        log.debug(f"Label: {label}, Proposed: {proposed_label}, Is trigger: {is_trigger}")
    return is_trigger


def format_line_info(line: dict, index: int, is_trigger: bool = False) -> str:
    """Format a line for display."""
    info = get_informative_dict(line)
    
    trigger_marker = "🎯 " if is_trigger else "   "
    
    # Extract key information
    username = info.get('username', 'N/A')
    verb = info.get('verb', 'N/A')
    resource = info.get('resource', 'N/A')
    namespace = info.get('namespace', 'N/A')
    name = info.get('name', 'N/A')
    timestamp = line.get('requestReceivedTimestamp', line.get('stageTimestamp', 'N/A'))
    
    # Format the output
    line_str = f"{trigger_marker}[{index:5d}] {timestamp[:23] if len(timestamp) > 23 else timestamp:23s} | "
    line_str += f"{username:30s} | {verb:15s} | {resource:20s}"
    
    if namespace != 'N/A':
        line_str += f" | ns:{namespace}"
    if name != 'N/A':
        line_str += f" | name:{name}"
    
    return line_str


def visualize_cluster_text(cluster: dict, label_key: str = DEFAULT_LABEL_KEY, 
                          show_only_triggers: bool = False) -> None:
    """Visualize a single cluster in text format."""
    uuid = cluster.get('uuid', 'unknown')
    num_lines = cluster.get('num_lines', 0)
    label = cluster.get('label', 'unknown')
    indices = cluster.get('indices', [])
    lines = cluster.get('lines', [])
    full_lines = cluster.get('full_lines', [])
    
    # Find triggering actions using full lines if available
    triggering_indices = []
    if full_lines:
        for i, full_line in enumerate(full_lines):
            if full_line and is_triggering_action(full_line, label_key):
                triggering_indices.append(i)
    
    print("=" * 120)
    print(f"Cluster UUID: {uuid}")
    print(f"Label: {label} | Number of lines: {num_lines} | Triggering actions: {len(triggering_indices)}")
    print("=" * 120)
    
    if show_only_triggers:
        # Show only triggering actions
        if len(triggering_indices) == 0:
            if len(lines) == 1:
                # Only one triggering action, show it
                idx = indices[0]
                line = lines[0]
                full_line = full_lines[0]
                print(format_line_info(full_line, idx, is_trigger=True))
        else:
            for i in triggering_indices:
                idx = indices[i]
                line = lines[i]
                full_line = full_lines[i]
                print(format_line_info(full_line, idx, is_trigger=True))
    else:
        # Show all lines
        if len(lines) == 0:
            print("  No lines in this cluster")
        else:
            for i, (idx, line) in enumerate(zip(indices, lines)):
                is_trigger = i in triggering_indices
                full_line = full_lines[i]
                print(format_line_info(full_line, idx, is_trigger=is_trigger))
    
    print()


def visualize_clusters_html(clusters: list[dict], output_file: str, 
                            label_key: str = DEFAULT_LABEL_KEY,
                            show_only_triggers: bool = False) -> None:
    """Generate an HTML visualization of clusters."""
    html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Cluster Visualization</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .cluster {{
            background-color: white;
            margin: 20px 0;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .cluster-header {{
            background-color: #4CAF50;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }}
        .cluster-info {{
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .line {{
            padding: 5px;
            margin: 2px 0;
            border-left: 3px solid #ddd;
            padding-left: 10px;
        }}
        .trigger {{
            background-color: #fff3cd;
            border-left: 3px solid #ffc107;
            font-weight: bold;
        }}
        .trigger::before {{
            content: "🎯 ";
        }}
        .timestamp {{
            color: #666;
        }}
        .username {{
            color: #2196F3;
            font-weight: bold;
        }}
        .verb {{
            color: #9C27B0;
            font-weight: bold;
        }}
        .resource {{
            color: #4CAF50;
        }}
        .namespace {{
            color: #FF5722;
        }}
        .name {{
            color: #795548;
        }}
        .filter-controls {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .filter-controls label {{
            margin-right: 20px;
        }}
        .summary {{
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <h1>Kubernetes Audit Log Cluster Visualization</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Clusters:</strong> {total_clusters}</p>
        <p><strong>Total Lines:</strong> {total_lines}</p>
        <p><strong>Total Triggering Actions:</strong> {total_triggers}</p>
    </div>
    
    <div class="filter-controls">
        <label><input type="checkbox" id="showOnlyTriggers" {checked}> Show only triggering actions</label>
        <label><input type="number" id="minLines" placeholder="Min lines" style="width: 80px;"> Minimum cluster size</label>
        <label><input type="number" id="maxLines" placeholder="Max lines" style="width: 80px;"> Maximum cluster size</label>
        <button onclick="applyFilters()">Apply Filters</button>
        <button onclick="resetFilters()">Reset</button>
    </div>
    
    <div id="clusters">
"""
    
    total_lines = sum(c.get('num_lines', 0) for c in clusters)
    total_triggers = 0
    
    # Calculate total triggering actions
    for cluster in clusters:
        full_lines = cluster.get('full_lines', [])
        if full_lines:
            for full_line in full_lines:
                if full_line and is_triggering_action(full_line, label_key):
                    total_triggers += 1
    
    html = html_template.format(
        total_clusters=len(clusters),
        total_lines=total_lines,
        total_triggers=total_triggers,
        checked="checked" if show_only_triggers else ""
    )
    
    for cluster in clusters:
        uuid = cluster.get('uuid', 'unknown')
        num_lines = cluster.get('num_lines', 0)
        label = cluster.get('label', 'unknown')
        indices = cluster.get('indices', [])
        lines = cluster.get('lines', [])
        full_lines = cluster.get('full_lines', [])
        
        # Find triggering actions using full lines if available
        triggering_indices = []
        if full_lines:
            for i, full_line in enumerate(full_lines):
                if full_line and is_triggering_action(full_line, label_key):
                    triggering_indices.append(i)
        
        html += f'    <div class="cluster" data-num-lines="{num_lines}">\n'
        html += f'        <div class="cluster-header">\n'
        html += f'            <div class="cluster-info">Cluster UUID: {uuid}</div>\n'
        html += f'            <div>Label: {label} | Lines: {num_lines} | Triggering Actions: {len(triggering_indices)}</div>\n'
        html += f'        </div>\n'
        
        for i, (idx, line) in enumerate(zip(indices, lines)):
            is_trigger = i in triggering_indices
            info = line  # Already in informative dict format
            
            username = info.get('username', 'N/A')
            verb = info.get('verb', 'N/A')
            resource = info.get('resource', 'N/A')
            namespace = info.get('namespace', 'N/A')
            name = info.get('name', 'N/A')
            timestamp = line.get('requestReceivedTimestamp', line.get('stageTimestamp', 'N/A'))
            
            if len(timestamp) > 23:
                timestamp = timestamp[:23]
            
            line_class = "line trigger" if is_trigger else "line"
            
            html += f'        <div class="{line_class}" data-is-trigger="{str(is_trigger).lower()}">\n'
            html += f'            <span class="timestamp">[{idx:5d}] {timestamp}</span> | '
            html += f'<span class="username">{username}</span> | '
            html += f'<span class="verb">{verb}</span> | '
            html += f'<span class="resource">{resource}</span>'
            
            if namespace != 'N/A':
                html += f' | <span class="namespace">ns:{namespace}</span>'
            if name != 'N/A':
                html += f' | <span class="name">name:{name}</span>'
            
            html += '\n        </div>\n'
        
        html += '    </div>\n'
    
    html += """    </div>
    
    <script>
        function applyFilters() {
            const showOnlyTriggers = document.getElementById('showOnlyTriggers').checked;
            const minLines = parseInt(document.getElementById('minLines').value) || 0;
            const maxLines = parseInt(document.getElementById('maxLines').value) || Infinity;
            
            document.querySelectorAll('.cluster').forEach(cluster => {
                const numLines = parseInt(cluster.getAttribute('data-num-lines'));
                
                // Filter by cluster size
                if (numLines < minLines || numLines > maxLines) {
                    cluster.style.display = 'none';
                    return;
                }
                
                cluster.style.display = 'block';
                
                // Filter lines within cluster
                cluster.querySelectorAll('.line').forEach(line => {
                    const isTrigger = line.getAttribute('data-is-trigger') === 'true';
                    if (showOnlyTriggers && !isTrigger) {
                        line.style.display = 'none';
                    } else {
                        line.style.display = 'block';
                    }
                });
            });
        }
        
        function resetFilters() {
            document.getElementById('showOnlyTriggers').checked = false;
            document.getElementById('minLines').value = '';
            document.getElementById('maxLines').value = '';
            applyFilters();
        }
        
        // Apply initial filter state
        applyFilters();
    </script>
</body>
</html>"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    log.info(f"HTML visualization written to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Visualize clusters from clusters.json output'
    )
    
    parser.add_argument('-f', '--file', required=True,
                        help='Input clusters.json file')
    parser.add_argument('-F', '--full-log', 
                        help='Input clusterized-log.json file (optional, for triggering action detection)')
    parser.add_argument('-k', '--key', default=DEFAULT_LABEL_KEY,
                        help='The label key used (default: label)')
    parser.add_argument('-t', '--triggers-only', action='store_true',
                        help='Show only triggering actions')
    parser.add_argument('-T', '--text', action='store_true',
                        help='Output to terminal instead of HTML')
    parser.add_argument('-l', '--log-level', default='INFO',
                        help='Logging level (default: INFO)')
    parser.add_argument('-n', '--max-clusters', type=int,
                        help='Maximum number of clusters to display')
    parser.add_argument('-m', '--min-cluster-size', type=int, default=0,
                        help='Minimum cluster size to display')
    parser.add_argument('-M', '--max-cluster-size', type=int,
                        help='Maximum cluster size to display')
    
    args = parser.parse_args()
    
    initialize_log(log_level=args.log_level, application_type="visualize",
                   create_out_subfolders=True)
    
    # Load clusters
    log.info(f"Loading clusters from {args.file}")
    clusters = []
    with open(args.file, 'r') as f:
        for line in f:
            clusters.append(json.loads(line))
    
    log.info(f"Loaded {len(clusters)} clusters")
    
    # Try to load full log file for triggering action detection
    full_log = None
    full_log_file = args.full_log
    if not full_log_file:
        # Try to find clusterized-log.json in the same directory
        cluster_dir = Path(args.file).parent
        potential_log = cluster_dir / "clusterized-log.json"
        if potential_log.exists():
            full_log_file = str(potential_log)
    
    if full_log_file and Path(full_log_file).exists():
        log.info(f"Loading full log from {full_log_file} for triggering action detection")
        full_log = {}
        with open(full_log_file, 'r') as f:
            for idx, line in enumerate(f):
                full_log[idx] = json.loads(line)
        log.info(f"Loaded {len(full_log)} lines from full log")
    else:
        log.warning("Full log file not found. Triggering actions cannot be identified.")
        log.warning("Provide --full-log or place clusterized-log.json in the same directory as clusters.json")
    
    # Add full line info to clusters if available
    if full_log:
        for cluster in clusters:
            indices = cluster.get('indices', [])
            cluster['full_lines'] = [full_log.get(idx) for idx in indices]
            # Log if we're missing any full lines
            missing = sum(1 for idx in indices if idx not in full_log)
            if missing > 0:
                log.warning(f"Cluster {cluster.get('uuid', 'unknown')}: {missing}/{len(indices)} lines not found in full log")
    
    log.info(f"Loaded {len(clusters)} clusters")
    
    # Filter clusters by size
    if args.min_cluster_size > 0 or args.max_cluster_size:
        max_size = args.max_cluster_size or float('inf')
        clusters = [c for c in clusters if args.min_cluster_size <= c.get('num_lines', 0) <= max_size]
        log.info(f"Filtered to {len(clusters)} clusters by size")
    
    # Limit number of clusters
    if args.max_clusters:
        clusters = clusters[:args.max_clusters]
        log.info(f"Limited to {args.max_clusters} clusters")
    
    if args.text:
        # Text output to terminal
        for cluster in clusters:
            visualize_cluster_text(cluster, args.key, args.triggers_only)
    else:
        # HTML output
        # Get OUT_FOLDER from sys.modules to ensure we get the updated value
        # The issue is that support/log.py imports 'parameters' while this file imports 'parseLog.parameters'
        # They can be different module objects, so we need to check both
        import sys
        params_module = sys.modules.get('parameters')
        if params_module is None:
            params_module = sys.modules.get('parseLog.parameters')
        if params_module is None:
            params_module = pm  # Fallback to original import
        output_file = params_module.OUT_FOLDER + 'clusters_visualization.html'
        visualize_clusters_html(clusters, output_file, args.key, args.triggers_only)
        print(f"\nVisualization saved to: {output_file}")
        print(f"Open it in a browser to view the clusters.")


if __name__ == "__main__":
    main()
