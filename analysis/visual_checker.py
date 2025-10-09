#!/usr/bin/env python3
"""
Visual Checker for K8s Audit Log Predictions

This tool displays Kubernetes audit log entries with color-coded output
based on API groups and shows predicted labels alongside key information.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

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

# ANSI color codes for different API groups
API_GROUP_COLORS = {
    'core': '\033[92m',  # Green
    'apps': '\033[94m',  # Blue
    'networking.k8s.io': '\033[95m',  # Magenta
    'rbac.authorization.k8s.io': '\033[93m',  # Yellow
    'admissionregistration.k8s.io': '\033[96m',  # Cyan
    'apiextensions.k8s.io': '\033[91m',  # Red
    'apiregistration.k8s.io': '\033[97m',  # White
    'authentication.k8s.io': '\033[90m',  # Dark Gray
    'authorization.k8s.io': '\033[35m',  # Purple
    'autoscaling': '\033[33m',  # Orange-ish
    'batch': '\033[36m',  # Dark Cyan
    'certificates.k8s.io': '\033[32m',  # Dark Green
    'coordination.k8s.io': '\033[34m',  # Dark Blue
    'discovery.k8s.io': '\033[31m',  # Dark Red
    'events.k8s.io': '\033[37m',  # Light Gray
    'flowcontrol.apiserver.k8s.io': '\033[45m',  # Background Magenta
    'node.k8s.io': '\033[42m',  # Background Green
    'policy': '\033[43m',  # Background Yellow
    'scheduling.k8s.io': '\033[44m',  # Background Blue
    'storage.k8s.io': '\033[46m',  # Background Cyan
    'unknown.fbk.eu': '\033[41m',  # Background Red
}

# Reset color
RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'

# Special colors for labels and status
LABEL_COLOR = '\033[103m\033[30m'  # Yellow background, black text
NULL_LABEL_COLOR = '\033[100m\033[37m'  # Gray background, white text
VERB_COLOR = '\033[102m\033[30m'  # Green background, black text
STAGE_COLOR = '\033[104m\033[37m'  # Blue background, white text


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


def colorize_api_group(api_group: str, text: str) -> str:
    """Apply color based on API group."""
    color = API_GROUP_COLORS.get(api_group, '\033[37m')  # Default to light gray
    return f"{color}{text}{RESET}"


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
        return f"{username} ({groups_str})"
    return username


def format_object_ref(obj_ref: Optional[Dict[str, Any]]) -> str:
    """Format object reference information."""
    if not obj_ref:
        return "N/A"
    
    resource = obj_ref.get('resource', 'N/A')
    namespace = obj_ref.get('namespace')
    name = obj_ref.get('name')
    
    parts = [resource]
    if namespace:
        parts.append(f"ns:{namespace}")
    if name:
        parts.append(f"name:{name}")
    
    return '/'.join(parts)


def print_audit_entry(entry: Dict[str, Any], entry_num: int, show_full: bool = False):
    """Print a single audit log entry with color formatting."""
    
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
    
    # Decode the predicted label
    label_info = decode_and_format_label(predicted_label)
    
    # Format stage and verb
    stage_display = f"{STAGE_COLOR} {stage} {RESET}"
    verb_display = f"{VERB_COLOR} {verb} {RESET}"
    
    # Format API group with color
    api_group_display = colorize_api_group(api_group, f" {api_group} ")
    
    # Print entry header
    print(f"\n{BOLD}{'═' * 80}{RESET}")
    print(f"{BOLD}Entry #{entry_num}{RESET} [{format_timestamp(timestamp)}] {audit_id}")
    print(f"Stage: {stage_display} | Verb: {verb_display} | API Group: {api_group_display}")
    print(f"{BOLD}{'═' * 80}{RESET}")
    
    # SECTION 1: PREDICTED LABEL
    print(f"\n{BOLD}🏷️  PREDICTED LABEL{RESET}")
    print(f"{'─' * 40}")
    if predicted_label is not None:
        print(f"Raw Label: {LABEL_COLOR} {label_info['raw']} {RESET}")
    else:
        print(f"Raw Label: {NULL_LABEL_COLOR} NULL {RESET}")
    
    # SECTION 2: DECODED LABEL
    print(f"\n{BOLD}🔍 DECODED LABEL{RESET}")
    print(f"{'─' * 40}")
    decoded_color = LABEL_COLOR if 'error' not in label_info['decoded'].lower() else NULL_LABEL_COLOR
    print(f"Decoded: {decoded_color} {label_info['decoded']} {RESET}")
    if label_info['details'] and 'No additional details' not in label_info['details']:
        print(f"Details: {DIM}{label_info['details']}{RESET}")
    
    # SECTION 3: ACTUAL AUDIT INFORMATION
    print(f"\n{BOLD}📋 ACTUAL AUDIT INFORMATION{RESET}")
    print(f"{'─' * 40}")
    
    # Object reference with detailed breakdown
    obj_ref_str = format_object_ref(obj_ref)
    print(f"📦 {BOLD}Object:{RESET} {colorize_api_group(api_group, obj_ref_str)}")
    if obj_ref:
        resource = obj_ref.get('resource', 'N/A')
        namespace = obj_ref.get('namespace', 'cluster-scoped')
        api_version = obj_ref.get('apiVersion', 'N/A')
        name = obj_ref.get('name', 'N/A')
        print(f"   ├─ Resource: {colorize_api_group(api_group, resource)}")
        print(f"   ├─ API Version: {api_version}")
        print(f"   ├─ Namespace: {namespace}")
        if name != 'N/A':
            print(f"   └─ Name: {name}")
    
    # User information with detailed breakdown
    user_info = format_user_info(user)
    print(f"👤 {BOLD}User:{RESET} {user_info}")
    if user:
        username = user.get('username', 'N/A')
        groups = user.get('groups', [])
        print(f"   ├─ Username: {username}")
        if groups:
            print(f"   └─ Groups: {', '.join(groups[:3])}")
            if len(groups) > 3:
                print(f"             (+{len(groups)-3} more groups)")
    
    # Verb with emphasis
    print(f"⚡ {BOLD}Action/Verb:{RESET} {verb_display}")
    
    # Print request URI
    print(f"🔗 {BOLD}Request URI:{RESET}")
    if show_full or len(request_uri) <= 100:
        print(f"   {request_uri}")
    else:
        print(f"   {request_uri[:97]}...")
    
    # Show response status if available
    response_status = entry.get('responseStatus')
    if response_status:
        code = response_status.get('code', 'N/A')
        status_color = '\033[92m' if str(code).startswith('2') else '\033[91m'
        print(f"📤 {BOLD}Response:{RESET} {status_color}HTTP {code}{RESET}")
    
    # Show additional details in full mode
    if show_full:
        print(f"\n{BOLD}📊 ADDITIONAL DETAILS{RESET}")
        print(f"{'─' * 40}")
        
        source_ips = entry.get('sourceIPs', [])
        if source_ips:
            print(f"🌐 Source IPs: {', '.join(source_ips)}")
        
        annotations = entry.get('annotations', {})
        if annotations:
            auth_decision = annotations.get('authorization.k8s.io/decision')
            if auth_decision:
                decision_color = '\033[92m' if auth_decision == 'allow' else '\033[91m'
                print(f"🛡️  Auth Decision: {decision_color}{auth_decision}{RESET}")
        
        # Show important fields for context
        user_agent = entry.get('userAgent', '')
        if user_agent:
            print(f"🖥️  User Agent: {user_agent}")
    
    print(f"{BOLD}{'═' * 80}{RESET}")


def print_statistics(entries: list):
    """Print summary statistics."""
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
    
    print(f"\n{BOLD}=== STATISTICS ==={RESET}")
    print(f"Total entries: {total}")
    print(f"With predicted labels: {with_labels}")
    print(f"Without predicted labels: {without_labels}")
    
    print(f"\n{BOLD}Top API Groups:{RESET}")
    for api_group, count in sorted(api_groups.items(), key=lambda x: x[1], reverse=True)[:10]:
        color_group = colorize_api_group(api_group, api_group)
        print(f"  {color_group}: {count}")
    
    print(f"\n{BOLD}Top Verbs:{RESET}")
    for verb, count in sorted(verbs.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {verb}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Visual checker for K8s audit log predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python visual_checker.py audit_logs.json
  python visual_checker.py audit_logs.json --limit 10
  python visual_checker.py audit_logs.json --full --stats
  python visual_checker.py audit_logs.json --filter-api-group core
  python visual_checker.py audit_logs.json --filter-verb list
        """
    )
    
    parser.add_argument('json_file', help='Path to the JSON file containing audit log entries')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of entries to display')
    parser.add_argument('--skip', type=int, default=0, help='Skip first N entries')
    parser.add_argument('--full', '-f', action='store_true', help='Show full details for each entry')
    parser.add_argument('--stats', '-s', action='store_true', help='Show statistics summary')
    parser.add_argument('--filter-api-group', help='Filter entries by API group')
    parser.add_argument('--filter-verb', help='Filter entries by verb')
    parser.add_argument('--filter-stage', help='Filter entries by stage')
    parser.add_argument('--filter-label', help='Filter entries by predicted label')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    
    args = parser.parse_args()
    
    # Disable colors if requested
    if args.no_color:
        global API_GROUP_COLORS, RESET, BOLD, DIM, LABEL_COLOR, NULL_LABEL_COLOR, VERB_COLOR, STAGE_COLOR
        API_GROUP_COLORS = {k: '' for k in API_GROUP_COLORS}
        RESET = BOLD = DIM = LABEL_COLOR = NULL_LABEL_COLOR = VERB_COLOR = STAGE_COLOR = ''
    
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
    
    if args.filter_api_group:
        filtered_entries = [
            e for e in filtered_entries 
            if get_api_group_from_object_ref(e.get('objectRef')) == args.filter_api_group
            or get_api_group_from_uri(e.get('requestURI', '')) == args.filter_api_group
        ]
    
    if args.filter_verb:
        filtered_entries = [e for e in filtered_entries if e.get('verb') == args.filter_verb]
    
    if args.filter_stage:
        filtered_entries = [e for e in filtered_entries if e.get('stage') == args.filter_stage]
    
    if args.filter_label:
        filtered_entries = [e for e in filtered_entries if str(e.get('predicted_label')) == args.filter_label]
    
    # Apply skip
    if args.skip > 0:
        filtered_entries = filtered_entries[args.skip:]
    
    # Apply limit
    if args.limit:
        filtered_entries = filtered_entries[:args.limit]
    
    # Print header
    print(f"{BOLD}K8s Audit Log Visual Checker{RESET}")
    print(f"File: {args.json_file}")
    print(f"Total entries: {len(entries)}, Showing: {len(filtered_entries)}")
    print("=" * 80)
    
    # Display entries
    for i, entry in enumerate(filtered_entries, 1):
        print_audit_entry(entry, i, args.full)
    
    # Show statistics if requested
    if args.stats:
        print_statistics(filtered_entries)
    
    print(f"\n{BOLD}=== END ==={RESET}")


if __name__ == '__main__':
    main()