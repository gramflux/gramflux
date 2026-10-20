"""Auditable schema CLI: update, generate, verify, diff.

Update downloads into a NEW directory; it never changes shipped schemas implicitly.
Generate and verify work offline against the exact packaged source snapshot.
"""

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from gramflux.errors import SchemaError
from gramflux.tl.generator import generate
from gramflux.tl.parser import parse

DATA = Path(__file__).resolve().parents[1] / "tl" / "data"
OUTPUT = DATA.parent / "generated" / "objects.py"


class Preformatted(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inside = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre":
            self.inside = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.parts.append(data)


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise SchemaError("schema download exceeds size limit")
    return bytes(data)


def update(destination: Path) -> None:
    if destination.exists():
        raise SchemaError("update destination must not already exist")
    payloads: dict[str, bytes] = {}
    sources = {
        "api": "https://core.telegram.org/schema",
        "mtproto": "https://core.telegram.org/schema/mtproto",
    }
    advertised: int | None = None
    for name, url in sources.items():
        html = download(url).decode("utf-8")
        parser = Preformatted()
        parser.feed(html)
        text = "".join(parser.parts)
        parse(text)
        payloads[name + ".tl"] = text.encode()
        if name == "api":
            match = re.search(r"Layer\s+(\d+)", html)
            advertised = int(match[1]) if match else None
    payloads["api.json"] = download("https://core.telegram.org/schema/json")
    json.loads(payloads["api.json"])
    metadata = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "advertised_layer": advertised,
        "sources": sources,
        "sha256": {n: hashlib.sha256(b).hexdigest() for n, b in payloads.items()},
        "note": (
            "HTML preformatted blocks extracted without changing declarations; "
            "API JSON retained verbatim"
        ),
    }
    destination.mkdir(parents=True)
    for name, data in payloads.items():
        (destination / name).write_bytes(data)
    (destination / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def report(data: Path = DATA) -> tuple[str, dict[str, Any]]:
    metadata = json.loads((data / "metadata.json").read_text())
    for name, expected in metadata["sha256"].items():
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != expected:
            raise SchemaError(f"source hash mismatch: {name}")
    source = (data / "api.tl").read_text()
    definitions = parse(source)
    protocol = parse((data / "mtproto.tl").read_text())
    machine = json.loads((data / "api.json").read_text())
    expected = {int(d["id"]) & 0xFFFFFFFF for d in machine["constructors"] + machine["methods"]}
    actual = {d.id for d in definitions}
    if expected != actual:
        raise SchemaError(
            f"TL/JSON IDs differ: missing={expected - actual}, extra={actual - expected}"
        )
    for raw in machine["constructors"] + machine["methods"]:
        definition = next(d for d in definitions if d.id == int(raw["id"]) & 0xFFFFFFFF)
        if (
            definition.name != raw.get("predicate", raw.get("method"))
            or [(p.name, p.type) for p in definition.params]
            != [(p["name"], p["type"]) for p in raw["params"]]
            or definition.result != raw["type"]
        ):
            raise SchemaError(f"TL/JSON definition mismatch: {definition.name}")
    rendered = generate(definitions, metadata["sha256"]["api.tl"])
    return rendered, {
        "advertised_layer": metadata["advertised_layer"],
        "sha256": metadata["sha256"]["api.tl"],
        "constructors": sum(not d.method for d in definitions),
        "methods": sum(d.method for d in definitions),
        "generated": len(definitions),
        "official_json_ids_matched": len(expected & actual),
        "protocol_declarations_parsed": len(protocol),
        "runtime": "Telethon bindings (separate layer); independent declarations are offline only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    sub.add_parser("verify")
    p = sub.add_parser("update")
    p.add_argument("destination", type=Path)
    p = sub.add_parser("diff")
    p.add_argument("old", type=Path)
    p.add_argument("new", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "update":
            update(args.destination)
        elif args.command == "diff":
            old = {d.name: d for d in parse(args.old.read_text())}
            new = {d.name: d for d in parse(args.new.read_text())}
            print(
                json.dumps(
                    {
                        "added": sorted(new.keys() - old.keys()),
                        "removed": sorted(old.keys() - new.keys()),
                        "changed": sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
                    },
                    indent=2,
                )
            )
        else:
            rendered, coverage = report()
            if args.command == "generate":
                OUTPUT.write_text(rendered)
            elif not OUTPUT.exists() or OUTPUT.read_text() != rendered:
                raise SchemaError("generated output differs; run generate and review the diff")
            print(json.dumps(coverage, indent=2))
    except (SchemaError, ValueError, OSError) as e:
        parser.exit(1, f"schema: {e}\n")


if __name__ == "__main__":
    main()
