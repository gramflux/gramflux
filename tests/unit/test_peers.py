import json

import pytest

from gramflux import Config
from gramflux.errors import ConfigurationError, PeerNotFound, SessionError
from gramflux.peers import PeerCache, PeerResolver
from gramflux.raw import types
from gramflux.storage import SessionData


def test_cache_min_entities_do_not_poison_full_access_hash():
    cache = PeerCache()
    cache.ingest(types.User(id=12, access_hash=123, username="original"))
    cache.ingest(types.User(id=12, access_hash=999, username="different", min=True))
    assert cache.get(12).access_hash == 123
    assert cache.by_name("original").id == 12
    assert cache.by_name("different") is None
    assert "123" not in repr(cache.get(12))


def test_username_change_and_reassignment_invalidates_prior_lookup():
    cache = PeerCache()
    cache.ingest(types.User(id=12, access_hash=123, username="first"))
    cache.ingest(types.User(id=12, access_hash=123, username="second"))
    assert cache.by_name("first") is None
    assert cache.by_name("SECOND").id == 12
    cache.ingest(types.User(id=13, access_hash=124, username="second"))
    assert cache.by_name("second").id == 13
    cache.ingest(types.User(id=12, access_hash=123))
    assert cache.by_name("second").id == 13


def test_peer_cache_lru_includes_entity_and_username_eviction():
    cache = PeerCache(2)
    cache.ingest(types.User(id=1, access_hash=10, username="one"))
    cache.ingest(types.User(id=2, access_hash=20, username="two"))
    cache.get(1)
    cache.ingest(types.User(id=3, access_hash=30, username="three"))
    assert cache.get(2) is None and cache.entity(2) is None
    assert cache.by_name("two") is None
    assert [p["id"] for p in cache.dump()] == [1, 3]


def test_peer_cache_persistence_is_additive_and_can_restore_into_smaller_cache():
    cache = PeerCache()
    cache.ingest(
        [
            types.User(id=12, access_hash=-123, username="some_user"),
            types.ChannelForbidden(id=50, access_hash=456, title="Title"),
        ]
    )
    restored = PeerCache(1)
    restored.restore(SessionData(json.dumps({"peers": cache.dump()}).encode()))
    assert restored.get(-1000000000050).input_peer().access_hash == 456
    assert restored.get(12) is None
    restored.restore(SessionData(b'{"version":1}'))
    assert restored.dump() == []


@pytest.mark.parametrize(
    "row",
    [
        {"id": True, "kind": "user", "access_hash": 0, "username": None},
        {"id": -2, "kind": "user", "access_hash": 0, "username": None},
        {"id": 2, "kind": "user", "access_hash": True, "username": None},
        {"id": 2, "kind": "user", "access_hash": 2**64, "username": None},
        {"id": 2, "kind": "user", "access_hash": 0, "username": "has spaces"},
    ],
)
def test_invalid_stored_peer_is_rejected(row):
    with pytest.raises(SessionError):
        PeerCache().restore(SessionData(json.dumps({"peers": [row]}).encode()))


@pytest.mark.parametrize("capacity", [0, -1, True, 4097])
def test_bad_capacity(capacity):
    with pytest.raises(ConfigurationError):
        Config(peer_cache_size=capacity)
    with pytest.raises(ConfigurationError):
        PeerCache(capacity)


async def test_resolution_caches_names_but_refreshes_explicitly():
    calls = []

    async def invoke(request):
        calls.append(request)
        return types.contacts.ResolvedPeer(
            peer=types.PeerUser(user_id=12),
            chats=[],
            users=[types.User(id=12, access_hash=123, username="some_user")],
        )

    resolver = PeerResolver(invoke)
    assert (await resolver.resolve("@some_user")).user_id == 12
    assert (await resolver.resolve("SOME_USER")).access_hash == 123
    assert len(calls) == 1
    await resolver.resolve("some_user", refresh=True)
    assert len(calls) == 2
    assert (await resolver.resolve(12)).access_hash == 123


async def test_unknown_id_never_uses_a_guessed_zero_hash():

    async def forbidden(request):
        raise AssertionError("no RPC should be attempted for an unknown numeric hash")

    resolver = PeerResolver(forbidden)
    for peer in [12, -1000000000050, types.PeerUser(user_id=12)]:
        with pytest.raises(PeerNotFound):
            await resolver.resolve(peer)
    assert (await resolver.resolve(-50)).chat_id == 50
    assert isinstance(await resolver.resolve("me"), types.InputPeerSelf)
    for bad in [True, 0, "https://t.me/some_user", "+123456"]:
        with pytest.raises(ConfigurationError):
            await resolver.resolve(bad)


async def test_self_peer_without_hash_remains_usable_after_restart():

    async def forbidden(request):
        raise AssertionError("self peer must not require network resolution")

    cache = PeerCache()
    cache.ingest(types.User(id=42, self=True, username="own_name"))
    resolver = PeerResolver(forbidden)
    resolver.cache.restore(SessionData(json.dumps({"peers": cache.dump()}).encode()))
    assert isinstance(await resolver.resolve(42), types.InputPeerSelf)
    assert isinstance(await resolver.resolve("me"), types.InputPeerSelf)


def test_username_cache_has_a_monotonic_lifetime():
    now = [0.0]
    cache = PeerCache(clock=lambda: now[0])
    cache.ingest(types.User(id=12, access_hash=123, username="old_name"))
    assert cache.by_name("old_name").id == 12
    now[0] = 60.0
    assert cache.by_name("old_name") is None
    assert cache.get(12).access_hash == 123


async def test_restored_username_is_resolved_again_to_avoid_reassigned_names():
    cache = PeerCache()
    cache.ingest(types.User(id=12, access_hash=123, username="old_name"))

    async def invoke(request):
        return types.contacts.ResolvedPeer(
            peer=types.PeerUser(user_id=13),
            chats=[],
            users=[types.User(id=13, access_hash=456, username="old_name")],
        )

    resolver = PeerResolver(invoke)
    resolver.cache.restore(SessionData(json.dumps({"peers": cache.dump()}).encode()))
    assert (await resolver.resolve("old_name")).user_id == 13
    assert (await resolver.resolve(12)).access_hash == 123


async def test_failed_explicit_refresh_cannot_fall_back_to_stale_username():
    from gramflux.errors import RPCError

    count = 0

    async def invoke(request):
        nonlocal count
        count += 1
        raise RPCError(400, "USERNAME_NOT_OCCUPIED")

    resolver = PeerResolver(invoke)
    resolver.cache.ingest(types.User(id=12, access_hash=123, username="old_name"))
    with pytest.raises(RPCError):
        await resolver.resolve("old_name", refresh=True)
    assert resolver.cache.by_name("old_name") is None
    with pytest.raises(RPCError):
        await resolver.resolve("old_name")
    assert count == 2
