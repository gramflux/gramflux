"""Explicit refresh and offline verification of short official reference excerpts.

Only factual method/error metadata and <=25 prose words per source page are retained.
Normal documentation generation never accesses the network.
"""

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.model import Definition

OUTPUT = Path(__file__).with_name("data") / "official_reference.json"


def plain(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return " ".join(
        html.unescape(text).replace("\\", "").replace("**", "").replace("`", "").split()
    )


def extract(definition: Definition, text: str) -> dict[str, Any]:
    rows: dict[str, str] = {}
    errors: list[dict[str, object]] = []
    eligibility: list[str] = []
    in_parameters = False
    for line in text.splitlines():
        if line.startswith("### "):
            in_parameters = line.strip() == "### Parameters"
            if any(term in line.lower() for term in ("users can", "bots can", "users and bots")):
                eligibility.append(plain(line.removeprefix("### ")))
        if in_parameters and line.startswith("| **"):
            cells = line.split("|")
            if len(cells) > 3:
                rows[plain(cells[1])] = plain(cells[3])
        match = re.match(r"\| (\d{3}) \| ([A-Za-z0-9_%\\]+) \|", line)
        if match:
            errors.append({"code": int(match[1]), "name": match[2].replace("\\", "")})
    opening = text.split("```", 1)[0]
    paragraphs = [plain(p) for p in opening.split("\n\n") if p.strip() and not p.startswith("#")]
    words = " ".join(paragraphs).split()
    summary = " ".join(words[:12]) + (" …" if len(words) > 12 else "")
    budget = 25 - min(len(words), 12)
    names = [p.name for p in definition.params if p.type != "#" and rows.get(p.name)]
    notes: dict[str, str] = {}
    for index, name in enumerate(names):
        share = max(1, budget // (len(names) - index))
        field_words = rows[name].split()
        take = min(len(field_words), share, budget)
        if take:
            notes[name] = " ".join(field_words[:take]) + (" …" if take < len(field_words) else "")
            budget -= take
    match = re.search(re.escape(definition.name) + r"#([a-fA-F0-9]+)\s", text)
    return {
        "status": "ok",
        "url": "https://core.telegram.org/method/" + definition.name + ".md",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "schema_id_matches": bool(match and int(match[1], 16) == definition.id),
        "summary_quote": summary,
        "parameter_notes": notes,
        "documented_parameters": sorted(rows),
        "errors": errors,
        "eligibility": eligibility,
    }


def fetch(definition: Definition) -> dict[str, Any]:
    url = "https://core.telegram.org/method/" + definition.name + ".md"
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "GramFlux-docs-reference"})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise ValueError("official reference page exceeds resource limit")
            return extract(definition, data.decode("utf-8"))
        except (OSError, UnicodeError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable fetch retry")


def verify(payload: dict[str, Any]) -> dict[str, int]:
    methods = [c.definition for c in REGISTRY.values() if c.definition.method]
    rows = payload["methods"]
    if set(rows) != {d.name for d in methods}:
        raise ValueError("official reference coverage differs from the pinned method registry")
    quoted = 0
    for definition in methods:
        row = rows[definition.name]
        if row.get("status") != "ok" or row.get("schema_id_matches") is not True:
            raise ValueError(f"missing or mismatched official reference: {definition.name}")
        prose = [row.get("summary_quote", ""), *row.get("parameter_notes", {}).values()]
        count = sum(len(value.replace(" …", "").split()) for value in prose)
        if count > 25:
            raise ValueError(f"source quotation budget exceeded: {definition.name}")
        quoted += count
        names = {p.name for p in definition.params if p.type != "#"}
        if not names <= set(row["documented_parameters"]):
            raise ValueError(f"official parameter table is incomplete: {definition.name}")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("invalid source digest")
    return {
        "methods": len(methods),
        "parameters": sum(sum(p.type != "#" for p in d.params) for d in methods),
        "retained_prose_words": quoted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("update", "verify"))
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=4)
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify(json.loads(OUTPUT.read_text())), indent=2))
        return
    results = {}
    definitions = [c.definition for c in REGISTRY.values() if c.definition.method]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, d): d.name for d in definitions}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    payload = {
        "provenance": (
            "Official Telegram method pages; factual metadata and <=25 quoted prose words per page."
        ),
        "methods": dict(sorted(results.items())),
    }
    verify(payload)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(OUTPUT)
    print(json.dumps(verify(payload), indent=2))


if __name__ == "__main__":
    main()
