import os
import operator
from functools import reduce
from typing import Any


def get_by_path(root, items):
    """Access a nested object in root by item sequence."""
    return reduce(operator.getitem, items, root)


def _env_name(keys):
    """e.g. ('weather', 'apikey') -> 'WEATHER_APIKEY'."""
    return "_".join(str(k).upper() for k in keys)


def _coerce_env(raw, reference):
    """Coerce a string env-var value to match the type of `reference`."""
    if isinstance(reference, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(reference, int):
        return int(raw)
    if isinstance(reference, float):
        return float(raw)
    if isinstance(reference, list):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return raw


def _resolve(keys, yaml_lookup, default, required) -> Any:
    """
    Resolve a config value with env-var override.

    Precedence: env var (auto-derived name) > yaml value > default. Env strings
    are coerced to match the yaml value's type, or the default's type if the
    yaml key is absent.
    """
    raw_env = os.environ.get(_env_name(keys))
    try:
        yaml_val = yaml_lookup()
        yaml_present = True
    except (KeyError, TypeError):
        yaml_val = None
        yaml_present = False

    if raw_env is not None:
        reference = yaml_val if yaml_present else default
        return _coerce_env(raw_env, reference) if reference is not None else raw_env

    if yaml_present:
        return yaml_val

    if default is None and required:
        raise KeyError("{} not in config but is required".format(".".join(keys)))
    return default


def get_prop_by_keys(config, *keys, default=None, required=True, dehumanized=False) -> Any:
    return _resolve(keys, lambda: get_by_path(config, keys), default, required)


def get_prop(config, prop, default=None, required=True, dehumanized=False) -> Any:
    return _resolve((prop,), lambda: config[prop], default, required)

def even_select(n, l):
    if n == 1:
        return [l[0]]
    return [l[round(i * (len(l) - 1) / (n - 1))] for i in range(n)]