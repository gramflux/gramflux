"""Reference and handwritten examples must match the implemented additive surface."""

import ast
import inspect
import json
import re
from pathlib import Path

from gramflux import resources
from gramflux.routing import Router
from gramflux.tools.next_reference import DATA, OUTPUT, render

ROOT = Path(__file__).resolve().parents[2]


def test_new_reference_is_reproducible_and_includes_every_mapped_method():
    assert render() == render() == (ROOT / OUTPUT).read_text()
    mapping = json.loads(DATA.read_text())
    for cls, methods in mapping.items():
        assert f"## {cls}\n" in render()
        for name, old in methods.items():
            assert hasattr(getattr(resources, cls), name)
            assert f"../reference/client/{old}.md" in render()


def test_next_api_snippets_parse_and_bind_supported_new_arguments():
    domains = {
        "auth": resources.Auth,
        "account": resources.Account,
        "peers": resources.Peers,
        "files": resources.Files,
        "contacts": resources.Contacts,
        "dialogs": resources.Dialogs,
        "bot": resources.Bot,
        "invites": resources.Invites,
        "membership": resources.Membership,
    }
    checked = 0

    def path(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = path(node.value)
            return parent + "." + node.attr if parent else None
        if isinstance(node, ast.Call) and path(node.func) == "client.chat":
            return "chat"
        return None

    for page in (ROOT / "docs/next-api").glob("*.md"):
        if page.name == "reference.md":
            continue
        for source in re.findall(r"```python\n(.*?)```", page.read_text(), re.S):
            tree = ast.parse(source)
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call):
                    continue
                target = path(call.func)
                cls, name = None, None
                if target and target.startswith("client."):
                    parts = target.split(".")
                    if len(parts) == 3 and parts[1] in domains:
                        cls, name = domains[parts[1]], parts[2]
                    elif target == "client.chat":
                        cls, name = resources.ChatFactory, "__call__"
                elif target and target.startswith("chat."):
                    parts = target.split(".")
                    if len(parts) == 2:
                        cls, name = resources.ChatResource, parts[1]
                    elif len(parts) == 3:
                        cls = {
                            "history": resources.History,
                            "search": resources.Search,
                            "members": resources.Members,
                        }[parts[1]]
                        name = parts[2]
                elif target and target.startswith("router."):
                    cls, name = Router, target.split(".")[1]
                if cls is not None:
                    inspect.signature(getattr(cls, name)).bind(
                        object(),
                        *(object() for _ in call.args),
                        **{kw.arg: object() for kw in call.keywords if kw.arg is not None},
                    )
                    checked += 1
    assert checked >= 35


def test_command_signature_uses_a_valid_enum_expression_not_its_repr():
    from gramflux.tools.docs import signature

    text = signature("command", Router.command)
    assert "direction: Direction = Direction.INCOMING" in text
    ast.parse(text + ":\n    return None\n")
