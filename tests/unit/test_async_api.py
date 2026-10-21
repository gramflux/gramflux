"""All official methods reach the real codec through the async facade.

Responses and arguments here are synthetic. This is not Telegram interoperability.
"""

import asyncio
import inspect

import pytest

from gramflux import Client, Session, filters
from gramflux.errors import ConfigurationError
from gramflux.events import RawUpdateEvent
from gramflux.raw import functions, types
from gramflux.tl import Codec
from gramflux.tl.generated.methods import API
from gramflux.tl.generated.objects import REGISTRY
from gramflux.tl.methods import generate_methods, method_name
from gramflux.tl.model import Definition, python_name
from tests.native_fixtures import fixture_field

METHODS = [cls for cls in REGISTRY.values() if cls.definition.method]
UPDATES = [cls for cls in REGISTRY.values() if cls.definition.result == "Update"]


@pytest.mark.parametrize("cls", METHODS, ids=lambda cls: cls.definition.name)
async def test_every_official_async_method_serializes_and_forwards(cls):
    definition = cls.definition
    captured = []
    expected = object()

    class Invoker:
        async def invoke(self, request):
            captured.append(request)
            assert type(request) is cls
            wire = Codec().encode(request)
            assert int.from_bytes(wire[:4], "little") == definition.id
            assert wire == Codec().encode(cls(**kwargs))
            return expected

    facade = API(Invoker())
    namespace, _, name = definition.name.rpartition(".")
    target = getattr(facade, namespace) if namespace else facade
    method = getattr(target, method_name(name))
    kwargs = {
        python_name(p.name): (
            functions.help.GetNearestDcRequest()
            if p.type.startswith("!")
            else fixture_field(p.type)
        )
        for p in definition.params
        if p.type != "#" and "?" not in p.type
    }
    assert inspect.iscoroutinefunction(method)
    assert await method(**kwargs) is expected
    assert len(captured) == 1
    assert inspect.signature(method).return_annotation
    for p in definition.params:
        if p.type == "#":
            assert p.name not in inspect.signature(method).parameters
        elif "?" in p.type:
            assert getattr(captured[0], python_name(p.name)) is (
                False if p.type.endswith("?true") else None
            )


async def test_facade_propagates_cancellation_and_exceptions_without_retries():
    started = asyncio.Event()
    cancelled = asyncio.Event()
    calls = 0

    class Invoker:
        async def invoke(self, request):
            nonlocal calls
            calls += 1
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    task = asyncio.create_task(API(Invoker()).help.get_nearest_dc())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set() and calls == 1

    failure = RuntimeError("synthetic network error")

    class Failing:
        async def invoke(self, request):
            raise failure

    with pytest.raises(RuntimeError) as error:
        await API(Failing()).help.get_nearest_dc()
    assert error.value is failure


def test_client_facade_is_cached_and_not_shared():
    first = Client(session=Session.temporary(), api_id=1, api_hash="a" * 32)
    second = Client(session=Session.temporary(), api_id=1, api_hash="a" * 32)
    assert first.api is first.api
    assert first.api is not second.api
    assert first.api.messages._client is first


@pytest.mark.parametrize("cls", UPDATES, ids=lambda cls: cls.definition.name)
def test_update_selector_accepts_every_official_update_constructor(cls):
    update = cls(
        **{
            python_name(p.name): fixture_field(p.type)
            for p in cls.definition.params
            if p.type != "#" and "?" not in p.type
        }
    )
    selector = filters.update_type(cls)
    assert selector(RawUpdateEvent(update))
    assert not selector(object())


@pytest.mark.parametrize("value", [None, str, types.User, functions.help.GetNearestDcRequest])
def test_update_selector_rejects_non_updates(value):
    with pytest.raises(ConfigurationError):
        filters.update_type(value)


def test_generator_detects_collisions():
    declarations = (
        Definition("help.getURL", 1, (), "Bool", True),
        Definition("help.getUrl", 2, (), "Bool", True),
    )
    with pytest.raises(ValueError, match="collision"):
        generate_methods(declarations, "test", 225)
