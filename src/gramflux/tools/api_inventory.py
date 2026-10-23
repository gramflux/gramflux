"""Inspect the actual public Client surface, separately from TL method declarations."""

import argparse
import inspect
import json
from pathlib import Path
from typing import Any, get_args

from gramflux import Client, __version__, events
from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.methods import method_name


def inventory() -> dict[str, Any]:
    methods = {}
    for name, value in inspect.getmembers(Client, inspect.isfunction):
        if name.startswith("_"):
            continue
        kind = (
            "async_generator"
            if inspect.isasyncgenfunction(value)
            else "async"
            if inspect.iscoroutinefunction(value)
            else "sync"
        )
        methods[name] = kind
    client = Client(session=None, api_id=1, api_hash="0" * 32)
    facade = client.api
    paths = []
    for cls in REGISTRY.values():
        if not cls.definition.method:
            continue
        namespace, _, tail = cls.definition.name.rpartition(".")
        target = getattr(facade, namespace) if namespace else facade
        name = method_name(tail)
        if not inspect.iscoroutinefunction(getattr(target, name)):
            raise ValueError(f"missing async method: {cls.definition.name}")
        paths.append("client.api." + (namespace + "." if namespace else "") + name)
    subscriptions = [name for name in methods if name == "on" or name.startswith("on_")]
    return {
        "version": __version__,
        "public_client_methods": methods,
        "public_client_method_count": len(methods),
        "event_subscription_methods": subscriptions,
        "event_classes": sorted(event.__name__ for event in get_args(events.Event)),
        "raw_tl_methods": sum(cls.definition.method for cls in REGISTRY.values()),
        "async_api_method_count": len(paths),
        "async_api_methods": sorted(paths),
        "raw_update_constructors": sorted(
            cls.definition.name for cls in REGISTRY.values() if cls.definition.result == "Update"
        ),
        "next_generation_views": [
            "auth",
            "account",
            "peers",
            "chat",
            "files",
            "contacts",
            "dialogs",
            "bot",
            "invites",
            "membership",
            "events",
            "raw",
        ],
        "next_generation_scope": (
            "Additive direct Client methods, local resources and routing; legacy contracts retained"
        ),
        "scope": "Surface inventory; raw declarations separate; live interoperability unverified",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("docs/api-surface.json"))
    args = parser.parse_args()
    content = json.dumps(inventory(), indent=2, ensure_ascii=False) + "\n"
    if args.write:
        args.output.write_text(content)
    elif args.check:
        if not args.output.is_file() or args.output.read_text() != content:
            raise SystemExit(
                "API inventory differs; run python -m gramflux.tools.api_inventory --write"
            )
        print("Public API inventory matches the implemented Client")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
