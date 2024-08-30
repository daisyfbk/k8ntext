import datetime
import json
import re

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np
import networkx as nx

from query_parser import QueryParser


def get_resources_string(action):
    text = ""
    if action.get('namespace') is not None:
        text += action.get('namespace') + "/"
    if action.get('resource') is not None:
        text += action.get('resource') + "/"
    if action.get('subresource') is not None:
        text += action.get('subresource') + "/"
    if action.get('name') is not None:
        text += action.get('name')
    return text


class AuditGraph:

    def __init__(self, actions_dict, dict_divided_by_label, query):
        # define all the dictionaries useful to the visualization part
        self.actions_dict = actions_dict
        self.dict_divided_by_label = dict_divided_by_label

        self.users_actions = {}
        for action_key, action_value in self.actions_dict.items():
            user = action_value.get('username')
            user_actions = self.users_actions.get(user)
            if not user_actions:
                user_actions = []
                self.users_actions[user] = user_actions

            user_actions.append(action_key)

        self.dict_divided_by_uuid = {}
        for log_lines in self.dict_divided_by_label.values():
            for log_line in log_lines:
                uuid = log_line.get('UUID')
                # add line dict_divided_by_label
                if uuid not in self.dict_divided_by_uuid:
                    self.dict_divided_by_uuid[uuid] = []
                self.dict_divided_by_uuid.get(uuid).append(log_line)

        # To create dict_divided_by_uuid dictionary we iterate dict_divided_by_label dictionary. If no log line has
        # been assigned to an action, the id of that action will not be present. This causes visualization problem.
        # Thus, add actions missing uuid.
        for log_line in self.actions_dict.values():
            uuid = log_line.get('UUID')
            if uuid not in self.dict_divided_by_uuid:
                self.dict_divided_by_uuid[uuid] = [log_line]

        self.verbs_color = {
            "create": "#009E73",
            "patch": "#56B4E9",
            "update": "#0072B2",
            "delete": "#D55E00",
            "deletecollection": "#CC79A7",
            "get": "#F0E442",
            "list": "#E69F00",
            "watch": "#333333"
        }

        self.query = query

    def on_click(self, event, ax, sc, actions):
        if event.inaxes == ax:
            cont, ind = sc.contains(event)
            if cont:
                fig2, ax2 = plt.subplots(figsize=(12, 6))

                action = self.actions_dict.get(actions[ind["ind"][0]])

                plt.suptitle("Action details", fontweight='bold')
                title = action.get('username') + " " + action.get('verb') + " " + get_resources_string(action)
                plt.title(title)

                G = nx.MultiDiGraph()

                # sort log lines based on username. This is done to create a multipartite layout that facilitates the
                # graph visualization
                log_lines = sorted(self.dict_divided_by_uuid.get(action.get('UUID')),
                                   key=lambda z: (z.get('username').startswith('system:'), z.get('username')))
                last_usernode = None
                user_layer = 0

                edges_to_plot = {}

                for log_line in log_lines:
                    user_node = Node({'username': log_line.get('username')})
                    if user_node != last_usernode and user_node is not None:
                        user_layer += 1
                        last_usernode = user_node

                    resource_node = Node({'resource': log_line.get('resource'),
                                          'subresource': log_line.get('subresource'), 'name': log_line.get('name')})

                    resource_layer = user_layer + 1
                    previous_resource_layer = nx.get_node_attributes(G, "subset").get(resource_node)
                    if previous_resource_layer is not None:
                        resource_layer = previous_resource_layer

                    G.add_node(user_node, type='user', subset=user_layer)
                    G.add_node(resource_node, type='resource', subset=resource_layer)
                    edges_to_plot_key = user_node.get_label() + resource_node.get_label(False) + log_line.get('verb')
                    if edges_to_plot_key not in edges_to_plot:
                        edges_to_plot[edges_to_plot_key] = {'user_node': user_node, 'resource_node': resource_node,
                                                            'verb': log_line.get('verb'), 'count': 0}
                    edges_to_plot[edges_to_plot_key]['count'] += 1

                for edge in edges_to_plot.values():
                    if edge.get('count') > 1:
                        new_label = " x" + str(edge.get('count')) + " " + edge.get('verb')
                        G.add_edge(edge.get('user_node'), edge.get('resource_node'), label=new_label)
                    else:
                        G.add_edge(edge.get('user_node'), edge.get('resource_node'), label=edge.get('verb'))

                pos = nx.pos = nx.multipartite_layout(G)
                nodes_labels = {}
                for node in G.nodes():
                    nodes_labels[node] = node.get_label()
                node_color_map = {'user': '#EE3377', 'resource': '#33BBEE'}

                # Generate plot
                nx.draw(G, pos, labels=nodes_labels, node_size=400, font_size=10, width=2, edge_color='#dddddd',
                        node_color=[node_color_map[node[1]['type']] for node in G.nodes(data=True)],
                        connectionstyle=[f"arc3,rad={0.3 * e[2]}" for e in G.edges(keys=True)])

                plt.axis('off')
                hovered_edges_to_remove = False

                def hover_inner_graph(event2):
                    nonlocal hovered_edges_to_remove

                    if event2.inaxes == ax2:
                        for node in G.nodes():
                            if is_mouse_over_node(event2, node):
                                add_labelled_edges(node)
                                hovered_edges_to_remove = True
                                return
                        if hovered_edges_to_remove:
                            remove_labelled_edges()

                def is_mouse_over_node(event2, node):
                    x, y = pos[node]
                    return (event2.xdata - x) ** 2 + (event2.ydata - y) ** 2 < 0.01

                def add_labelled_edges(node):
                    # Get edges for both outgoing and incoming edges
                    edges = [e for e in G.edges(keys=True) if e[0] == node or e[1] == node]
                    nx.draw_networkx_edges(G, pos, edgelist=edges, edge_color='black', ax=ax2,
                                           connectionstyle=[f"arc3,rad={0.3 * e[2]}" for e in edges])
                    # Get edge labels for both outgoing and incoming edges
                    edge_labels = {(e[0], e[1], e[2]): G[e[0]][e[1]][e[2]]['label'] for e in edges}
                    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax2,
                                                 connectionstyle=[f"arc3,rad={0.3 * e[2]}" for e in edges])

                    plt.draw()

                def remove_labelled_edges():
                    ax2.clear()
                    nx.draw(G, pos, labels=nodes_labels, node_size=400, font_size=10, width=2, edge_color='#dddddd',
                            node_color=[node_color_map[node[1]['type']] for node in G.nodes(data=True)],
                            connectionstyle=[f"arc3,rad={0.3 * e[2]}" for e in G.edges(keys=True)])
                    nonlocal hovered_edges_to_remove
                    hovered_edges_to_remove = False
                    plt.title(title)
                    plt.draw()

                fig2.canvas.mpl_connect('motion_notify_event', lambda event2: hover_inner_graph(event2))

                # Show plot
                plt.show(block=False)

    def update_annot(self, index, sc, annot, actions):
        pos = sc.get_offsets()[index]
        annot.xy = pos
        action = self.actions_dict.get(actions[index])
        text = get_resources_string(action)

        annot.set_text(text)
        annot.get_bbox_patch().set_alpha(0.4)

    def hover(self, event, fig, ax, sc, annot, actions):
        vis = annot.get_visible()
        if event.inaxes == ax:
            cont, ind = sc.contains(event)
            if cont:
                self.update_annot(ind["ind"][0], sc, annot, actions)
                annot.set_visible(True)
                fig.canvas.draw_idle()
            else:
                if vis:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()

    def create_user_labels(self, users):
        user_labels = []
        for user in users:
            user_label = user
            if user.startswith('system:'):
                user_label = user_label.split(":")[-1]

            user_labels.append(user_label)
        return user_labels

    def plot_graph(self):
        fig, ax = plt.subplots(figsize=(15, 7.5), layout="constrained")
        plt.suptitle("K8S Audit Logs actions", fontweight='bold')

        # sort alphabetically and leave system: at the end
        users = sorted(self.users_actions.keys(), key=lambda z: (z.startswith('system:'), z))

        users_index = 0
        x, y, actions, dots_color = [], [], [], []

        query_parser = QueryParser()
        users_added_to_chart = []

        for user in users:
            line_color = "black"
            if user.startswith('system:'):
                line_color = "silver"

            any_user_action_added = False
            for user_action in self.users_actions.get(user):
                # plot if query is set and action match or if query is not set
                if ((self.query and query_parser.match(self.actions_dict.get(user_action), self.query))
                        or not self.query):
                    # populate arrays for create points
                    any_user_action_added = True
                    timestamp = self.actions_dict.get(user_action).get('stageTimestamp')
                    date_timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                    x.append(date_timestamp)
                    y.append(users_index)
                    actions.append(user_action)
                    dots_color.append(self.verbs_color[self.actions_dict.get(user_action).get('verb')])

            if any_user_action_added:
                # add a horizontal line for each user
                ax.axhline(users_index, color=line_color, linewidth=2, zorder=0)
                users_index -= 1
                users_added_to_chart.append(user)

        # draw points
        sc = plt.scatter(x, y, color=dots_color, marker='o', zorder=1)

        plt.yticks(np.arange(0, users_index, -1), self.create_user_labels(users_added_to_chart), rotation=30)

        # makes legend
        handles = []
        for verb, color in self.verbs_color.items():
            handles.append(mpatches.Patch(color=color, label=verb))
        box = ax.get_position()
        ax.set_position([box.x0, box.y0 + box.height * 0.07,
                         box.width, box.height * 0.93])
        plt.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, -0.05),
                   fancybox=True, shadow=True, ncol=4)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

        # Remove some spines
        ax.spines[["top", "right"]].set_visible(False)

        # Create an annotation for hover event
        annot = ax.annotate("", xy=(0, 0), xytext=(-20, 20), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w"),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)

        # capture events
        fig.canvas.mpl_connect("motion_notify_event", lambda event: self.hover(event, fig, ax, sc, annot, actions))
        fig.canvas.mpl_connect('button_press_event', lambda event: self.on_click(event, ax, sc, actions))

        plt.show()


class Node:
    def __init__(self, attributes):
        self.attributes = attributes

    def print(self):
        return str(self.attributes)

    def get_label(self, compact_events=True):
        if len(self.attributes) == 1:
            return self.attributes.get('username').split(":")[-1]
        else:
            rs = get_resources_string(self.attributes)
            if rs.startswith('events') and compact_events:
                rs = re.sub("\.[0-9a-f]+$", "", rs)
            l = re.sub("/", "/\n", rs)
            return l

    def __hash__(self):
        encoded = json.dumps(self.attributes, sort_keys=True)
        return hash(encoded)

    def __eq__(self, other):
        if isinstance(other, Node):
            return self.attributes == other.attributes
        return False
