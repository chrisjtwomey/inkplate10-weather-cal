"""Reading a rendered page in a test.

BeautifulSoup's ``find`` answers with a tag, a bare string, or nothing, so
every lookup is three types wide and a missing element is only discovered one
line later as an attribute error on ``None``. These narrow it to a tag and
say which selector found nothing.
"""
from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def one(node: Tag | BeautifulSoup, *args, **kwargs) -> Tag:
    """The element that must be there."""
    found = node.find(*args, **kwargs)
    assert isinstance(found, Tag), f"no element matching {args or kwargs}"
    return found


def attr(node: Tag, name: str) -> str:
    """An attribute, as the string a test compares against.

    Absent reads as empty, and the few attributes HTML allows to repeat
    (``class`` among them) read as they were written.
    """
    value = node.get(name)
    if value is None:
        return ""
    return " ".join(value) if isinstance(value, list) else value
