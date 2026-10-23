"""Keep handwritten learning examples aligned with the actual public API."""

import ast
import inspect
import re
from pathlib import Path

from gramflux import Client

ROOT = Path(__file__).resolve().parents[2]
PAGES = [
    "getting-started/next-steps.md",
    "tutorials/reply-bot.md",
    "concepts/asyncio.md",
    "concepts/entities.md",
    "concepts/messages.md",
    "concepts/updates.md",
    "guides/lifecycle.md",
    "guides/messaging.md",
    "guides/history.md",
    "guides/faq.md",
    "quick-references/index.md",
    "quick-references/client.md",
    "quick-references/events.md",
]


def test_learning_snippets_parse_and_use_supported_client_arguments():
    snippets = 0
    checked_calls = 0
    for relative in PAGES:
        text = (ROOT / "docs" / relative).read_text()
        for source in re.findall(r"```python\n(.*?)```", text, re.S):
            snippets += 1
            tree = ast.parse(source)
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call):
                    continue
                fn = call.func
                if (
                    isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == "client"
                ):
                    method = getattr(Client, fn.attr)
                    signature = inspect.signature(method)
                    assert not any(isinstance(arg, ast.Starred) for arg in call.args)
                    signature.bind(
                        object(),
                        *(object() for _ in call.args),
                        **{kw.arg: object() for kw in call.keywords if kw.arg is not None},
                    )
                    checked_calls += 1
    assert snippets >= 20
    assert checked_calls >= 20


def test_quick_reference_lists_every_public_client_method_once():
    text = (ROOT / "docs/quick-references/client.md").read_text()
    names = re.findall(r"\| \[([a-z_]+)\]\(\.\./reference/client/", text)
    public = {
        name
        for name, fn in inspect.getmembers(Client, inspect.isfunction)
        if not name.startswith("_")
    }
    assert len(names) == len(set(names))
    assert set(names) == public


def test_learning_links_resolve_to_repository_documents():
    for relative in PAGES:
        path = ROOT / "docs" / relative
        for target in re.findall(r"\]\(([^)]+\.md)(?:#[^)]*)?\)", path.read_text()):
            if "://" not in target:
                assert (path.parent / target).is_file(), (relative, target)
