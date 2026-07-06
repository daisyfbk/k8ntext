#!/usr/bin/env python3
"""
K8NTEXT Timeline Visualizer

Reads a clusterized Kubernetes audit log (JSONL, each line a JSON object
enriched with uuid_new) and produces a self-contained interactive HTML page.

Features:
- Horizontal scrolling timeline.
- One row per user on the y-axis.
- Colored dots for every action; triggering actions are drawn as large dots.
- Multiple color palettes: by cluster, trigger verb, trigger user, or trigger
  resource type.
- Click a triggering action to highlight its entire cluster; all other actions
  are greyed out.
- User filter panel to show/hide rows.  When a cluster is selected, any user
  with an action in that cluster is automatically shown.
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow imports from the project root and parseLog sub-package.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PARSELOG_DIR = _PROJECT_ROOT / "parseLog"
for p in (_PROJECT_ROOT, _PARSELOG_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from parseLog.clusterizer import is_triggering_action  # noqa: E402
from parseLog.common import LABEL_UNKNOWN, LABEL_IGNORE  # noqa: E402
from parseLog.parameters import TIMESTAMP_KEY  # noqa: E402

DEFAULT_LABEL_KEY = "label"
UUID_KEY = "uuid_new"
PALETTE_CLUSTER = "cluster"
PALETTE_VERB = "verb"
PALETTE_USER = "user"
PALETTE_RESOURCE = "resource"
PALETTES = [PALETTE_CLUSTER, PALETTE_VERB, PALETTE_USER, PALETTE_RESOURCE]


def _timestamp_to_seconds(ts: str) -> float:
    """Parse an ISO timestamp to seconds since epoch."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(ts).timestamp()


