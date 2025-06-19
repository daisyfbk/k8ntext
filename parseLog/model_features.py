import datetime
from label_proposer import load_verbs


def parse_user_agent(user_agent: str) -> dict:
    splits = user_agent.split(' ')
    if len(splits) == 1:
        tool = splits[0]
        platform = None
        meta = None
    elif len(splits) == 2:
        tool, platform = splits
        meta = None
    elif len(splits) == 3:
        tool, platform, meta = splits
    else:
        tool, platform, *_ = splits
        meta = None

    tool, version = tool.split('/', 1)

    if platform:
        platform = platform.replace('(', '').replace(')', '')
        platform, arch = platform.split('/', 1)
    else:
        platform = None
        arch = None

    if meta:
        meta = meta.split('/')
        if len(meta) == 2:
            _, h = meta
            extra = None
        else:
            _, h, extra = meta
    else:
        h = None
        extra = None

    return {
        "tool": tool,
        "version": version,
        "platform": platform,
        "arch": arch,
        "h": h,
        "extra": extra
    }


def parse_user_agent_wrapper(user_agent: str) -> dict:
    try:
        return parse_user_agent(user_agent)
    except Exception :
        return {
            "tool": None,
            "version": None,
            "platform": None,
            "arch": None,
            "h": None,
            "extra": None
        }


FEATURES = [
    # 'objectRef',
    # 'objectRef.name',
    'objectRef.apiGroup',
    'objectRef.namespace',
    'objectRef.resource',
    'objectRef.subresource',
    'user.groups[0]',
    'user.groups[1]',
    'user.groups[2]',
    # 'user.username',
    'userAgent.extra',
    'userAgent.tool',
    'userAgent.version',
    'verb',
    'requestObject.kind',
    'requestObject.apiVersion',
    'requestObject.metadata.namespace',
    # 'requestObject.metadata.generateName
    'requestObject.metadata.ownerReferences.apiVersion',
    'requestObject.metadata.ownerReferences.kind',
    # 'requestObject.metadata.ownerReferences.name',
    # 'requestObject.metadata.ownerReferences.uid',
    'requestObject.metadata.ownerReferences.controller',
    'requestObject.metadata.ownerReferences.blockOwnerDeletion',
    'requestObject.volumeBindingMode',
    'requestObject.spec.volumeMode',
    'responseObject.spec.volumeMode',
    'responseObject.kind',
    'responseObject.metadata.namespace',
    # 'responseObject.metadata.name',
    # 'responseObject.metadata.resourceVersion',
    'responseObject.metadata.ownerReferences.apiVersion',
    'responseObject.metadata.ownerReferences.kind',
    # 'responseObject.metadata.ownerReferences.name',
    # 'responseObject.metadata.ownerReferences.uid',
    'responseObject.metadata.ownerReferences.controller',
    'responseObject.metadata.ownerReferences.blockOwnerDeletion',
    'responseObject.involvedObject.apiVersion',
    'responseObject.involvedObject.kind',
    # 'responseObject.involvedObject.name',
    'responseObject.involvedObject.namespace',
    'responseObject.involvedObject.resource',
    'responseObject.involvedObject.subresource',
    # 'responseObject.involvedObject.fieldPath',
    'responseObject.reason',
    'responseObject.count',
    'responseObject.type',
    'responseObject.reportingComponent',
    'responseObject.source.component',
    'annotations.authorization.k8s.io/decision',
    'responseStatus.code'
    # 'annotations.authorization.k8s.io/reason',
    # "objectRef.uid",
    # "userAgent.h",
    # "userAgent.platform",
    # "userAgent.version",
    # "sourceIPs[0]",
    # "objectRef.resourceVersion",
    # "objectRef.apiVersion",
    # "userAgent.arch",
    # "user.uid",
    # "user.extra.authentication.kubernetes.io/pod-name[0]",
    # "user.extra.authentication.kubernetes.io/pod-uid[0]",
]

___global_verb_map = load_verbs()

FEATURE_PREPROCESSING = {
    # "requestReceivedTimestamp": lambda x: int(datetime.datetime.fromisoformat(x[:-1]).timestamp()),
    "stageTimestamp": lambda x: int(datetime.datetime.fromisoformat(x[:-1]).timestamp()),
    "userAgent": lambda x: parse_user_agent_wrapper(x),
    "verb": lambda x: ___global_verb_map[x],
    "objectRef.namespace": lambda x: 1 if x is not None and x != '' else 0,
    "responseObject.metadata.namespace": lambda x: 1 if x is not None and x != '' else 0,
    "responseObject.involvedObject.namespace": lambda x: 1 if x is not None and x != '' else 0,
}
