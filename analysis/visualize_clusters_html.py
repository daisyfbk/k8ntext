from analysis.visualize_clusters import NONE_MARKER, is_triggering_action
from parseLog.parameters import LABEL_FEATURE as DEFAULT_LABEL_KEY


import logging as log


def visualize_clusters_html(clusters: list[dict], output_file: str,
                            label_key: str = DEFAULT_LABEL_KEY,
                            show_only_triggers: bool = False) -> None:
    """
    Visualize clusters in an HTML file.

    Args:
        clusters (list[dict]): List of clusters to visualize.
        output_file (str): Path to the output HTML file.
        label_key (str, optional): The label key used. Defaults to DEFAULT_LABEL_KEY.
        show_only_triggers (bool, optional): Whether to show only triggering actions. Defaults to False.
    """

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

            username = info.get('username', NONE_MARKER)
            verb = info.get('verb', NONE_MARKER)
            resource = info.get('resource', NONE_MARKER)
            namespace = info.get('namespace', NONE_MARKER)
            name = info.get('name', NONE_MARKER)
            timestamp = line.get('requestReceivedTimestamp', line.get('stageTimestamp', NONE_MARKER))

            if len(timestamp) > 23:
                timestamp = timestamp[:23]

            line_class = "line trigger" if is_trigger else "line"

            html += f'        <div class="{line_class}" data-is-trigger="{str(is_trigger).lower()}">\n'
            html += f'            <span class="timestamp">[{idx:5d}] {timestamp}</span> | '
            html += f'<span class="username">{username}</span> | '
            html += f'<span class="verb">{verb}</span> | '
            html += f'<span class="resource">{resource}</span>'

            if namespace != NONE_MARKER:
                html += f' | <span class="namespace">ns:{namespace}</span>'
            if name != NONE_MARKER:
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