def _format_timestamp(ts: str) -> str:
    """Return a human-readable timestamp string."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _username(line: dict) -> str:
    """Extract the username from a log line, tolerating missing fields."""
    user = line.get("user") or {}
    return user.get("username", "unknown")


def _object_ref_field(line: dict, field: str) -> Any:
    """Safely read a field from objectRef."""
    ref = line.get("objectRef") or {}
    return ref.get(field)


def _action_summary(line: dict) -> str:
    """Short textual summary of an action for tooltips/inspectors."""
    verb = line.get("verb", "?")
    resource = _object_ref_field(line, "resource") or "?"
    namespace = _object_ref_field(line, "namespace")
    name = _object_ref_field(line, "name")
    ns_part = f"/{namespace}" if namespace else ""
    name_part = f"/{name}" if name else ""
    return f"{verb} {resource}{ns_part}{name_part}"


def _color_for_key(key: str, saturation: float = 70, lightness: float = 50) -> str:
    """Deterministic HSL color from an arbitrary string key."""
    hue = hash(key) % 360
    return f"hsl({hue}, {saturation}%, {lightness}%)"


def _dark_color_for_key(key: str) -> str:
    """A slightly darker variant for strokes."""
    return _color_for_key(key, saturation=75, lightness=35)


def short_username(username: str) -> str:
    """Return a shortened username for display purposes."""
    if username.startswith("system:serviceaccount:"):
        return "sys:sa:" + username.split(":", 2)[-1]
    if username.startswith("system:"):
        return "sys:" + username.split(":", 1)[-1]
    return username


def load_clusterized_log(path: str, label_key: str = DEFAULT_LABEL_KEY) -> list[dict]:
    """Load a JSONL file and enrich each line with derived fields."""
    actions = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, raw in enumerate(f):
            raw = raw.strip()
            if not raw:
                continue
            line = json.loads(raw)
            ts = line.get(TIMESTAMP_KEY)
            if not ts:
                continue
            try:
                seconds = _timestamp_to_seconds(ts)
            except Exception:
                continue

            uuid = line.get(UUID_KEY)
            if uuid is None:
                # The visualizer requires UUIDs.  Skip lines without them.
                continue

            trigger = is_triggering_action(line, label_key)
            actions.append({
                "index": idx,
                "raw": line,
                "uuid": uuid,
                "timestamp": ts,
                "seconds": seconds,
                "username": _username(line),
                "summary": _action_summary(line),
                "is_trigger": trigger,
                "label": line.get(label_key, LABEL_UNKNOWN),
            })
    return actions


def _trigger_action_for_cluster(cluster_actions: list[dict]) -> dict | None:
    """Return the triggering action for a cluster, if any."""
    for a in cluster_actions:
        if a["is_trigger"]:
            return a
    # Fallback: return the earliest action if no explicit trigger was found.
    if cluster_actions:
        return min(cluster_actions, key=lambda a: a["seconds"])
    return None


def _cluster_color_key(
    uuid: str,
    cluster_actions: list[dict],
    palette: str,
) -> str:
    """Return the key used to pick a color for a cluster under the given palette."""
    if palette == PALETTE_CLUSTER:
        return uuid
    trigger = _trigger_action_for_cluster(cluster_actions)
    if trigger is None:
        return uuid
    if palette == PALETTE_VERB:
        return trigger["raw"].get("verb", "unknown")
    if palette == PALETTE_USER:
        return _username(trigger["raw"])
    if palette == PALETTE_RESOURCE:
        return _object_ref_field(trigger["raw"], "resource") or "unknown"
    return uuid


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K8NTEXT Timeline</title>
    <style>
        :root {
            --bg: #f8f9fa;
            --panel-bg: #ffffff;
            --text: #212529;
            --muted: #6c757d;
            --border: #dee2e6;
            --highlight-row: rgba(255, 235, 59, 0.15);
            --greyed: #adb5bd;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            overflow: hidden;
        }
        #app {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        #header {
            padding: 12px 16px;
            background: var(--panel-bg);
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 16px;
            align-items: center;
            flex-wrap: wrap;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        #header h1 {
            margin: 0;
            font-size: 1.1rem;
            font-weight: 600;
        }
        .control-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        label { font-size: 0.85rem; color: var(--muted); }
        button {
            background: #0d6efd;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 0.85rem;
            cursor: pointer;
        }
        button:hover { background: #0b5ed7; }
        button.secondary {
            background: #6c757d;
        }
        button.secondary:hover { background: #5c636a; }
        input[type="range"] { width: 140px; }
        #main {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        #sidebar {
            width: 300px;
            background: var(--panel-bg);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-section {
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }
        .sidebar-section h2 {
            margin: 0 0 10px 0;
            font-size: 0.9rem;
            font-weight: 600;
        }
        #user-filters {
            flex: 1;
            overflow-y: auto;
        }
        .user-toggle {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 0;
            font-size: 0.8rem;
            cursor: pointer;
            user-select: none;
            min-width: 0;
        }
        .user-toggle input { cursor: pointer; }
        .user-toggle span {
            display: block;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        #cluster-info {
            max-height: 35%;
            overflow-y: auto;
        }
        .cluster-info-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 0;
            font-size: 0.78rem;
            cursor: pointer;
        }
        .cluster-info-item:hover { background: var(--bg); }
        .cluster-info-item.selected { font-weight: bold; background: var(--highlight-row); }
        .cluster-swatch {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .cluster-id {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            word-break: break-all;
        }
        .cluster-stats {
            margin-left: auto;
            color: var(--muted);
            white-space: nowrap;
        }
        #timeline-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            position: relative;
        }
        #y-axis {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 240px;
            background: rgba(248,249,250,0.95);
            border-right: 1px solid var(--border);
            z-index: 2;
            overflow: hidden;
        }
        #y-axis-content {
            position: relative;
            will-change: transform;
        }
        .user-label {
            position: absolute;
            left: 0;
            right: 0;
            height: __ROW_HEIGHT__px;
            display: flex;
            align-items: center;
            padding: 0 8px;
            box-sizing: border-box;
            font-size: 0.78rem;
            font-weight: 500;
        }
        .user-label-text {
            display: block;
            width: 100%;
            min-width: 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .user-label.hidden-user { color: var(--greyed); text-decoration: line-through; }
        #timeline-scroll {
            flex: 1;
            overflow-x: auto;
            overflow-y: auto;
            margin-left: 240px;
            position: relative;
            background: #fff;
        }
        svg { display: block; }
        .grid-line { stroke: #e9ecef; stroke-width: 1; }
        .tick-label {
            font-size: 10px;
            fill: var(--muted);
            text-anchor: middle;
        }
        .row-separator { stroke: #e9ecef; stroke-width: 1; }
        .user-row { fill: transparent; }
        .user-row:hover { fill: var(--highlight-row); }
        .action-dot {
            transition: opacity 0.2s ease, transform 0.2s ease;
        }
        /* Default state: everything visible and colorful */
        .action-dot { opacity: 1; }

        /* When a cluster is selected, dim everything first... */
        body.has-selection .action-dot {
            opacity: 0.08;
            filter: grayscale(0.8);
        }
        body.has-selection .user-row { opacity: 0.4; }
        body.has-selection .user-label { opacity: 0.4; }

        /* ...then re-highlight dots and rows belonging to the selected cluster */
        body.has-selection .action-dot.cluster-selected {
            opacity: 1;
            filter: none;
            stroke-width: 3;
        }
        body.has-selection .user-row.cluster-selected {
            opacity: 1;
            fill: var(--highlight-row);
        }
        body.has-selection .user-label.cluster-selected {
            opacity: 1;
            font-weight: 700;
        }

        /* Hidden users are removed from the packed layout */
        .user-row.user-hidden { display: none; }
        .user-label.user-hidden { display: none; }
        .action-dot.user-hidden { display: none; }

        #detail-panel {
            position: absolute;
            right: 16px;
            top: 16px;
            width: 320px;
            max-height: calc(100% - 32px);
            background: var(--panel-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
            padding: 12px;
            overflow-y: auto;
            z-index: 10;
            display: none;
        }
        #detail-panel h3 {
            margin: 0 0 8px 0;
            font-size: 0.95rem;
        }
        #detail-panel .close {
            float: right;
            background: none;
            border: none;
            color: var(--muted);
            font-size: 1.2rem;
            line-height: 1;
            padding: 0 4px;
            cursor: pointer;
        }
        .detail-action {
            font-size: 0.78rem;
            padding: 6px 0;
            border-bottom: 1px solid var(--border);
        }
        .detail-action:last-child { border-bottom: none; }
        .detail-action .ts { color: var(--muted); }
        .detail-action .user { font-weight: 600; }
        .detail-action .summary { font-family: "SFMono-Regular", Consolas, monospace; }
        .empty-state {
            padding: 20px;
            color: var(--muted);
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div id="app">
        <div id="header">
            <h1>K8NTEXT Timeline Visualizer</h1>
            <div class="control-group">
                <label for="zoom-slider">Zoom:</label>
                <input id="zoom-slider" type="range" min="0.5" max="100" step="0.5" value="__PIXELS_PER_SECOND__">
                <span id="zoom-value">__PIXELS_PER_SECOND__x</span>
            </div>
            <div class="control-group">
                <button onclick="scrollToStart()">Start</button>
                <button onclick="scrollToEnd()">End</button>
            </div>
            <div class="control-group">
                <button class="secondary" onclick="resetSelection()">Reset selection</button>
                <button class="secondary" onclick="showAllUsers()">Show all users</button>
                <button class="secondary" onclick="deselectAllUsers()">Deselect all users</button>
            </div>
            <div class="control-group">
                <span id="stats">__STATS__</span>
            </div>
        </div>
        <div id="main">
            <div id="sidebar">
                <div class="sidebar-section" id="user-filters">
                    <h2>Users</h2>
                    __USER_CHECKBOXES__
                </div>
                <div class="sidebar-section" id="cluster-info">
                    <h2>Clusters</h2>
                    __CLUSTER_INFO_ITEMS__
                </div>
            </div>
            <div id="timeline-wrapper">
                <div id="y-axis">
                    <div id="y-axis-content">__USER_LABELS__</div>
                </div>
                <div id="timeline-scroll">
                    <svg id="timeline-svg" width="__TIMELINE_WIDTH__" height="__TOTAL_HEIGHT__" xmlns="http://www.w3.org/2000/svg">
                        __GRID_ELEMENTS__
                        __ROW_ELEMENTS__
                        __ACTION_ELEMENTS__
                    </svg>
                </div>
                <div id="detail-panel">
                    <button class="close" onclick="resetSelection()">&times;</button>
                    <h3 id="detail-title">Cluster</h3>
                    <div id="detail-content"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const users = __USERS_JSON__;
        const actions = __ACTIONS_JSON__;
        const rowHeight = __ROW_HEIGHT__;
        const timelineStart = __TIMELINE_START__;
        const timelineEnd = __TIMELINE_END__;
        const baseScale = __PIXELS_PER_SECOND__;
        const normalRadius = __NORMAL_RADIUS__;
        const triggerRadius = __TRIGGER_RADIUS__;
        const allUsersVisibleHeight = __TOTAL_HEIGHT__;

        let currentScale = baseScale;
        let selectedUuid = null;
        let packedVisibleUsers = false;

        const svg = document.getElementById('timeline-svg');
        const scrollArea = document.getElementById('timeline-scroll');
        const yAxis = document.getElementById('y-axis');
        const yAxisContent = document.getElementById('y-axis-content');
        const zoomSlider = document.getElementById('zoom-slider');
        const zoomValue = document.getElementById('zoom-value');
        const detailPanel = document.getElementById('detail-panel');
        const detailTitle = document.getElementById('detail-title');
        const detailContent = document.getElementById('detail-content');
        const baseUserRow = Object.fromEntries(users.map((user, idx) => [user, idx]));

        function isUserVisible(user) {
            const cb = document.querySelector('.user-toggle input[data-user="' + user + '"]');
            return !!(cb && cb.checked);
        }

        function getUserRowMap() {
            if (!packedVisibleUsers) {
                return baseUserRow;
            }

            const rowMap = {};
            let visibleRow = 0;
            users.forEach(user => {
                if (!isUserVisible(user)) return;
                rowMap[user] = visibleRow;
                visibleRow += 1;
            });
            return rowMap;
        }

        function getVisibleUserCount() {
            return users.filter(isUserVisible).length;
        }

        function refreshLayout() {
            const rowMap = getUserRowMap();
            const visibleUserCount = getVisibleUserCount();
            const totalHeight = packedVisibleUsers
                ? Math.max(rowHeight, visibleUserCount * rowHeight + rowHeight)
                : allUsersVisibleHeight;

            svg.setAttribute('height', totalHeight);
            yAxis.style.height = totalHeight + 'px';
            yAxisContent.style.height = totalHeight + 'px';

            document.querySelectorAll('.user-label').forEach(label => {
                const user = label.dataset.user;
                const visible = isUserVisible(user);
                label.classList.toggle('user-hidden', !visible);
                if (!visible) return;
                const row = rowMap[user];
                label.style.top = (row * rowHeight) + 'px';
                label.style.height = rowHeight + 'px';
            });

            document.querySelectorAll('.user-row').forEach(row => {
                const user = row.dataset.user;
                const visible = isUserVisible(user);
                row.classList.toggle('user-hidden', !visible);
                if (!visible) return;
                row.setAttribute('y', rowMap[user] * rowHeight);
            });

            document.querySelectorAll('.row-separator').forEach(line => {
                const user = line.dataset.user;
                const visible = isUserVisible(user);
                line.classList.toggle('user-hidden', !visible);
                if (!visible) return;
                const y = (rowMap[user] + 1) * rowHeight;
                line.setAttribute('y1', y);
                line.setAttribute('y2', y);
            });

            document.querySelectorAll('.action-dot').forEach(dot => {
                const user = dot.dataset.user;
                const visible = isUserVisible(user);
                dot.classList.toggle('user-hidden', !visible);
                if (!visible) return;
                dot.setAttribute('cy', rowMap[user] * rowHeight + rowHeight / 2);
            });

            document.querySelectorAll('.grid-line').forEach(line => line.setAttribute('y2', totalHeight));
        }

        function xForSeconds(s) {
            return (s - timelineStart) * currentScale;
        }

        function updateScale(scale) {
            const oldScale = currentScale;
            const viewportWidth = scrollArea.clientWidth;
            const centerOffset = scrollArea.scrollLeft + viewportWidth / 2;
            const centerSeconds = timelineStart + centerOffset / oldScale;

            currentScale = parseFloat(scale);
            zoomValue.textContent = currentScale.toFixed(1) + 'x';
            const width = (timelineEnd - timelineStart) * currentScale;
            svg.setAttribute('width', width);
            // Move dots to their new positions.
            document.querySelectorAll('.action-dot').forEach(dot => {
                const s = parseFloat(dot.dataset.seconds);
                dot.setAttribute('cx', xForSeconds(s));
            });
            // Stretch row backgrounds and separators.
            document.querySelectorAll('.user-row').forEach(row => row.setAttribute('width', width));
            document.querySelectorAll('.row-separator').forEach(line => line.setAttribute('x2', width));
            // Rebuild grid lines from scratch so ticks stay correct.
            const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            gridGroup.setAttribute('class', 'grid-layer');
            const tickCount = Math.max(10, Math.min(50, Math.floor(width / 150)));
            const duration = timelineEnd - timelineStart;
            for (let i = 0; i <= tickCount; i++) {
                const frac = i / tickCount;
                const s = timelineStart + frac * duration;
                const x = xForSeconds(s);
                const date = new Date(s * 1000);
                const label = date.toISOString().substr(11, 8);
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', x);
                line.setAttribute('y1', 0);
                line.setAttribute('x2', x);
                line.setAttribute('y2', svg.getAttribute('height'));
                line.setAttribute('class', 'grid-line');
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', x);
                text.setAttribute('y', 20);
                text.setAttribute('class', 'tick-label');
                text.textContent = label;
                gridGroup.appendChild(line);
                gridGroup.appendChild(text);
            }
            const oldGrid = svg.querySelector('.grid-layer');
            if (oldGrid) oldGrid.remove();
            svg.insertBefore(gridGroup, svg.firstChild);

            // Keep the same center point in view after zooming.
            const newScrollLeft = (centerSeconds - timelineStart) * currentScale - viewportWidth / 2;
            scrollArea.scrollLeft = Math.max(0, newScrollLeft);
        }

        zoomSlider.addEventListener('input', e => updateScale(e.target.value));

        function toggleUser(checkbox) {
            if (checkbox.checked) {
                packedVisibleUsers = false;
            }
            refreshLayout();
        }

        function showAllUsers() {
            document.querySelectorAll('.user-toggle input').forEach(cb => cb.checked = true);
            packedVisibleUsers = false;
            refreshLayout();
        }

        function deselectAllUsers() {
            document.querySelectorAll('.user-toggle input').forEach(cb => {
                cb.checked = false;
            });
            packedVisibleUsers = false;
            refreshLayout();
        }

        function scrollToStart() {
            scrollArea.scrollLeft = 0;
        }

        function scrollToEnd() {
            scrollArea.scrollLeft = scrollArea.scrollWidth;
        }

        function resetSelection() {
            selectedUuid = null;
            document.body.classList.remove('has-selection');
            document.querySelectorAll('.cluster-selected').forEach(el => el.classList.remove('cluster-selected'));
            document.querySelectorAll('.cluster-info-item.selected').forEach(el => el.classList.remove('selected'));
            detailPanel.style.display = 'none';
        }

        function selectCluster(uuid) {
            selectedUuid = uuid;
            document.body.classList.add('has-selection');
            document.querySelectorAll('.cluster-selected').forEach(el => el.classList.remove('cluster-selected'));
            document.querySelectorAll('.cluster-info-item.selected').forEach(el => el.classList.remove('selected'));

            const visibleUsersBeforeSelection = getVisibleUserCount();

            // Highlight all dots belonging to this cluster and ensure their users are visible.
            document.querySelectorAll('.action-dot[data-uuid="' + uuid + '"]').forEach(dot => {
                dot.classList.add('cluster-selected');
                const user = dot.dataset.user;
                document.querySelectorAll('[data-user="' + user + '"]').forEach(el => {
                    el.classList.remove('user-hidden');
                    if (el.classList.contains('user-row') || el.classList.contains('user-label')) {
                        el.classList.add('cluster-selected');
                    }
                });
                const cb = document.querySelector('.user-toggle input[data-user="' + user + '"]');
                if (cb) cb.checked = true;
            });

            packedVisibleUsers = visibleUsersBeforeSelection === 0;
            refreshLayout();

            document.querySelectorAll('.action-dot[data-uuid="' + uuid + '"]').forEach(dot => {
                dot.classList.add('cluster-selected');
                const user = dot.dataset.user;
                document.querySelectorAll('.user-row[data-user="' + user + '"], .user-label[data-user="' + user + '"]').forEach(el => {
                    el.classList.add('cluster-selected');
                });
            });

            const info = document.querySelector('.cluster-info-item[data-uuid="' + uuid + '"]');
            if (info) info.classList.add('selected');

            renderDetailPanel(uuid);
        }

        function renderDetailPanel(uuid) {
            const clusterActions = actions.filter(a => a.uuid === uuid).sort((a, b) => a.seconds - b.seconds);
            if (clusterActions.length === 0) return;
            detailTitle.textContent = 'Cluster ' + uuid;
            detailTitle.style.color = clusterActions[0].color;
            detailContent.innerHTML = clusterActions.map(a =>
                '<div class="detail-action">' +
                    '<div class="ts">' + a.timestamp + '</div>' +
                    '<div><span class="user">' + a.user + '</span> &middot; <span class="summary">' + a.summary + '</span>' + (a.is_trigger ? ' 🎯' : '') + '</div>' +
                '</div>'
            ).join('');
            detailPanel.style.display = 'block';
        }

        // Click handlers for all action dots.
        document.querySelectorAll('.action-dot').forEach(dot => {
            dot.addEventListener('click', e => {
                e.stopPropagation();
                selectCluster(dot.dataset.uuid);
            });
        });

        // Click on cluster info item selects that cluster.
        document.querySelectorAll('.cluster-info-item').forEach(item => {
            item.addEventListener('click', () => selectCluster(item.dataset.uuid));
        });

        scrollArea.addEventListener('scroll', () => {
            yAxisContent.style.transform = 'translateY(' + (-scrollArea.scrollTop) + 'px)';
        });

        // Click on background resets.
        scrollArea.addEventListener('click', e => {
            if (e.target === scrollArea || e.target === svg) {
                resetSelection();
            }
        });

        // Keyboard shortcuts.
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') resetSelection();
        });

        refreshLayout();
    </script>
</body>
</html>
"""


