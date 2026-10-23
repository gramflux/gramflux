"""New direct method learning pages must match real callable signatures."""

import ast
import inspect
import json
import re
from pathlib import Path

from gramflux import Client

ROOT = Path(__file__).resolve().parents[2]


def test_highlevel_guides_use_real_methods_and_supported_arguments():
    calls = 0
    instance = Client(session=None, api_id=1, api_hash="0" * 32)
    for path in (ROOT / "docs/client-methods").glob("*.md"):
        for source in re.findall(r"```python\n(.*?)```", path.read_text(), re.S):
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if isinstance(owner, ast.Name) and owner.id == "client":
                    method = getattr(instance, node.func.attr)
                    inspect.signature(method).bind(
                        *(object() for _ in node.args),
                        **{k.arg: object() for k in node.keywords if k.arg is not None},
                    )
                    calls += 1
    assert calls >= 25


def test_added_methods_have_individual_reference_and_coverage_links():
    record = json.loads((ROOT / "research/high-level-inventory.json").read_text())
    coverage = (ROOT / "docs/client-methods/coverage.md").read_text()
    for name in record["added_methods"]:
        assert f"../reference/client/{name}.md" in coverage
        page = (ROOT / "docs/reference/client" / f"{name}.md").read_text()
        assert "Parameters" in page
        assert "Returns" in page
        assert "Raises" in page or "Errors" in page
