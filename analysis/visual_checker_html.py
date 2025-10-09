#!/usr/bin/env python3
"""
HTML Visual Checker for K8s Audit Log Predictions

This tool generates an HTML report displaying Kubernetes audit log entries 
with color-coded output based on API groups and predicted labels.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import html

# Import label decoder from parent directory
sys.path.append(str(Path(__file__).parent.parent / 'parseLog'))
try:
    import os
    # Change to parseLog directory to load CSV files
    original_cwd = os.getcwd()
    parselog_dir = Path(__file__).parent.parent / 'parseLog'
    os.chdir(parselog_dir)
    
    from label_proposer import decode_label, load_labels, load_verbs
    # Initialize labels and verbs data
    labels, available_verbs, namespaced_labels, seen_apigroups = load_labels()
    verbs = load_verbs()
    
    # Change back to original directory
    os.chdir(original_cwd)
    DECODER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import label decoder: {e}", file=sys.stderr)
    print("Label decoding will not be available.", file=sys.stderr)
    DECODER_AVAILABLE = False
except Exception as e:
    print(f"Warning: Could not initialize label decoder: {e}", file=sys.stderr)
    print("Label decoding will not be available.", file=sys.stderr)
    DECODER_AVAILABLE = False

def decode_and_format_label(predicted_label: Any) -> Dict[str, str]:
    """Decode a predicted label and return formatted information."""
    if not DECODER_AVAILABLE or predicted_label is None:
        return {
            'raw': str(predicted_label) if predicted_label is not None else 'NULL',
            'decoded': 'No decoder available' if not DECODER_AVAILABLE else 'NULL',
            'details': 'Label decoder not loaded' if not DECODER_AVAILABLE else 'No label to decode'
        }
    
    try:
        # Handle different label formats
        if isinstance(predicted_label, str):
            if predicted_label.lower() in ['null', 'none', '']:
                return {
                    'raw': 'NULL',
                    'decoded': 'NULL',
                    'details': 'No predicted label'
                }
            # Try to convert string to int
            label_int = int(predicted_label)
        elif isinstance(predicted_label, int):
            label_int = predicted_label
        else:
            return {
                'raw': str(predicted_label),
                'decoded': 'Invalid label type',
                'details': f'Expected int or string, got {type(predicted_label)}'
            }
        
        # Decode the label
        decoded_string = decode_label(label_int, as_string=True)
        decoded_dict = decode_label(label_int, as_string=False)
        
        if isinstance(decoded_dict, dict) and 'error' in decoded_dict:
            return {
                'raw': str(label_int),
                'decoded': decoded_dict.get('error', 'Unknown error'),
                'details': str(decoded_dict.get('reason', 'No additional details'))
            }
        
        # Format detailed information
        details_parts = []
        if isinstance(decoded_dict, dict):
            details_parts.append(f"API Group: {decoded_dict.get('apiGroup', 'N/A')}")
            details_parts.append(f"Version: {decoded_dict.get('version', 'N/A')}")
            details_parts.append(f"Resource: {decoded_dict.get('uri', 'N/A')}")
            details_parts.append(f"Verb: {decoded_dict.get('verb', 'N/A')}")
            details_parts.append(f"Namespaced: {'Yes' if decoded_dict.get('is_namespaced') else 'No'}")
            details_parts.append(f"Single Object: {'Yes' if decoded_dict.get('is_single_object') else 'No'}")
        
        return {
            'raw': str(label_int),
            'decoded': decoded_string,
            'details': ' | '.join(details_parts)
        }
        
    except Exception as e:
        return {
            'raw': str(predicted_label),
            'decoded': f'Decode error: {str(e)}',
            'details': 'Failed to decode label'
        }


# CSS color schemes for different API groups
API_GROUP_COLORS = {
    'core': '#28a745',  # Green
    'apps': '#007bff',  # Blue
    'networking.k8s.io': '#6f42c1',  # Purple
    'rbac.authorization.k8s.io': '#ffc107',  # Yellow
    'admissionregistration.k8s.io': '#17a2b8',  # Cyan
    'apiextensions.k8s.io': '#dc3545',  # Red
    'apiregistration.k8s.io': '#6c757d',  # Gray
    'authentication.k8s.io': '#343a40',  # Dark
    'authorization.k8s.io': '#e83e8c',  # Pink
    'autoscaling': '#fd7e14',  # Orange
    'batch': '#20c997',  # Teal
    'certificates.k8s.io': '#198754',  # Success Green
    'coordination.k8s.io': '#0d6efd',  # Primary Blue
    'discovery.k8s.io': '#d63384',  # Danger Pink
    'events.k8s.io': '#adb5bd',  # Light Gray
    'flowcontrol.apiserver.k8s.io': '#6610f2',  # Indigo
    'node.k8s.io': '#198754',  # Success
    'policy': '#fd7e14',  # Warning Orange
    'scheduling.k8s.io': '#0dcaf0',  # Info Cyan
    'storage.k8s.io': '#6f42c1',  # Purple
    'unknown.fbk.eu': '#dc3545',  # Danger Red
}

def get_api_group_from_object_ref(obj_ref: Optional[Dict[str, Any]]) -> str:
    """Extract API group from objectRef, handling core API special case."""
    if not obj_ref:
        return 'unknown'
    
    api_group = obj_ref.get('apiGroup', '')
    
    # Handle core API (empty apiGroup means core)
    if not api_group:
        return 'core'
    
    return api_group


def get_api_group_from_uri(uri: str) -> str:
    """Extract API group from requestURI as fallback."""
    if uri.startswith('/api/v1/'):
        return 'core'
    elif uri.startswith('/apis/'):
        parts = uri.split('/')
        if len(parts) > 2:
            return parts[2]
    return 'unknown'


def format_timestamp(timestamp: str) -> str:
    """Format timestamp for better readability."""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%H:%M:%S.%f')[:-3]  # Remove microseconds, keep milliseconds
    except:
        return timestamp


def format_user_info(user: Dict[str, Any]) -> str:
    """Format user information."""
    username = user.get('username', 'N/A')
    groups = user.get('groups', [])
    if groups:
        groups_str = ', '.join(groups[:2])  # Show first 2 groups
        if len(groups) > 2:
            groups_str += f" (+{len(groups)-2} more)"
        return f"{username} <small>({groups_str})</small>"
    return username


def format_object_ref(obj_ref: Optional[Dict[str, Any]]) -> str:
    """Format object reference information."""
    if not obj_ref:
        return "N/A"
    
    resource = obj_ref.get('resource', 'N/A')
    namespace = obj_ref.get('namespace')
    name = obj_ref.get('name')
    
    parts = [f"<strong>{resource}</strong>"]
    if namespace:
        parts.append(f"<small>ns:{namespace}</small>")
    if name:
        parts.append(f"<small>name:{name}</small>")
    
    return ' / '.join(parts)


def generate_html_header(title: str) -> str:
    """Generate the HTML header with CSS styles."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background-color: #f8f9fa;
        }}
        
        .audit-entry {{
            background: white;
            border-left: 4px solid #dee2e6;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }}
        
        .audit-entry:hover {{
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            transform: translateY(-1px);
        }}
        
        .api-group-badge {{
            font-weight: bold;
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
        }}
        
        .label-badge {{
            font-weight: bold;
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
        }}
        
        .label-null {{
            background-color: #6c757d;
            color: white;
        }}
        
        .label-predicted {{
            background-color: #28a745;
            color: white;
        }}
        
        .stage-badge {{
            background-color: #17a2b8;
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
        }}
        
        .verb-badge {{
            background-color: #ffc107;
            color: #212529;
            padding: 0.25rem 0.5rem;
            border-radius: 0.375rem;
            font-size: 0.875rem;
            font-weight: bold;
        }}
        
        .timestamp {{
            color: #6c757d;
            font-size: 0.875rem;
        }}
        
        .audit-id {{
            font-family: monospace;
            background-color: #e9ecef;
            padding: 0.125rem 0.25rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
        }}
        
        .uri-text {{
            font-family: monospace;
            background-color: #f8f9fa;
            padding: 0.25rem;
            border-radius: 0.25rem;
            font-size: 0.875rem;
            word-break: break-all;
        }}
        
        .stats-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        .filter-info {{
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
        }}
        
        .table-hover tbody tr:hover {{
            background-color: #f8f9fa;
        }}
        
        .sticky-header {{
            position: sticky;
            top: 0;
            background-color: #fff;
            z-index: 100;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>"""


def generate_html_footer() -> str:
    """Generate the HTML footer."""
    return """
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Add smooth scrolling
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({
                    behavior: 'smooth'
                });
            });
        });
        
        // Add copy functionality for audit IDs
        document.querySelectorAll('.audit-id').forEach(element => {
            element.style.cursor = 'pointer';
            element.title = 'Click to copy';
            element.addEventListener('click', function() {
                navigator.clipboard.writeText(this.textContent);
                const original = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => this.textContent = original, 1000);
            });
        });
    </script>
