"""Synthetic values for required native TL fields in tests, never production defaults."""

from datetime import datetime

from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.model import python_name


def native_date(value):
    return int(value.timestamp()) if isinstance(value, datetime) else value or 0


def fixture_field(kind, depth=0):
    if kind in ("int", "long", "#", "double"):
        return 0
    if kind == "string":
        return ""
    if kind == "bytes":
        return b""
    if kind in ("Bool", "true"):
        return False
    if kind in ("int128", "int256"):
        return bytes(16 if kind == "int128" else 32)
    if kind.startswith(("Vector<", "vector<")):
        return []
    choices = [
        cls
        for cls in REGISTRY.values()
        if not cls.definition.method
        and cls.definition.result == kind
        and cls.definition.name != "vector"
    ]
    if not choices or depth > 8:
        raise ValueError(f"no safe synthetic fixture for {kind}")
    choices.sort(
        key=lambda cls: len(
            [p for p in cls.definition.params if p.type != "#" and "?" not in p.type]
        )
    )
    for cls in choices:
        try:
            return cls(
                **{
                    python_name(p.name): fixture_field(p.type, depth + 1)
                    for p in cls.definition.params
                    if p.type != "#" and "?" not in p.type
                }
            )
        except ValueError:
            continue
    raise ValueError(f"recursive fixture for {kind}")
