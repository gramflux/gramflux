"""Coverage/contract checks for separately navigable, source-backed method docs."""

import ast
import inspect
import json

import pytest

from gramflux import Client
from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.methods import method_name
from gramflux.tools.docs import render
from gramflux.tools.docs_reference import load_content
from gramflux.tools.docs_sources import OUTPUT, extract, verify


@pytest.fixture(scope="module")
def pages():
    return render()


def test_every_public_method_has_complete_parameter_explanations_and_an_example(pages):
    content = load_content()
    public = {
        name: fn
        for name, fn in inspect.getmembers(Client, inspect.isfunction)
        if not name.startswith("_")
    }
    assert set(content["methods"]) == set(public) | {"__init__"}
    for name, function in {"__init__": Client, **public}.items():
        text = pages["client/" + ("constructor" if name == "__init__" else name) + ".md"]
        assert "## Returns" in text and "## Example" in text
        assert "## Errors and recovery" in text and "## Behavior and constraints" in text
        for parameter in inspect.signature(function).parameters.values():
            if parameter.name in {"self", "cls"} or parameter.name.startswith("_"):
                continue
            assert f"### {parameter.name}\n" in text
            meaning = content["overrides"].get(
                name + "." + parameter.name, content["parameters"].get(parameter.name)
            )
            assert meaning and len(meaning.split()) >= 10
            assert meaning in text
        ast.parse(content["methods"][name]["example"])


def test_every_raw_method_has_its_own_page_and_all_wire_arguments(pages):
    count = 0
    parameters = 0
    for cls in REGISTRY.values():
        d = cls.definition
        if not d.method:
            continue
        namespace = d.name.rpartition(".")[0] or "root"
        name = method_name(d.name.rsplit(".", 1)[-1])
        text = pages[f"raw/{namespace}/{name}.md"]
        count += 1
        assert f"`0x{d.id:08x}`" in text
        for parameter in d.params:
            if parameter.type != "#":
                parameters += 1
                assert f"### {parameter.name}\n" in text or f"### {parameter.name}_\n" in text
        assert "## Result and interpretation" in text
        assert "## Server errors and recovery" in text
        assert "## Flags and related fields" in text
        assert "## Request construction example" in text
    assert count == 783 and parameters == 1992


def test_semantically_different_options_are_explained_separately(pages):
    send = pages["client/send_message.md"]
    assert "## Parameters" in send
    assert "### reply_markup" in send and "### entities" in send
    assert "UTF-16" in send and "parse_mode" in send
    assert "None" in send and "False" in send
    assert "1–16" in pages["client/upload_file.md"]
    assert "1–200" in pages["client/iter_members.md"]
    assert "sharing a bit" not in pages["client/send_message.md"]
    assert "int | None" in pages["client/send_message.md"].replace(r"\|", "|")
    assert "| `flags` | `int` | `Required` |" in pages["raw/auth/import_bot_authorization.md"]
    assert "types.InputPeerUser" in pages["raw/messages/get_history.md"]
    assert "### access_hash" not in pages["client/get_history.md"]


def test_official_reference_coverage_and_source_quote_budget():
    snapshot = json.loads(OUTPUT.read_text())
    stats = verify(snapshot)
    assert stats["methods"] == 783 and stats["parameters"] == 1992
    for record in snapshot["methods"].values():
        prose = [record["summary_quote"], *record["parameter_notes"].values()]
        assert sum(len(text.replace(" …", "").split()) for text in prose) <= 25
    snapshot["methods"]["messages.getHistory"]["schema_id_matches"] = False
    with pytest.raises(ValueError, match="mismatched"):
        verify(snapshot)


def test_source_extractor_preserves_an_explicit_integer_named_flags():
    d = next(
        c.definition
        for c in REGISTRY.values()
        if c.definition.name == "auth.importBotAuthorization"
    )
    text = f"""# {d.name}

Authorize a bot.

```tl
{d.name}#{d.id:x} flags:int api_id:int api_hash:string bot_auth_token:string = auth.Authorization;
```
### Parameters
| Name | Type | Description |
| **flags** | int | Reserved for future use. |
| **api_id** | int | Application identifier. |
| **api_hash** | string | Application secret. |
| **bot_auth_token** | string | Bot token. |
### Only bots can use this method
### Possible errors
| 403 | SAMPLE_ERROR_%d | Synthetic error for this parser test. |
"""
    result = extract(d, text)
    assert result["schema_id_matches"]
    assert "flags" in result["parameter_notes"]
    assert result["errors"] == [{"code": 403, "name": "SAMPLE_ERROR_%d"}]
