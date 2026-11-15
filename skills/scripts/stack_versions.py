#!/usr/bin/env python3
"""How a tech-stack version is read and compared.

The registry states a minimum per component (``min_versions: {node: "24", typescript: "6.0"}``) and a stack lock
records what the project uses (``versions: {node: "26.1.0", typescript: "6.0.3"}``). Both are text, never numbers: as
a number ``3.10`` is ``3.1``, in JSON and in YAML alike.

The grammar is the one both sides are held to:

* a leading ``v`` is dropped (``v24.1.0``);
* the leading run of dotted whole numbers is the release, compared as a tuple and padded with zeros, so ``6`` equals
  ``6.0`` and ``1.27`` is above ``1.9``;
* a suffix that marks a pre-release (``19.0.0-rc.1``, ``3.13.0rc1``) orders below its release; build metadata after
  ``+`` changes nothing;
* anything that is not one version is refused: a range, a wildcard, a tag or a value with no leading number
  (``^19``, ``24.x``, ``>=3.11``, ``1 || 2``, ``latest``). A lock says which version is in use, not which would do.

Stdlib only: the gate validator loads this.
"""
from __future__ import annotations

import re

__all__ = ["VersionError", "parse", "below", "beyond", "is_version"]

_VERSION = re.compile(r"[vV]?(\d+(?:\.\d+)*)((?:-|\+|[A-Za-z])[0-9A-Za-z.+-]*)?")
_COMPONENT = re.compile(r"[a-z0-9][a-z0-9-]*")


class VersionError(ValueError):
    """The value is not one version in use."""


def parse(value: object) -> tuple:
    """``(release, rank)``: the release as a tuple of whole numbers, and 0 for a pre-release or 1 for a release.
    Raises ``VersionError`` for anything that is not text holding one version."""
    if not isinstance(value, str):
        raise VersionError(f"{value!r} is not text: write a version as a string, because the number 3.10 is 3.1")
    text = value.strip()
    match = _VERSION.fullmatch(text)
    if not match:
        raise VersionError(f"{value!r} is not one version: a range, a wildcard, a tag or a value with no leading number "
                           "does not say which version is in use (write it like 19.1.0)")
    release = tuple(int(part) for part in match.group(1).split("."))
    suffix = match.group(2) or ""
    return release, 1 if not suffix or suffix.startswith("+") else 0


def is_version(value: object) -> bool:
    try:
        parse(value)
    except VersionError:
        return False
    return True


def is_component(name: object) -> bool:
    """A component name the registry accepts: lower-case letters, digits and dashes (``node``, ``rust-edition``)."""
    return isinstance(name, str) and _COMPONENT.fullmatch(name) is not None


def _key(value: object, width: int = 0) -> tuple:
    release, rank = parse(value)
    return release + (0,) * max(0, width - len(release)), rank


def below(version: object, minimum: object) -> bool:
    """Whether ``version`` orders below ``minimum``. ``6`` is not below ``6.0``; ``19.0.0-rc.1`` is below ``19.0.0``."""
    width = max(len(parse(version)[0]), len(parse(minimum)[0]))
    return _key(version, width) < _key(minimum, width)


def beyond(version: object, limit: object) -> bool:
    """Whether ``version`` is past the release line ``limit`` names: ``7.0`` is beyond ``6`` and ``6.9.3`` is not.
    The comparison stops at the precision ``limit`` gives, because a limit of ``6`` means the whole 6 line."""
    limit_release = parse(limit)[0]
    release = parse(version)[0]
    head = (release + (0,) * len(limit_release))[:len(limit_release)]
    return head > limit_release
