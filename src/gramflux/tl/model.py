"""Schema descriptors and the generated-object base class."""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    id: int
    params: tuple[Parameter, ...]
    result: str
    method: bool = False
    generics: tuple[str, ...] = ()
    line: int = field(default=0, compare=False)


@dataclass(slots=True, repr=False)
class TLObject:
    """Typed generated declaration. Repr deliberately excludes field values."""

    definition: ClassVar[Definition]

    def __repr__(self) -> str:
        return f"<{self.definition.name}>"


def python_name(name: str) -> str:
    import keyword

    return name + "_" if keyword.iskeyword(name) else name


def class_name(d: Definition) -> str:
    return python_name(
        "".join(s[:1].upper() + s[1:] for s in d.name.split(".")) + ("Request" if d.method else "")
    )
