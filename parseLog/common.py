from typing import Iterable

from tqdm import tqdm as tqdm_base

IGNORED_NAMESPACES = {
    "falco",
    "kube-flannel"
}
LABEL_UNKNOWN = -1
LABEL_IGNORE = -2


def tqdm(array: Iterable) -> Iterable:
    return tqdm_base(array, ncols=200, leave=False)


def exists_subkey(__object, *keys):
    exists = True
    for key in keys:
        if key not in __object:
            exists = False
            break
        __object = __object[key]

    return exists
