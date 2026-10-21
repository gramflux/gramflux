"""Reference generation must cover the real public surface without unstable reprs."""

import re

from gramflux.tl.generated.objects import REGISTRY
from gramflux.tools.docs import render


def test_reference_contains_each_official_method_once_with_exact_wire_id():
    rendered = render()
    raw = "\n".join(text for name, text in rendered.items() if name.startswith("raw/"))
    for cls in REGISTRY.values():
        definition = cls.definition
        if not definition.method:
            continue
        assert raw.count(f"**Official method:** `{definition.name}`") == 1
        assert f"`0x{definition.id:08x}`" in raw
    assert "| flags |" not in raw
    assert "| `flags` | `#` |" not in raw
    assert "| `offset_date` | `int` | Required |" in rendered["raw/messages.md"]
    assert "| `no_webpage` | `flags.1?true` | False |" in rendered["raw/messages.md"]


def test_reference_preserves_resumable_login_and_safe_stable_signatures():
    first = render()
    assert first == render()
    client = first["client.md"]
    assert "### sign_in" in client
    assert "code: str | None = None" in client
    assert "`login_stage`" in client
    assert "_backend" not in client
    assert r"| `client` | `Client \| None` |" in first["events.md"]
    assert not re.search(r" at 0x[0-9a-f]+", "".join(first.values()))
    assert (
        "def open(name: str | pathlib.Path, *, require_authorized: bool = True)"
        in first["configuration.md"]
    )
    assert "### Session.create" in first["configuration.md"]