</body>
</html>"""


def generate_entry_html(entry: Dict[str, Any], entry_num: int, show_full: bool = False) -> str:
    """Generate HTML for a single audit log entry."""
    
    # Extract key information
    audit_id = entry.get('auditID', 'N/A')[:8]  # Short ID
    stage = entry.get('stage', 'N/A')
    verb = entry.get('verb', 'N/A')
    predicted_label = entry.get('predicted_label')
    obj_ref = entry.get('objectRef')
    user = entry.get('user', {})
    request_uri = entry.get('requestURI', 'N/A')
    timestamp = entry.get('requestReceivedTimestamp', 'N/A')
    
    # Determine API group
    api_group = get_api_group_from_object_ref(obj_ref)
    if api_group == 'unknown':
        api_group = get_api_group_from_uri(request_uri)
    
    # Get API group color
    api_group_color = API_GROUP_COLORS.get(api_group, '#6c757d')
    
    # Decode the predicted label
    label_info = decode_and_format_label(predicted_label)
    
    # Format other badges
    stage_html = f'<span class="stage-badge">📋 {html.escape(stage)}</span>'
    verb_html = f'<span class="verb-badge">⚡ {html.escape(verb)}</span>'
    api_group_html = f'<span class="api-group-badge" style="background-color: {api_group_color}">🔧 {html.escape(api_group)}</span>'
    
    # Format object reference
    obj_ref_html = format_object_ref(obj_ref)
    
    # Format user information
    user_html = format_user_info(user)
    
    # Generate main entry HTML
    html_content = f"""
    <div class="audit-entry mb-4" id="entry-{entry_num}" style="border-left-color: {api_group_color}">
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <h4 class="card-title mb-0">
                    <i class="fas fa-list-ol text-muted"></i> Entry #{entry_num}
                    <span class="audit-id">{html.escape(audit_id)}</span>
                </h4>
                <span class="timestamp">
                    <i class="fas fa-clock"></i> {html.escape(format_timestamp(timestamp))}
                </span>
            </div>
            
            <!-- SECTION 1: PREDICTED LABEL -->
            <div class="card mb-3" style="border-left: 4px solid #ffc107;">
                <div class="card-header bg-warning text-dark">
                    <h5 class="mb-0"><i class="fas fa-tag"></i> 🏷️ Predicted Label</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-12">
                            <strong>Raw Label:</strong><br>
    """
    
    # Add predicted label display
    if predicted_label is not None:
        html_content += f'<span class="badge bg-success fs-6">{html.escape(label_info["raw"])}</span>'
    else:
        html_content += '<span class="badge bg-secondary fs-6">NULL</span>'
    
    html_content += """
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- SECTION 2: DECODED LABEL -->
            <div class="card mb-3" style="border-left: 4px solid #17a2b8;">
                <div class="card-header bg-info text-white">
                    <h5 class="mb-0"><i class="fas fa-search"></i> 🔍 Decoded Label</h5>
                </div>
                <div class="card-body">
    """
    
    # Add decoded label information
    if 'error' not in label_info['decoded'].lower() and label_info['decoded'] != 'NULL':
        html_content += f"""
                    <div class="mb-2">
                        <strong>Decoded:</strong><br>
                        <span class="badge bg-primary fs-6">{html.escape(label_info['decoded'])}</span>
                    </div>
        """
        if label_info['details'] and 'No additional details' not in label_info['details']:
            html_content += f"""
                    <div class="mb-2">
                        <strong>Details:</strong><br>
                        <small class="text-muted">{html.escape(label_info['details'])}</small>
                    </div>
            """
    else:
        html_content += f"""
                    <div class="mb-2">
                        <strong>Decoded:</strong><br>
                        <span class="badge bg-secondary fs-6">{html.escape(label_info['decoded'])}</span>
                    </div>
        """
        if label_info['details'] and 'No label to decode' not in label_info['details']:
            html_content += f"""
                    <div class="mb-2">
                        <strong>Details:</strong><br>
                        <small class="text-danger">{html.escape(label_info['details'])}</small>
                    </div>
            """
    
    html_content += f"""
                </div>
            </div>
            
            <!-- SECTION 3: ACTUAL AUDIT INFORMATION -->
            <div class="card mb-3" style="border-left: 4px solid #28a745;">
                <div class="card-header bg-success text-white">
                    <h5 class="mb-0"><i class="fas fa-clipboard-list"></i> 📋 Actual Audit Information</h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-md-4 mb-2">
                            <strong><i class="fas fa-cog"></i> Stage:</strong><br>
                            {stage_html}
                        </div>
                        <div class="col-md-4 mb-2">
                            <strong><i class="fas fa-bolt"></i> Verb:</strong><br>
                            {verb_html}
                        </div>
                        <div class="col-md-4 mb-2">
                            <strong><i class="fas fa-layer-group"></i> API Group:</strong><br>
                            {api_group_html}
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <strong><i class="fas fa-cube"></i> Object:</strong><br>
                            <span style="color: {api_group_color}">{obj_ref_html}</span>
                        </div>
                        <div class="col-md-6">
                            <strong><i class="fas fa-user"></i> User:</strong><br>
                            {user_html}
                        </div>
                    </div>
                    
                    <div class="mb-2">
                        <strong><i class="fas fa-link"></i> Request URI:</strong><br>
                        <div class="uri-text">{html.escape(request_uri)}</div>
                    </div>
    """
    
    # Add response status if available
    response_status = entry.get('responseStatus')
    if response_status:
        code = response_status.get('code', 'N/A')
        status_color = '#28a745' if str(code).startswith('2') else '#dc3545'
        html_content += f"""
                    <div class="mb-2">
                        <strong><i class="fas fa-reply"></i> Response:</strong>
                        <span class="badge" style="background-color: {status_color}">HTTP {code}</span>
                    </div>
        """
    
    # Show additional details in full mode
    if show_full:
        source_ips = entry.get('sourceIPs', [])
        if source_ips:
            html_content += f"""
                    <div class="mb-2">
                        <strong><i class="fas fa-map-marker-alt"></i> Source IPs:</strong>
                        {', '.join(html.escape(ip) for ip in source_ips)}
                    </div>
            """
        
        annotations = entry.get('annotations', {})
        if annotations:
            auth_decision = annotations.get('authorization.k8s.io/decision')
            if auth_decision:
                decision_color = '#28a745' if auth_decision == 'allow' else '#dc3545'
                html_content += f"""
                    <div class="mb-2">
                        <strong><i class="fas fa-shield-alt"></i> Auth Decision:</strong>
                        <span class="badge" style="background-color: {decision_color}">{html.escape(auth_decision)}</span>
                    </div>
                """
    
    html_content += """
                </div>
            </div>
        </div>
    </div>
    """
    
    return html_content


def generate_statistics_html(entries: list) -> str:
    """Generate HTML for summary statistics."""
    total = len(entries)
    with_labels = sum(1 for e in entries if e.get('predicted_label') is not None)
    without_labels = total - with_labels
    
    # Count API groups
    api_groups = {}
    for entry in entries:
        obj_ref = entry.get('objectRef')
        api_group = get_api_group_from_object_ref(obj_ref)
        if api_group == 'unknown':
            api_group = get_api_group_from_uri(entry.get('requestURI', ''))
        api_groups[api_group] = api_groups.get(api_group, 0) + 1
    
    # Count verbs
    verbs = {}
    for entry in entries:
        verb = entry.get('verb', 'unknown')
        verbs[verb] = verbs.get(verb, 0) + 1
    
    # Count stages
    stages = {}
    for entry in entries:
        stage = entry.get('stage', 'unknown')
        stages[stage] = stages.get(stage, 0) + 1
    
    html_content = f"""
    <div class="card stats-card mb-4" id="statistics">
        <div class="card-body">
            <h3 class="card-title"><i class="fas fa-chart-bar"></i> Statistics Summary</h3>
            
            <div class="row text-center mb-4">
                <div class="col-md-4">
                    <h2>{total}</h2>
                    <p>Total Entries</p>
                </div>
                <div class="col-md-4">
                    <h2>{with_labels}</h2>
                    <p>With Labels</p>
                </div>
                <div class="col-md-4">
                    <h2>{without_labels}</h2>
                    <p>Without Labels</p>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-4">
                    <h5><i class="fas fa-cogs"></i> Top API Groups</h5>
                    <div class="table-responsive">
                        <table class="table table-sm table-hover">
                            <tbody>
    """
    
    for api_group, count in sorted(api_groups.items(), key=lambda x: x[1], reverse=True)[:10]:
        color = API_GROUP_COLORS.get(api_group, '#6c757d')
        html_content += f"""
                                <tr>
                                    <td>
                                        <span class="api-group-badge" style="background-color: {color}">
                                            {html.escape(api_group)}
                                        </span>
                                    </td>
                                    <td class="text-end"><strong>{count}</strong></td>
                                </tr>
        """
    
    html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <h5><i class="fas fa-bolt"></i> Top Verbs</h5>
                    <div class="table-responsive">
                        <table class="table table-sm table-hover">
                            <tbody>
    """
    
    for verb, count in sorted(verbs.items(), key=lambda x: x[1], reverse=True)[:10]:
        html_content += f"""
                                <tr>
                                    <td><span class="verb-badge">{html.escape(verb)}</span></td>
                                    <td class="text-end"><strong>{count}</strong></td>
                                </tr>
        """
    
    html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <h5><i class="fas fa-layer-group"></i> Top Stages</h5>
                    <div class="table-responsive">
                        <table class="table table-sm table-hover">
                            <tbody>
    """
    
    for stage, count in sorted(stages.items(), key=lambda x: x[1], reverse=True)[:10]:
        html_content += f"""
                                <tr>
                                    <td><span class="stage-badge">{html.escape(stage)}</span></td>
                                    <td class="text-end"><strong>{count}</strong></td>
                                </tr>
        """
    
    html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    
    return html_content


def main():
    parser = argparse.ArgumentParser(
        description="HTML visual checker for K8s audit log predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python visual_checker_html.py audit_logs.json
  python visual_checker_html.py audit_logs.json --limit 10 --output report.html
  python visual_checker_html.py audit_logs.json --full --stats
  python visual_checker_html.py audit_logs.json --filter-api-group core
        """
    )
    
    parser.add_argument('json_file', help='Path to the JSON file containing audit log entries')
    parser.add_argument('--output', '-o', help='Output HTML file path (default: audit_report.html)')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of entries to display')
    parser.add_argument('--skip', type=int, default=0, help='Skip first N entries')
    parser.add_argument('--full', '-f', action='store_true', help='Show full details for each entry')
    parser.add_argument('--stats', '-s', action='store_true', help='Show statistics summary')
    parser.add_argument('--filter-api-group', help='Filter entries by API group')
    parser.add_argument('--filter-verb', help='Filter entries by verb')
    parser.add_argument('--filter-stage', help='Filter entries by stage')
    parser.add_argument('--filter-label', help='Filter entries by predicted label')
    
    args = parser.parse_args()
    
    # Set default output file
    if not args.output:
        args.output = 'audit_report.html'
    
    # Read JSON file
    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"Error: File '{args.json_file}' not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(json_path, 'r') as f:
            content = f.read().strip()
            
        # Try to parse as regular JSON first
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                entries = [data]
            else:
                entries = data
        except json.JSONDecodeError:
            # If that fails, try JSONL format - one JSON object per line
            entries = []
            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON on line {line_num}: {e}", file=sys.stderr)
                        continue
                            
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{args.json_file}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{args.json_file}': {e}", file=sys.stderr)
        sys.exit(1)
    
    if not entries:
        print("No valid entries found in the file", file=sys.stderr)
        sys.exit(1)
    
    # Apply filters
    filtered_entries = entries
    filter_info = []
    
    if args.filter_api_group:
        filtered_entries = [
            e for e in filtered_entries 
            if get_api_group_from_object_ref(e.get('objectRef')) == args.filter_api_group
            or get_api_group_from_uri(e.get('requestURI', '')) == args.filter_api_group
        ]
        filter_info.append(f"API Group: {args.filter_api_group}")
    
    if args.filter_verb:
        filtered_entries = [e for e in filtered_entries if e.get('verb') == args.filter_verb]
        filter_info.append(f"Verb: {args.filter_verb}")
    
    if args.filter_stage:
        filtered_entries = [e for e in filtered_entries if e.get('stage') == args.filter_stage]
        filter_info.append(f"Stage: {args.filter_stage}")
    
    if args.filter_label:
        filtered_entries = [e for e in filtered_entries if str(e.get('predicted_label')) == args.filter_label]
        filter_info.append(f"Label: {args.filter_label}")
    
    # Apply skip
    if args.skip > 0:
        filtered_entries = filtered_entries[args.skip:]
        filter_info.append(f"Skipped first {args.skip} entries")
    
    # Apply limit
    if args.limit:
        filtered_entries = filtered_entries[:args.limit]
        filter_info.append(f"Limited to {args.limit} entries")
    
    # Generate HTML
    title = f"K8s Audit Log Report - {Path(args.json_file).name}"
    html_content = generate_html_header(title)
    
    # Add main container
    html_content += f"""
    <div class="container-fluid py-4">
        <div class="sticky-header py-3 mb-4">
            <div class="row align-items-center">
                <div class="col">
                    <h1 class="mb-0">
                        <i class="fas fa-shield-alt text-primary"></i>
                        K8s Audit Log Visual Report
                    </h1>
                    <p class="text-muted mb-0">
                        <i class="fas fa-file"></i> {html.escape(args.json_file)} | 
                        <i class="fas fa-list"></i> Total: {len(entries)} entries | 
                        <i class="fas fa-eye"></i> Showing: {len(filtered_entries)} entries
                    </p>
                </div>
                <div class="col-auto">
                    <a href="#statistics" class="btn btn-outline-primary btn-sm">
                        <i class="fas fa-chart-bar"></i> Statistics
                    </a>
                </div>
            </div>
        </div>
    """
    
    # Add filter information if any filters are applied
    if filter_info:
        html_content += f"""
        <div class="alert filter-info mb-4">
            <h6><i class="fas fa-filter"></i> Active Filters:</h6>
            <ul class="mb-0">
                {''.join(f'<li>{html.escape(info)}</li>' for info in filter_info)}
            </ul>
        </div>
        """
    
    # Add statistics if requested
    if args.stats:
        html_content += generate_statistics_html(filtered_entries)
    
    # Add entries
    html_content += '<div id="entries">'
    for i, entry in enumerate(filtered_entries, 1):
        html_content += generate_entry_html(entry, i, args.full)
    html_content += '</div>'
    
    # Close container
    html_content += '</div>'
    
    # Add footer
    html_content += generate_html_footer()
    
    # Write HTML file
    try:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML report generated successfully: {output_path.absolute()}")
        print(f"Open in browser: file://{output_path.absolute()}")
        
    except Exception as e:
        print(f"Error writing HTML file '{args.output}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()