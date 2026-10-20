import dataclasses
import json

import pytest

from gramflux.errors import SchemaError
from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.parser import parse
from gramflux.tools.schema import DATA, OUTPUT, report


def test_official_generation_is_deterministic_and_complete():
    rendered, coverage = report()
    assert rendered == OUTPUT.read_text()
    assert coverage["generated"] == len(REGISTRY) == 2356
    assert coverage["official_json_ids_matched"] == 2356
    for cls in REGISTRY.values():
        assert dataclasses.is_dataclass(cls)
    assert json.loads((DATA / "metadata.json").read_text())["advertised_layer"] == 225


def test_generic_flags_namespaces_and_multiline():
    definitions = parse("""
        thing#1234 flags:# value:flags.31?Vector<int> = Thing;
        ---functions---
        invoke#abcd {X:Type}
            query:!X = X;
    """)
    assert definitions[0].params[1].type == "flags.31?Vector<int>"
    assert definitions[1].generics == ("X",)
    assert definitions[1].method


@pytest.mark.parametrize(
    "source",
    [
        "x#1 = X; y#1 = Y;",
        "x#1 value:Missing = X;",
        "x#1 value:flags.0?int = X;",
        "x#1 flags:# value:flags.32?int = X;",
        "x#1 x:int x:int = X;",
        "x#1 x:[int] = X;",
        "x#1 = X",
        "x#1 value:int = X; ---invalid---",
    ],
)
def test_reject_invalid_schema_with_location(source):
    with pytest.raises(SchemaError, match="line"):
        parse(source)
