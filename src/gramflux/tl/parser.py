"""Parser for the official API's TL grammar; unknown syntax fails closed."""

import re

from gramflux.errors import SchemaError

from .model import Definition, Parameter

# Prelude declarations have special binary semantics, rather than object fields.
PRELUDE = {
    "int ? = Int",
    "long ? = Long",
    "double ? = Double",
    "string ? = String",
    "vector {t:Type} # [ t ] = Vector t",
    "int128 4*[ int ] = Int128",
    "int256 8*[ int ] = Int256",
    "message msg_id:long seqno:int bytes:int body:Object = Message",
}
TYPE = re.compile(r"(?:[A-Za-z_][\w.]*\.\d+\?)?(?:!?[A-Za-z_][\w.]*|#|(?:[Vv]ector)<.+>)$")


def parse(source: str) -> tuple[Definition, ...]:
    """Parse declarations with explicit IDs, flags, vectors and generic queries.

    IDs are taken from the source, never guessed or rewritten. The polymorphic
    vector constructor is represented explicitly and handled specially by the codec.
    """
    clean = re.sub(r"/\*.*?\*/", lambda m: "\n" * m[0].count("\n"), source, flags=re.S)
    clean = re.sub(r"//[^\n]*", "", clean)
    result: list[Definition] = []
    methods = False
    pending = ""
    start = 0
    for line_no, line in enumerate(clean.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line in {"---functions---", "---types---"}:
            if pending:
                raise SchemaError(f"line {start}: unterminated declaration")
            methods = line == "---functions---"
            continue
        if not pending:
            start = line_no
        pending += " " + line
        while ";" in pending:
            declaration, pending = pending.split(";", 1)
            declaration = declaration.strip()
            pending = pending.strip()
            if declaration in PRELUDE:
                continue
            match = re.fullmatch(r"([\w.]+)#([0-9a-fA-F]{1,8})\s*(.*?)\s*=\s*(.+)", declaration)
            if not match:
                raise SchemaError(f"line {start}: unsupported declaration: {declaration[:100]}")
            name, ident, body, returns = match.groups()
            if name == "vector" and body == "{t:Type} # [ t ]" and returns == "Vector t":
                result.append(Definition(name, int(ident, 16), (), returns, methods, ("t",), start))
                continue
            generics = tuple(re.findall(r"\{(\w+):Type\}", body))
            body = re.sub(r"\{\w+:Type\}", "", body)
            params: list[Parameter] = []
            for token in body.split():
                if ":" not in token:
                    raise SchemaError(f"line {start}: unsupported parameter: {token}")
                key, value = token.split(":", 1)
                if not re.fullmatch(r"[a-zA-Z_]\w*", key) or not TYPE.fullmatch(value):
                    raise SchemaError(f"line {start}: invalid parameter {token}")
                params.append(Parameter(key, value))
            result.append(
                Definition(name, int(ident, 16), tuple(params), returns, methods, generics, start)
            )
    if pending.strip():
        raise SchemaError(f"line {start}: missing semicolon")
    validate(tuple(result))
    return tuple(result)


def base_type(t: str) -> str:
    return t.split("?", 1)[-1].removeprefix("!")


def validate(definitions: tuple[Definition, ...]) -> None:
    ids: set[int] = set()
    names: set[str] = set()
    known = {d.result for d in definitions if not d.method}
    known |= {d.name for d in definitions if not d.method}
    known.add("Message")
    known |= {
        "int",
        "long",
        "double",
        "string",
        "bytes",
        "int128",
        "int256",
        "#",
        "true",
        "Object",
        "Type",
    }
    for d in definitions:

        def fail(message: str, d: Definition = d) -> None:
            raise SchemaError(f"line {d.line} ({d.name}): {message}")

        if d.id in ids or d.name in names:
            fail("duplicate ID or name")
        ids.add(d.id)
        names.add(d.name)
        seen: dict[str, str] = {}
        for p in d.params:
            if p.name in seen:
                fail(f"duplicate field {p.name}")
            if "?" in p.type:
                flag, _, bit = p.type.split("?", 1)[0].rpartition(".")
                if seen.get(flag) != "#" or not bit.isdigit() or not 0 <= int(bit) < 32:
                    fail(f"invalid flag reference {p.type}")
            seen[p.name] = p.type
        for t in [*(p.type for p in d.params), d.result]:
            t = base_type(t)
            while t.startswith(("Vector<", "vector<")) and t.endswith(">"):
                t = t[t.index("<") + 1 : -1].removeprefix("%")
            if t not in known and t not in d.generics and t != "Vector t":
                fail(f"unresolved type {t}")
