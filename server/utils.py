import operator
import numpy as np
from functools import reduce

def get_by_path(root, items):
    """Access a nested object in root by item sequence."""
    return reduce(operator.getitem, items, root)

def get_prop_by_keys(
    config, *keys, default=None, required=True, dehumanized=False
):
    val = default
    found_vals = [get_by_path(config, keys)]

    if len(found_vals) == 0:
        if default is None and required is True:
            raise KeyError("{} not in config but is required".format(".".join(keys)))
    else:
        val = found_vals[0]

    return val


def get_prop(config, prop, default=None, required=True, dehumanized=False):
    val = default

    if prop not in config:
        if default is None and required is True:
            raise KeyError("{} not in config but is required".format(prop))
    else:
        val = config[prop]

    return val

def even_select(n, l):
    indices = np.round(np.linspace(0, len(l) - 1, n)).astype(int)

    selection = []
    for idx in indices:
        selection.append(l[idx])
    return selection