def build_html(
    actions: list[dict],
    output_path: str,
    pixels_per_second: float = 5.0,
    row_height: int = 60,
    normal_radius: int = 5,
    trigger_radius: int = 18,
    palette: str = PALETTE_CLUSTER,
) -> None:
    """Render the actions to a self-contained interactive HTML file."""
    if not actions:
        raise ValueError("No actions to visualize.")

    users = sorted({short_username(a["username"]) for a in actions})
    user_to_row = {u: i for i, u in enumerate(users)}
    clusters: dict[str, list[dict]] = {}
    for a in actions:
        clusters.setdefault(a["uuid"], []).append(a)

    # Compute a stable color for each cluster according to the chosen palette.
    cluster_color: dict[str, str] = {}
    for uuid, cluster_actions in clusters.items():
        key = _cluster_color_key(uuid, cluster_actions, palette)
        cluster_color[uuid] = _color_for_key(key)

    min_ts = min(a["seconds"] for a in actions)
    max_ts = max(a["seconds"] for a in actions)
    duration = max_ts - min_ts
    if duration <= 0:
        duration = 1.0

    padding_seconds = duration * 0.05
    timeline_start = min_ts - padding_seconds
    timeline_end = max_ts + padding_seconds
    timeline_width = (timeline_end - timeline_start) * pixels_per_second
    total_height = len(users) * row_height + row_height

    def x_for_seconds(s: float) -> float:
        return (s - timeline_start) * pixels_per_second

    def _build_action_circle(a: dict) -> str:
        x = x_for_seconds(a["seconds"])
        y = user_to_row[short_username(a["username"])] * row_height + row_height // 2
        color = cluster_color[a["uuid"]]
        stroke = _dark_color_for_key(_cluster_color_key(a["uuid"], clusters[a["uuid"]], palette))
        radius = trigger_radius if a["is_trigger"] else normal_radius
        cursor = "pointer"
        title = (
            f"{_format_timestamp(a['timestamp'])}\n"
            f"{_username(a['raw'])}\n"
            f"{a['summary']}\n"
            f"cluster: {a['uuid']}\n"
            f"trigger: {'yes' if a['is_trigger'] else 'no'}"
        )
        trigger_attr = 'data-trigger="true"' if a["is_trigger"] else ""
        return (
            f'<circle class="action-dot" '
            f'data-uuid="{a["uuid"]}" '
            f'data-user="{short_username(a["username"])}" '
            f'data-idx="{a["index"]}" '
            f'data-seconds="{a["seconds"]}" '
            f'{trigger_attr} '
            f'cx="{x:.2f}" cy="{y:.2f}" r="{radius}" '
            f'fill="{color}" stroke="{stroke}" stroke-width="2" '
            f'title="{title}" '
            f'style="cursor:{cursor};" />'
        )

    # Build action elements.  Draw non-trigger dots first so that larger trigger
    # dots are rendered on top and remain clickable even when they overlap with
    # other actions from the same cluster.
    action_elements: list[str] = [
        _build_action_circle(a) for a in actions if not a["is_trigger"]
    ]
    action_elements.extend(_build_action_circle(a) for a in actions if a["is_trigger"])

    # Build grid lines and time ticks.
    grid_elements: list[str] = []
    tick_count = max(10, min(50, int(timeline_width // 150)))
    for i in range(tick_count + 1):
        frac = i / tick_count
        s = timeline_start + frac * (timeline_end - timeline_start)
        x = x_for_seconds(s)
        dt = datetime.datetime.fromtimestamp(s, tz=datetime.timezone.utc)
        label = dt.strftime("%H:%M:%S")
        grid_elements.append(
            f'<line x1="{x:.2f}" y1="0" x2="{x:.2f}" y2="{total_height}" '
            f'class="grid-line" />'
        )
        grid_elements.append(
            f'<text x="{x:.2f}" y="20" class="tick-label">{label}</text>'
        )

    # Build user rows (background highlights and separator lines).
    row_elements: list[str] = []
    for i, user in enumerate(users):
        y = i * row_height
        row_elements.append(
            f'<rect class="user-row" x="0" y="{y}" width="{timeline_width}" '
            f'height="{row_height}" data-user="{user}" />'
        )
        row_elements.append(
            f'<line x1="0" y1="{y + row_height}" x2="{timeline_width}" '
            f'y2="{y + row_height}" class="row-separator" data-user="{user}" />'
        )

    # User filter panel.
    user_checkboxes = []
    for user in users:
        user_checkboxes.append(
            f'<label class="user-toggle">'
            f'<input type="checkbox" checked data-user="{user}" '
            f'onchange="toggleUser(this)"><span>{user}</span></label>'
        )

    # Cluster legend/info, sorted by size descending.
    cluster_info_items = []
    sorted_clusters = sorted(clusters.items(), key=lambda item: len(item[1]), reverse=True)
    for uuid, cluster_actions in sorted_clusters:
        size = len(cluster_actions)
        triggers = sum(1 for a in cluster_actions if a["is_trigger"])
        cluster_info_items.append(
            f'<div class="cluster-info-item" data-uuid="{uuid}">'
            f'<span class="cluster-swatch" style="background:{cluster_color[uuid]}"></span>'
            f'<span class="cluster-id">{uuid}</span>'
            f'<span class="cluster-stats">{size} actions, {triggers} trigger(s)</span>'
            f'</div>'
        )

    # Precompute data for the JavaScript front-end.
    js_actions = [
        {
            "index": a["index"],
            "uuid": a["uuid"],
            "user": short_username(a["username"]),
            "timestamp": _format_timestamp(a["timestamp"]),
            "summary": a["summary"],
            "is_trigger": a["is_trigger"],
            "seconds": a["seconds"],
            "color": cluster_color[a["uuid"]],
        }
        for a in actions
    ]

    # Wrap grid elements in a group so zoom rebuilds can replace them cleanly.
    grid_elements = [
        '<g class="grid-layer">',
        *grid_elements,
        '</g>',
    ]

    replacements = {
        "__ROW_HEIGHT__": str(row_height),
        "__PIXELS_PER_SECOND__": str(pixels_per_second),
        "__TIMELINE_WIDTH__": f"{timeline_width:.2f}",
        "__TOTAL_HEIGHT__": str(total_height),
        "__TIMELINE_START__": f"{timeline_start:.6f}",
        "__TIMELINE_END__": f"{timeline_end:.6f}",
        "__NORMAL_RADIUS__": str(normal_radius),
        "__TRIGGER_RADIUS__": str(trigger_radius),
        "__STATS__": f"{len(actions)} actions · {len(users)} users · {len(clusters)} clusters",
        "__USER_LABELS__": "\n".join(
            f'<div class="user-label" data-user="{u}" '
            f'style="top:{i*row_height}px;height:{row_height}px;"><span class="user-label-text">{u}</span></div>'
            for i, u in enumerate(users)
        ),
        "__GRID_ELEMENTS__": "\n".join(grid_elements),
        "__ROW_ELEMENTS__": "\n".join(row_elements),
        "__ACTION_ELEMENTS__": "\n".join(action_elements),
        "__USER_CHECKBOXES__": "\n".join(user_checkboxes),
        "__CLUSTER_INFO_ITEMS__": "\n".join(cluster_info_items),
        "__USERS_JSON__": json.dumps(users),
        "__ACTIONS_JSON__": json.dumps(js_actions),
    }

    html = HTML_TEMPLATE
    for marker, value in replacements.items():
        html = html.replace(marker, value)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an interactive K8NTEXT timeline HTML from a clusterized JSONL log."
    )
    parser.add_argument("-f", "--file", required=True, help="Input clusterized JSONL file (with uuid_new).")
    parser.add_argument("-o", "--output", default="timeline.html", help="Output HTML file.")
    parser.add_argument("-k", "--label-key", default=DEFAULT_LABEL_KEY, help="Key used for labels.")
    parser.add_argument("--scale", type=float, default=5.0, help="Pixels per second (default: 5).")
    parser.add_argument(
        "--palette",
        choices=PALETTES,
        default=PALETTE_CLUSTER,
        help=(
            "Color palette for dots. "
            "'cluster' (default) colors by cluster UUID; "
            "'verb' by the triggering action's verb; "
            "'user' by the triggering action's user; "
            "'resource' by the triggering action's resource type."
        ),
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    actions = load_clusterized_log(args.file, label_key=args.label_key)
    if not actions:
        print("Error: no valid actions found in the input file.", file=sys.stderr)
        sys.exit(1)

    build_html(actions, args.output, pixels_per_second=args.scale, palette=args.palette)
    print(f"Timeline written to: {args.output}")


if __name__ == "__main__":
    main()
