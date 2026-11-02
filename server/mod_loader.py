"""Load the mods: extra pages with their own data, from the folders in ``mods/``.

Each folder holds a ``mod.py``. Its ``setup(mod)`` gives the mod's pages and its
source, or None for a mod that reads only the server's own data. Its optional
``SETTINGS`` gives the fields of its section on the Settings page.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import os
import re
import shutil
import sys
from dataclasses import dataclass
from typing import Any

from epd_server.config import get_prop_by_keys
from epd_server.settings_form import Field, Group, default_of
from epd_server.source import CompositeSource, DataSource

_FOLDER_NAME = re.compile(r"[a-z0-9_]+")


class ModError(Exception):
    """A mod cannot load. The message names it, and the server stops."""


@dataclass(frozen=True)
class Mod:
    """What ``setup`` gets: its name, the arguments for each of its pages, and its settings."""
    name: str
    page_kwargs: dict
    config: dict
    fields: tuple[Field, ...] = ()

    def get(self, key: str) -> Any:
        """The setting ``key``, as the server's own keys resolve: the environment
        variable, config.yaml, the field's default. None when it is blank, so a
        mod with no API key yet still loads and Settings can reach it."""
        field = next((f for f in self.fields if f.key == key), None)
        default = default_of(field, self.config) if field else None
        value = get_prop_by_keys(self.config, "mods", self.name, *key.split("."), default=default, required=False)
        return None if value == "" else value


@dataclass(frozen=True)
class Loaded:
    """The server's pages and source with every mod's added, and each mod's section on Settings."""
    pages: list
    source: DataSource
    groups: tuple[Group, ...]


def _prefixed(field: Field, name: str) -> Field:
    prefix = f"mods.{name}."
    return dataclasses.replace(field, key=prefix + field.key, when=prefix + field.when if field.when else "")


def _import(name: str, path: str):
    spec = importlib.util.spec_from_file_location(f"weather_cal_mod_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copy_files(folder: str, out_dir: str) -> None:
    """Copy a mod's files to where its pages' HTML goes, since the mods folder can
    be read-only and the HTML must sit beside the files it links to. The copies
    take fresh permissions, so a read-only original cannot stop the next write."""
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        target = os.path.join(out_dir, os.path.relpath(root, folder))
        os.makedirs(target, exist_ok=True)
        for file in files:
            if file != "mod.py":
                shutil.copyfile(os.path.join(root, file), os.path.join(target, file))


def _mod_names(mods_dir: str) -> list[str]:
    if not os.path.isdir(mods_dir):
        return []
    names = sorted(n for n in os.listdir(mods_dir)
                   if os.path.isdir(os.path.join(mods_dir, n)) and not n.startswith((".", "_")))
    for name in names:
        if not _FOLDER_NAME.fullmatch(name):
            raise ModError(f"Mod {name}: rename the folder. Use lowercase letters, digits and _ only.")
        if not os.path.isfile(os.path.join(mods_dir, name, "mod.py")):
            raise ModError(f"Mod {name}: the folder has no mod.py.")
    return names


def _load_one(name: str, mods_dir: str, data_dir: str, config: dict, geometry: dict,
              pages: list, sources: list) -> Group | None:
    """Add one mod's pages and source to ``pages`` and ``sources``, and give its Settings section."""
    folder = os.path.join(mods_dir, name)
    out_dir = os.path.join(data_dir, name)
    _copy_files(folder, out_dir)

    module = _import(name, os.path.join(folder, "mod.py"))
    declared = tuple(getattr(module, "SETTINGS", ()))
    mod = Mod(name, {**geometry, "html_dir": out_dir, "png_dir": out_dir}, config, declared)
    mod_pages, mod_source = module.setup(mod)

    taken = {p.png_filename for p in pages}
    for page in mod_pages:
        if page.png_filename in taken:
            raise ModError(f"Mod {name}: another page is already named {page.name}.")
        page.png_path  # noqa: B018 - raises for a page made without mod.page_kwargs
        taken.add(page.png_filename)
    pages.extend(mod_pages)
    if mod_source is not None:
        sources.append(mod_source)

    # A name two sources share, or that no source gives, would otherwise fail every render.
    try:
        known = CompositeSource(*sources).datasets()
    except ValueError as exc:
        raise ModError(f"Mod {name}: {exc}") from None
    missing = sorted({r for page in mod_pages for r in page.requires} - set(known))
    if missing:
        raise ModError(f"Mod {name}: no source gives {', '.join(missing)}.")

    fields = tuple(_prefixed(f, name) for f in declared)
    return Group(name.replace("_", " ").capitalize(), fields) if fields else None


def load_mods(mods_dir: str, data_dir: str, config: dict, geometry: dict, pages: list, sources: list) -> Loaded:
    """Load each folder in ``mods_dir``, in name order. No folder means no mods.

    Raises:
        ModError: a mod cannot load.
    """
    pages, sources, groups = list(pages), list(sources), []
    for name in _mod_names(mods_dir):
        try:
            group = _load_one(name, mods_dir, data_dir, config, geometry, pages, sources)
        except ModError:
            raise
        except Exception as exc:  # noqa: BLE001 - a mod's own code can raise anything
            raise ModError(f"Mod {name} failed to load: {exc!r}") from exc
        if group is not None:
            groups.append(group)
    return Loaded(pages, CompositeSource(*sources), tuple(groups))
