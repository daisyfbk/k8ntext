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