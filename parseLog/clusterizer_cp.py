CONTROL_PLANE_UUID = [
    i for i in range(2000, 2030)
]


def is_control_plane_action(log_line: dict) -> int | None:
    # Control plane actions
    # ** API Server watching objects
    # The API server monitors core components with a 10minute
    # timeout. It remains unclear what the API server watches in other groups:
    # we probably need to deploy more components to see what the API server
    # watches.
    # - Verb: =watch=
    # - Users: =system:apiserver=
    # - Objects: =configmaps=, =clusterroles=, =namespaces=, =serviceaccounts=,
    #   =resourcequotas=, =clusterrolebindings=, =rolebindings=, =secrets=,
    #   =nodes=, =pods=, =roles=
    # - Namespaces: none, apart from =configmaps= in =kube-system=. Additionally,
    #   if legacy service accounts areused, the API server also watches
    #   =kube-apiserver-legacy-service-account-token-tracking=, a CM in =kube-system=.
    if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:apiserver':
        api_server_watched_objects = [
            'configmaps', 'clusterroles', 'namespaces', 'serviceaccounts',
            'resourcequotas', 'clusterrolebindings', 'rolebindings',
            'secrets', 'nodes', 'pods', 'roles'
        ]
        if log_line.get('resource') in api_server_watched_objects:
            return CONTROL_PLANE_UUID[0]
    # ** =kube-controller-manager= watching objects
    # The =kube-system= namespace watches objects, similar to the API server.
    # However, ConfigMaps are watched over non-namespaced objects and also
    # =certificateigningrequests= are watched.
    # 
    # I believe that the objects watched by the Kube Controller Manager are
    # specific to what is deployed in the cluster. For example, if the
    # cluster has a deployment, the Kube Controller Manager will watch
    # also =deployments=.
    # 
    # - Verb: =watch=
    # - Users: =system:kube-controller-manager=
    # - Objects: same as the API server, plus =certificateigningrequests=
    # - Namespaces: none
    if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:kube-controller-manager':
        kcm_watched_objects = [
            'configmaps', 'clusterroles', 'namespaces', 'serviceaccounts',
            'resourcequotas', 'clusterrolebindings', 'rolebindings',
            'secrets', 'nodes', 'pods', 'roles', 'certificateigningrequests'
        ]
        if log_line.get('resource') in kcm_watched_objects:
            return CONTROL_PLANE_UUID[1]
    # # ** =kube-controller-manager= getting and creating tokens for GC and RQ controllers
    # # The =kube-controller-manager= gets every less than an hour the serviceaccounts
    # # =/api/v1/namespaces/kube-system/serviceaccounts/generic-garbage-collector= and
    # # =/api/v1/namespaces/kube-system/serviceaccounts/resourcequota-controller=.
    # # It then creates tokens for them, which expire in an hour.
    # # *** 1
    # # - Verb: =get=
    # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
    # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/generic-garbage-collector=
    if log_line.get('verb') == 'get' and log_line.get('username') == 'system:kube-controller-manager':
        if log_line.get('resource') == 'serviceaccounts' and \
                log_line.get('namespace') == 'kube-system' and \
                log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
            return CONTROL_PLANE_UUID[2]
    # # *** 2
    # # - Verb: =get=
    # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
    # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/resourcequota-controller=
    if log_line.get('verb') == 'get' and log_line.get('username') == 'system:kube-controller-manager':
        if log_line.get('resource') == 'serviceaccounts' and \
                log_line.get('namespace') == 'kube-system' and \
                log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
            return CONTROL_PLANE_UUID[3]
    # # *** 3
    # # - Verb: =create=
    # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
    # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/generic-garbage-collector/token=
    if log_line.get('verb') == 'create' and log_line.get('username') == 'system:kube-controller-manager':
        if log_line.get('resource') == 'serviceaccounts' and \
                log_line.get('namespace') == 'kube-system' and \
                log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
            return CONTROL_PLANE_UUID[4]
    # # *** 4
    # # - Verb: =create=
    # # - Users: =system:kube-controller-manager=, groups =system:authenticated=
    # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/resourcequota-controller/token=
    if log_line.get('verb') == 'create' and log_line.get('username') == 'system:kube-controller-manager':
        if log_line.get('resource') == 'serviceaccounts' and \
                log_line.get('namespace') == 'kube-system' and \
                log_line.get('name') in ['generic-garbage-collector', 'resourcequota-controller']:
            return CONTROL_PLANE_UUID[5]
    # # ** Kube Scheduler watching objects
    # # The Kube Scheduler watches pods, nodes, namespaces, always with
    # # a 10-minute timeout.
    # # - Verb: =watch=
    # # - Users: =system:kube-scheduler=
    # # - Objects: =pods=, =nodes=, =namespaces=
    # # - Namespaces: none
    if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:kube-scheduler':
        kube_scheduler_watched_objects = [
            'pods', 'nodes', 'namespaces'
        ]
        if log_line.get('resource') in kube_scheduler_watched_objects:
            return CONTROL_PLANE_UUID[6]
    # # *** Extension-apiserver-authentication
    # # This object is also watched by the Kube Scheduler.
    # # - Verb: =watch=
    # # - Users: =system:kube-scheduler=
    # # - Object: =configmaps/extension-apiserver-authentication=
    # # - Namespaces: =kube-system=
    if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:kube-scheduler':
        if log_line.get('resource') == 'configmaps' and \
                log_line.get('namespace') == 'kube-system' and \
                log_line.get('name') == 'extension-apiserver-authentication':
            return CONTROL_PLANE_UUID[7]
    # # ** Nodes watching objects
    # # Each node in the cluster watches pods (non-namespaced), nodes
    # # (themselves), and some configmaps.
    # # *** Pods
    # # - Verb: =watch=
    # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
    # # - Objects: =pods=
    # # - Namespaces: none
    if log_line.get('verb') == 'watch' and log_line.get('username', '').startswith('system:node:'):
        if log_line.get('resource') == 'pods':
            return CONTROL_PLANE_UUID[8]
    # # *** Nodes
    # # - Verb: =watch=
    # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
    # # - Objects: =nodes/{node-name}=
    # # - Namespaces: none
    if log_line.get('verb') == 'watch' and log_line.get('username', '').startswith('system:node:'):
        if log_line.get('resource') == 'nodes':
            return CONTROL_PLANE_UUID[9]
    # # *** ConfigMaps
    # # Every node hosting some Pod of any namespace will be in charge of watching
    # # the serviceaccounts of the Pods that are running.
    # # 
    # # The CMs being watched are =kube-flannel-cfg=, =kube-proxy=, =kube-root-ca.crt=,
    # # and =coredns=. They of course depend on the components deployed in the cluster.
    # # Let's keep this generic.
    # # 
    # # - Verb: =watch=
    # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
    # # - Objects: =configmaps/kube-system/configmaps/{serviceaccount}=
    # # - Namespace: =kube-system=
    if log_line.get('verb') == 'watch' and log_line.get('username', '').startswith('system:node:'):
        if log_line.get('resource') == 'configmaps' and log_line.get('namespace') == 'kube-system':
            return CONTROL_PLANE_UUID[10]
    # # ** Nodes creating tokens
    # # *** Nodes creating tokens for SAs in the kube-system namespace
    # # Since nodes watch the configmaps of the Pods they are running, as the
    # # tokens of their service accounts expire, they will recreate them.
    # # - Verb: =create=
    # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
    # # - Objects: =/api/v1/namespaces/kube-system/serviceaccounts/{serviceaccount}/token=
    if log_line.get('verb') == 'create' and log_line.get('username', '').startswith('system:node:'):
        if log_line.get('resource') == 'serviceaccounts' and log_line.get('namespace') == 'kube-system':
            return CONTROL_PLANE_UUID[11]
    # # ** Nodes getting their own status
    # # Nodes poll their own status every ten seconds.
    # # - Verb: =get=
    # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
    # # - Objects: =/api/v1/nodes/{the same node}=
    if log_line.get('verb') == 'get' and log_line.get('username', '').startswith('system:node:'):
        if log_line.get('resource') == 'nodes':
            return CONTROL_PLANE_UUID[12]
    # # ** Nodes patching their status to update conditions
    # # Nodes update their status (e.g., MemoryPressure, DiskPressure, PIDPressure) by patching their own status
    # # every five minutes.
    # # - Verb: =patch=
    # # - Users: =system:node:.*=, groups =["system:nodes","system:authenticated"]=
    # # - Objects: =/api/v1/nodes/{the same node}=
    if log_line.get('verb') == 'patch' and log_line.get('username', '').startswith('system:node:'):
        if log_line.get('resource') == 'nodes':
            return CONTROL_PLANE_UUID[13]
    # # ** CoreDNS watching namespaces 
    # # - Verb: =watch=
    # # - Users: =system:serviceaccount:kube-system:coredns=
    # # - Objects: =namespaces=
    if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:serviceaccount:kube-system:coredns':
        if log_line.get('resource') == 'namespaces':
            return CONTROL_PLANE_UUID[14]
    # # ** Kube-proxy watching nodes
    # # - Verb: =watch=
    # # - Users: =system:serviceaccount:kube-system:kube-proxy=
    # # - Objects: =nodes=
    if log_line.get('verb') == 'watch' and log_line.get('username') == 'system:serviceaccount:kube-system:kube-proxy':
        if log_line.get('resource') == 'nodes':
            return CONTROL_PLANE_UUID[15]
    # Leases
    # {'username': 'system:kube-controller-manager', 'verb': 'get', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-system', 'name': 'kube-controller-manager', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-controller-manager', 'requestReceivedTimestamp': '2024-07-23T15:51:49.343786Z', 'stageTimestamp': '2024-07-23T15:51:49.347699Z', 'metadata/uid': '774a1d00-f6da-4af8-9e98-d3f07aab0c3e'}
    # {'username': 'system:kube-scheduler', 'verb': 'get', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-system', 'name': 'kube-scheduler', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-scheduler', 'requestReceivedTimestamp': '2024-07-23T15:51:49.377841Z', 'stageTimestamp': '2024-07-23T15:51:49.381077Z', 'metadata/uid': '76cad05e-fbec-4503-88ab-21e9ec9d38fa'}
    # These two go together
    if log_line.get('verb') == 'get' and log_line.get('resource') == 'leases' and \
            log_line.get('namespace') == 'kube-system' and \
            log_line.get('name') in ['kube-controller-manager', 'kube-scheduler']:
        if log_line.get('username') in ['system:kube-controller-manager', 'system:kube-scheduler']:
            return CONTROL_PLANE_UUID[16]
    # Informative dict: {'username': 'system:node:kubeadm-worker1', 'verb': 'update', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-node-lease', 'name': 'kubeadm-worker1', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/kubeadm-worker1', 'requestReceivedTimestamp': '2024-05-28T09:24:12.745411Z', 'stageTimestamp': '2024-05-28T09:24:12.752851Z', 'ownerReferences': [{'apiVersion': 'v1', 'kind': 'Node', 'name': 'kubeadm-worker1', 'uid': 'db6a67cd-b742-4291-a2ca-2861b2968a37'}], 'metadata/uid': '535ef3e4-70b6-4e00-8d2c-f71aad03087d'}
    if log_line.get('verb') == 'update' and log_line.get('resource') == 'leases' and \
            log_line.get('namespace') == 'kube-node-lease':
        if log_line.get('username', '').startswith('system:node:'):
            return CONTROL_PLANE_UUID[17]
    # Informative dict: {'username': 'system:kube-controller-manager', 'verb': 'update', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-system', 'name': 'kube-controller-manager', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-controller-manager', 'requestReceivedTimestamp': '2024-05-28T09:24:14.087182Z', 'stageTimestamp': '2024-05-28T09:24:14.093831Z', 'metadata/uid': '774a1d00-f6da-4af8-9e98-d3f07aab0c3e'}
    if log_line.get('verb') == 'update' and log_line.get('resource') == 'leases' and \
            log_line.get('namespace') == 'kube-system' and \
            log_line.get('name') == 'kube-controller-manager':
        if log_line.get('username') == 'system:kube-controller-manager':
            return CONTROL_PLANE_UUID[18]
    # Informative dict: {'username': 'system:serviceaccount:kube-system:node-controller', 'verb': 'patch', 'resource': 'nodes', 'subresource': None, 'namespace': None, 'name': 'kubeadm-worker1', 'requestURI': '/api/v1/nodes/kubeadm-worker1', 'requestReceivedTimestamp': '2024-07-03T14:22:32.426183Z', 'stageTimestamp': '2024-07-03T14:22:32.445044Z', 'metadata/uid': 'db6a67cd-b742-4291-a2ca-2861b2968a37'}
    if log_line.get('verb') == 'patch' and log_line.get('resource') == 'nodes':
        if log_line.get('username') == 'system:serviceaccount:kube-system:node-controller':
            return CONTROL_PLANE_UUID[19]

    # Informative dict: {'username': 'system:kube-scheduler', 'verb': 'update', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-system', 'name': 'kube-scheduler', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-scheduler', 'requestReceivedTimestamp': '2024-05-28T09:24:17.889294Z', 'stageTimestamp': '2024-05-28T09:24:17.896166Z', 'metadata/uid': '76cad05e-fbec-4503-88ab-21e9ec9d38fa'}
    # Informative dict: {'username': 'system:kube-scheduler', 'verb': 'update', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-system', 'name': 'kube-scheduler', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/kube-scheduler', 'requestReceivedTimestamp': '2024-05-28T09:24:19.904287Z', 'stageTimestamp': '2024-05-28T09:24:19.911503Z', 'metadata/uid': '76cad05e-fbec-4503-88ab-21e9ec9d38fa'}
    if log_line.get('verb') == 'update' and log_line.get('resource') == 'leases' and \
            log_line.get('namespace') == 'kube-system' and \
            log_line.get('name') == 'kube-scheduler':
        if log_line.get('username') in ['system:kube-scheduler']:
            return CONTROL_PLANE_UUID[20]

    # Informative dict: {'username': 'system:apiserver',      'verb': 'update', 'resource': 'leases', 'subresource': None, 'namespace': 'kube-system', 'name': 'apiserver-adpx6exqq66lc64z7ri5spi2yq', 'requestURI': '/apis/coordination.k8s.io/v1/namespaces/kube-system/leases/apiserver-adpx6exqq66lc64z7ri5spi2yq', 'requestReceivedTimestamp': '2024-05-28T09:24:34.384599Z', 'stageTimestamp': '2024-05-28T09:24:34.394065Z', 'metadata/uid': '8d923080-040e-46e2-8a07-924831e68898'}
    if log_line.get('verb') == 'update' and log_line.get('resource') == 'leases' and \
            log_line.get('namespace') == 'kube-system' and \
            log_line.get('name', '').startswith('apiserver-'):
        if log_line.get('username') == 'system:apiserver':
            return CONTROL_PLANE_UUID[21]
    return None
