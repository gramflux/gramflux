"""Minimal legal shapes for every generated constructor, not live API coverage."""

from collections import defaultdict

from gramflux.tl import Codec
from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.model import python_name


def test_all_generated_constructors_minimal_roundtrip():
    by_result = defaultdict(list)
    for cls in REGISTRY.values():
        if not cls.definition.method and cls.definition.name != "vector":
            by_result[cls.definition.result].append(cls)
    for group in by_result.values():
        group.sort(
            key=lambda c: sum(p.type != "#" and "?" not in p.type for p in c.definition.params)
        )

    def make_type(t, ancestors):
        primitives = {
            "int": 0,
            "long": 0,
            "double": 0.0,
            "string": "",
            "bytes": b"",
            "int128": bytes(16),
            "int256": bytes(32),
            "Bool": False,
        }
        if t in primitives:
            return primitives[t]
        if t.startswith(("Vector<", "vector<")):
            return []
        if t == "Object":
            t = "Null"
        for candidate in by_result[t]:
            if candidate not in ancestors:
                try:
                    return make_object(candidate, ancestors)
                except RecursionError:
                    continue
        raise RecursionError(t)

    def make_object(cls, ancestors):
        if len(ancestors) > 30:
            raise RecursionError(cls.definition.name)
        values = {}
        for p in cls.definition.params:
            if p.type == "#":
                continue
            if "?" in p.type:
                values[python_name(p.name)] = False if p.type.endswith("?true") else None
            else:
                values[python_name(p.name)] = make_type(p.type, ancestors | {cls})
        return cls(**values)

    codec = Codec()
    checked = 0
    for group in by_result.values():
        for cls in group:
            obj = make_object(cls, set())
            assert codec.decode(codec.encode(obj)) == obj, cls.definition.name
            checked += 1
    assert checked == 1572  # vector is exercised by typed vector tests instead
