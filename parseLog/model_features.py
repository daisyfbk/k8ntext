import datetime

FEATURE_PREPROCESSING = {
    "requestReceivedTimestamp": lambda x: int(datetime.datetime.fromisoformat(x[:-1]).timestamp()),
    "stageTimestamp": lambda x: int(datetime.datetime.fromisoformat(x[:-1]).timestamp()),
    "userAgent": lambda x: parse_user_agent(x),
}


def parse_user_agent(user_agent: str) -> dict:
    splits = user_agent.split(' ')
    if len(splits) == 1:
        tool = splits[0]
        platform = None
        meta = None
    elif len(splits) == 2:
        tool, platform = splits
        meta = None
    else:
        tool, platform, meta = splits

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


FILTER_FEATURES = [
    # "requestURI",
    "verb",
    "user",
    "sourceIPs",
    "userAgent",
    "objectRef",
    # "cplabel"
    # "requestReceivedTimestamp",
    # "stageTimestamp",
]
EXCLUDE_FEATURES = [
    "objectRef.uid",
    "userAgent.h",
    "userAgent.platform",
    "userAgent.version",
    "sourceIPs[0]",
    "objectRef.resourceVersion",
    "objectRef.apiVersion",
    "userAgent.arch",
    "user.uid",
    "user.extra.authentication.kubernetes.io/pod-name[0]",
    "user.extra.authentication.kubernetes.io/pod-uid[0]",
]
