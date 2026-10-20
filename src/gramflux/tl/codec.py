"""Strict, bounded TL binary encoding and decoding.

No objects are instantiated from arbitrary module paths or pickle data. Constructor
IDs resolve exclusively through the supplied generated registry.
"""

import math
import struct
from dataclasses import dataclass
from typing import Any

from gramflux.errors import SerializationError

from .model import TLObject, python_name

VECTOR = 0x1CB5C415
TRUE = 0x997275B5
FALSE = 0xBC799737


@dataclass(slots=True)
class Reader:
    data: memoryview
    offset: int = 0

    def take(self, size: int) -> bytes:
        if size < 0 or size > len(self.data) - self.offset:
            raise SerializationError("truncated TL input")
        start = self.offset
        self.offset += size
        return bytes(self.data[start : self.offset])

    def uint(self) -> int:
        return int.from_bytes(self.take(4), "little")


class Codec:
    """Thread-safe codec; each operation has its own reader and buffers.

    Bounds apply to both encoding and decoding. Unknown constructor IDs,
    invalid flag groups, excess input, and noncanonical strings are rejected.
    """

    def __init__(
        self,
        registry: dict[int, type[TLObject]] | None = None,
        *,
        max_bytes: int = 16 * 1024 * 1024,
        max_vector: int = 100_000,
        max_depth: int = 64,
    ) -> None:
        if min(max_bytes, max_vector, max_depth) <= 0:
            raise ValueError("codec limits must be positive")
        if registry is None:
            from .generated.objects import REGISTRY

            registry = REGISTRY
        self.registry = registry
        self.max_bytes = max_bytes
        self.max_vector = max_vector
        self.max_depth = max_depth

    def encode(self, value: Any, type: str = "Object") -> bytes:
        output = bytearray()
        try:
            self._write(output, value, type, 0)
        except (OverflowError, struct.error, UnicodeError, TypeError, AttributeError) as e:
            raise SerializationError("value does not match TL field type") from e
        return bytes(output)

    def decode(self, data: bytes, type: str = "Object") -> Any:
        if len(data) > self.max_bytes:
            raise SerializationError("TL input exceeds limit")
        reader = Reader(memoryview(data))
        try:
            result = self._read(reader, type, 0)
        except (UnicodeError, struct.error) as e:
            raise SerializationError("invalid TL primitive") from e
        if reader.offset != len(data):
            raise SerializationError("trailing TL input")
        return result

    def _check(self, depth: int, size: int) -> None:
        if depth > self.max_depth or size > self.max_bytes:
            raise SerializationError("TL resource limit exceeded")

    def _write(self, out: bytearray, value: Any, t: str, depth: int) -> None:
        self._check(depth, len(out))
        t = t.removeprefix("!")
        if t in {"int", "long", "#"}:
            if not isinstance(value, int) or isinstance(value, bool):
                raise SerializationError("expected integer")
            out.extend(value.to_bytes(8 if t == "long" else 4, "little", signed=t != "#"))
        elif t == "double":
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise SerializationError("expected finite double")
            out.extend(struct.pack("<d", value))
        elif t in {"int128", "int256"}:
            size = 16 if t == "int128" else 32
            if not isinstance(value, bytes) or len(value) != size:
                raise SerializationError(f"expected {size} bytes")
            out.extend(value)
        elif t in {"string", "bytes"}:
            raw = value.encode("utf-8") if t == "string" and isinstance(value, str) else value
            if not isinstance(raw, bytes) or (t == "string" and not isinstance(value, str)):
                raise SerializationError("expected string or bytes")
            n = len(raw)
            if n >= 1 << 24 or n > self.max_bytes:
                raise SerializationError("TL bytes exceed limit")
            prefix = bytes([n]) if n < 254 else b"\xfe" + n.to_bytes(3, "little")
            out.extend(prefix)
            out.extend(raw)
            out.extend(b"\0" * (-(len(prefix) + n) % 4))
        elif t == "Bool":
            if not isinstance(value, bool):
                raise SerializationError("expected bool")
            out.extend(struct.pack("<I", TRUE if value else FALSE))
        elif t.startswith(("Vector<", "vector<")):
            if not isinstance(value, (list, tuple)) or len(value) > self.max_vector:
                raise SerializationError("invalid vector or length exceeds limit")
            if t.startswith("Vector"):
                out.extend(struct.pack("<I", VECTOR))
            out.extend(struct.pack("<i", len(value)))
            for item in value:
                self._write(out, item, t[t.index("<") + 1 : -1], depth + 1)
        else:
            if not isinstance(value, TLObject) or self.registry.get(
                value.definition.id
            ) is not type(value):
                raise SerializationError("unregistered TL object")
            d = value.definition
            if t not in {"Object", "X"} and d.result != t and not t.startswith("!"):
                raise SerializationError(f"constructor does not produce {t}")
            if d.name == "vector":
                raise SerializationError("vector requires an element type")
            out.extend(struct.pack("<I", d.id))
            flags: dict[str, int] = {}
            groups: dict[tuple[str, int], list[bool]] = {}
            for p in d.params:
                if p.type == "#":
                    flags[p.name] = 0
                elif "?" in p.type:
                    cond, field_type = p.type.split("?", 1)
                    flag, bit = cond.split(".")
                    v = getattr(value, python_name(p.name))
                    if field_type == "true" and not isinstance(v, bool):
                        raise SerializationError("optional true fields must be bool")
                    present = v is True if field_type == "true" else v is not None
                    groups.setdefault((flag, int(bit)), []).append(present)
            for (flag, bit_number), group in groups.items():
                if any(group) != all(group):
                    raise SerializationError("fields sharing a flag must be present together")
                if all(group):
                    flags[flag] |= 1 << bit_number
            for p in d.params:
                field_type = p.type
                if field_type == "#":
                    self._write(out, flags[p.name], "#", depth + 1)
                    continue
                if "?" in field_type:
                    cond, field_type = field_type.split("?", 1)
                    flag, bit = cond.split(".")
                    if not flags[flag] & (1 << int(bit)) or field_type == "true":
                        continue
                self._write(out, getattr(value, python_name(p.name)), field_type, depth + 1)
        self._check(depth, len(out))

    def _read(self, r: Reader, t: str, depth: int) -> Any:
        self._check(depth, r.offset)
        if t in {"int", "long", "#"}:
            return int.from_bytes(r.take(8 if t == "long" else 4), "little", signed=t != "#")
        if t == "double":
            value = struct.unpack("<d", r.take(8))[0]
            if not math.isfinite(value):
                raise SerializationError("nonfinite double")
            return value
        if t in {"int128", "int256"}:
            return r.take(16 if t == "int128" else 32)
        if t in {"bytes", "string"}:
            n = r.take(1)[0]
            prefix = 1
            if n == 255:
                raise SerializationError("invalid TL bytes prefix")
            if n == 254:
                n = int.from_bytes(r.take(3), "little")
                prefix = 4
                if n < 254:
                    raise SerializationError("noncanonical TL bytes length")
            if n > self.max_bytes:
                raise SerializationError("TL bytes exceed limit")
            raw = r.take(n)
            if any(r.take(-(n + prefix) % 4)):
                raise SerializationError("nonzero TL padding")
            return raw.decode("utf-8") if t == "string" else raw
        if t.startswith(("Vector<", "vector<")):
            if t.startswith("Vector") and r.uint() != VECTOR:
                raise SerializationError("invalid vector constructor")
            n = int.from_bytes(r.take(4), "little", signed=True)
            if not 0 <= n <= self.max_vector:
                raise SerializationError("vector count exceeds limit")
            return [self._read(r, t[t.index("<") + 1 : -1], depth + 1) for _ in range(n)]
        ident = r.uint()
        if t == "Bool":
            if ident not in {TRUE, FALSE}:
                raise SerializationError("invalid bool constructor")
            return ident == TRUE
        cls = self.registry.get(ident)
        if cls is None:
            raise SerializationError(f"unknown TL constructor {ident:08x}")
        d = cls.definition
        if t != "Object" and d.result != t:
            raise SerializationError(f"constructor does not produce {t}")
        if d.method or d.name == "vector":
            raise SerializationError("cannot decode method or untyped vector as object")
        fields: dict[str, Any] = {}
        flags: dict[str, int] = {}
        for p in d.params:
            field_type = p.type
            if field_type == "#":
                flags[p.name] = r.uint()
                known = 0
                for q in d.params:
                    if q.type.startswith(p.name + "."):
                        known |= 1 << int(q.type.split("?", 1)[0].split(".")[1])
                if flags[p.name] & ~known:
                    raise SerializationError("unknown flags require a newer schema")
                continue
            if "?" in field_type:
                cond, field_type = field_type.split("?", 1)
                flag, bit = cond.split(".")
                present = bool(flags[flag] & (1 << int(bit)))
                if field_type == "true":
                    fields[python_name(p.name)] = present
                    continue
                if not present:
                    fields[python_name(p.name)] = None
                    continue
            fields[python_name(p.name)] = self._read(r, field_type, depth + 1)
        return cls(**fields)
