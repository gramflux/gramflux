"""Protocol constructors from the pinned official schema, not competitor bindings."""

from dataclasses import make_dataclass
from pathlib import Path
from typing import Any

from gramflux.tl.codec import Codec
from gramflux.tl.model import TLObject, python_name
from gramflux.tl.parser import parse

DEFINITIONS = {
    d.name: d for d in parse((Path(__file__).parents[1] / "tl/data/mtproto.tl").read_text())
}
CONSTRUCTORS: dict[str, type[TLObject]] = {}
for definition in DEFINITIONS.values():
    if any(
        "%" in p.type or p.type in {"Message", "vector<future_salt>"} for p in definition.params
    ):
        continue
    cls = make_dataclass(
        definition.name,
        [(python_name(p.name), Any) for p in definition.params],
        bases=(TLObject,),
        namespace={"definition": definition},
        slots=True,
        kw_only=True,
        repr=False,
    )
    CONSTRUCTORS[definition.name] = cls
CODEC = Codec({cls.definition.id: cls for cls in CONSTRUCTORS.values()})


def object(name: str, **fields: Any) -> TLObject:
    return CONSTRUCTORS[name](**fields)
