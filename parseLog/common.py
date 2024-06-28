IGNORED_NAMESPACES = {
    "falco",
    "kube-flannel"
}
LABEL_UNKNOWN = -1
LABEL_IGNORE = -2


from typing import Iterable
from tqdm import tqdm as tqdm_base

def tqdm(array: Iterable) -> Iterable:
    return tqdm_base(array, ncols=200, leave=False)
    