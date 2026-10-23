"""Cross-surface contracts: forwarding, laziness and unchanged legacy signatures."""

import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from gramflux import Client
from gramflux import resources as views
from gramflux.tools.docs import signature

ROOT = Path(__file__).resolve().parents[2]
MAPPING = json.loads((ROOT / "research/next-api-mapping.json").read_text())


def make_client():
    return Client(api_id=1, api_hash="0" * 32)


def test_legacy_contract_and_imports_remain_intact():
    baseline = json.loads((ROOT / "research/legacy-api-contract.json").read_text())
    for name, expected in baseline["methods"].items():
        assert signature(name, getattr(Client, name)) == expected
    assert signature("Client", Client) == baseline["constructor"]
    for name in baseline["properties"]:
        assert hasattr(Client, name)
    from gramflux import auth, events, files, filters, raw, sessions, storage

    assert all((auth, events, files, filters, raw, sessions, storage))


def test_views_are_local_and_cached_without_touching_the_backend():
    client = make_client()
    client._backend = Mock()
    for name in [
        "auth",
        "account",
        "peers",
        "files",
        "contacts",
        "dialogs",
        "bot",
        "invites",
        "membership",
        "events",
        "raw",
        "chat",
    ]:
        assert getattr(client, name) is getattr(client, name)
    chat = client.chat("@unresolved")
    assert chat._peer == "@unresolved"
    assert chat.history._peer == chat.search._peer == chat.members._peer == "@unresolved"
    client._backend.assert_not_called()
    assert not client._backend.mock_calls


CASES = [(cls, new, old) for cls, rows in MAPPING.items() for new, old in rows.items()]


@pytest.mark.parametrize("cls,new,old", CASES)
async def test_every_resource_forwards_all_options_and_result_identity(cls, new, old):
    client = make_client()
    bound = cls in {"History", "Search", "Members", "ChatResource"}
    peer = object()
    view = getattr(views, cls)(client, peer) if bound else getattr(views, cls)(client)
    method = getattr(view, new)
    args, kwargs, values = [], {}, {}
    for p in inspect.signature(method).parameters.values():
        value = object()
        values[p.name] = value
        if p.kind == p.KEYWORD_ONLY:
            kwargs[p.name] = value
        else:
            args.append(value)
    result = object()
    replacement = (
        AsyncMock(return_value=result)
        if inspect.iscoroutinefunction(method)
        else Mock(return_value=result)
    )
    setattr(client, old, replacement)
    actual = method(*args, **kwargs)
    if inspect.iscoroutinefunction(method):
        actual = await actual
    assert actual is result
    original = inspect.signature(getattr(Client, old))
    positional = [
        peer if p.name == "peer" and bound else values[p.name]
        for p in original.parameters.values()
        if p.name != "self" and p.kind == p.POSITIONAL_OR_KEYWORD
    ]
    expected_kwargs = {
        p.name: values[p.name] for p in original.parameters.values() if p.kind == p.KEYWORD_ONLY
    }
    replacement.assert_called_once_with(*positional, **expected_kwargs)


@pytest.mark.parametrize("cls,new,old", CASES)
async def test_every_resource_preserves_raised_exception_identity(cls, new, old):
    client = make_client()
    bound = cls in {"History", "Search", "Members", "ChatResource"}
    view = getattr(views, cls)(client, "me") if bound else getattr(views, cls)(client)
    method = getattr(view, new)
    args, kwargs = [], {}
    for p in inspect.signature(method).parameters.values():
        if p.default is not p.empty:
            continue
        if p.kind == p.KEYWORD_ONLY:
            kwargs[p.name] = object()
        else:
            args.append(object())
    error = RuntimeError("controlled transport failure")
    replacement = (
        AsyncMock(side_effect=error)
        if inspect.iscoroutinefunction(method)
        else Mock(side_effect=error)
    )
    setattr(client, old, replacement)
    with pytest.raises(RuntimeError) as caught:
        value = method(*args, **kwargs)
        if inspect.iscoroutinefunction(method):
            await value
    assert caught.value is error


async def test_history_remains_lazy_and_partial_consumption_does_not_prefetch():
    client = make_client()
    calls = []

    async def original(peer, **options):
        calls.append((peer, options))
        yield object()
        calls.append("second")
        yield object()

    client.iter_history = original
    stream = client.chat("me").history.iter(limit=None, page_size=1)
    assert calls == []
    async for _ in stream:
        break
    assert len(calls) == 1 and calls[0][0] == "me"
    await stream.aclose()


async def test_raw_alias_uses_original_invoker_and_namespace_types():
    from gramflux.raw import functions, types

    client = make_client()
    result = object()
    client.invoke = AsyncMock(return_value=result)
    request = functions.users.GetUsersRequest(id=[types.InputUserSelf()])
    assert await client.raw.invoke(request) is result
    assert await client.raw.users.get_users(id=[types.InputUserSelf()]) is result
    assert type(client.raw.users) is type(client.api.users)
    assert client.invoke.await_count == 2


@pytest.mark.parametrize("cls,new,old", CASES)
def test_resource_parameter_defaults_and_passing_modes_match_legacy(cls, new, old):
    bound = cls in {"History", "Search", "Members", "ChatResource"}
    expected = {
        name: p
        for name, p in inspect.signature(getattr(Client, old)).parameters.items()
        if name != "self" and not (name == "peer" and bound)
    }
    actual = {
        name: p
        for name, p in inspect.signature(getattr(getattr(views, cls), new)).parameters.items()
        if name != "self"
    }
    assert actual.keys() == expected.keys()
    for name, parameter in actual.items():
        assert parameter.default == expected[name].default
        assert parameter.kind == expected[name].kind


async def test_resource_cancellation_is_not_translated_or_swallowed():
    import asyncio

    client = make_client()
    client.send_message = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await client.chat("me").send("hello")
