"""Encrypted controlled peers verify correlation, cancellation and failure semantics."""

import asyncio
import struct
import time
from contextlib import asynccontextmanager

import pytest

from gramflux.errors import FloodWait, SerializationError, TransportError
from gramflux.mtproto import crypto, protocol
from gramflux.mtproto.sender import Sender, unpack_gzip
from gramflux.raw import functions, types
from gramflux.tl import Codec

AUTH = bytes(range(256))
SESSION = 12345
SALT = 7654321


class Peer:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        self.closed = False
        self.last_id = 0
        self.codec = Codec()

    async def send(self, data):
        if self.closed:
            raise ConnectionError("controlled disconnected socket")
        value = crypto.decrypt(AUTH, data, SESSION, incoming=False)
        await self.outgoing.put(value)

    async def receive(self):
        return await self.incoming.get()

    async def close(self):
        self.closed = True

    def next_id(self):
        self.last_id = max((int(time.time() * 2**32) & ~3) | 1, self.last_id + 4)
        return self.last_id

    async def push(self, body, *, salt=SALT, ident=None, sequence=1):
        ident = ident or self.next_id()
        packet = crypto.encrypt(
            AUTH, crypto.Envelope(salt, SESSION, ident, sequence, body), incoming=True
        )
        await self.incoming.put(packet)
        return ident

    async def result(self, request, value):
        body = struct.pack("<Iq", 0xF35C6D01, request.message_id) + self.codec.encode(value)
        return await self.push(body)

    async def request(self):
        async with asyncio.timeout(3):
            while True:
                value = await self.outgoing.get()
                if value.body[:4] != struct.pack("<I", 0x62D6B459):
                    return value


@asynccontextmanager
async def pair(**kwargs):
    peer = Peer()
    sender = Sender(peer, AUTH, SALT, **kwargs)
    sender.session = SESSION
    sender.start()
    try:
        async with asyncio.timeout(5):
            yield sender, peer
    finally:
        await sender.close()


def request():
    return functions.help.GetNearestDcRequest()


def result(country):
    return types.NearestDc(country=country, this_dc=2, nearest_dc=2)


async def test_out_of_order_rpc_responses_and_acknowledgments():
    async with pair() as (sender, peer):
        first = asyncio.create_task(sender.invoke(request()))
        a = await peer.request()
        second = asyncio.create_task(sender.invoke(request()))
        b = await peer.request()
        second_id = await peer.result(b, result("BB"))
        assert (await second).country == "BB"
        assert not first.done()
        first_id = await peer.result(a, result("AA"))
        assert (await first).country == "AA"
        assert a.message_id < b.message_id and a.sequence == 1 and b.sequence == 3
        ack_ids = []
        while len(ack_ids) < 2:
            value = await peer.outgoing.get()
            ack_ids.extend(protocol.CODEC.decode(value.body).msg_ids)
        assert set(ack_ids) == {first_id, second_id}
        assert not sender.pending


async def test_cancellation_and_late_response_do_not_cancel_unrelated_request():
    async with pair() as (sender, peer):
        cancelled = asyncio.create_task(sender.invoke(request()))
        a = await peer.request()
        survivor = asyncio.create_task(sender.invoke(request()))
        b = await peer.request()
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        await peer.result(a, result("ignored"))
        await peer.result(b, result("received"))
        assert (await survivor).country == "received"
        assert not sender.pending


async def test_timeout_covers_admission_and_bounds_outstanding_requests():
    async with pair(max_pending=1) as (sender, peer):
        first = asyncio.create_task(sender.invoke(request(), deadline_seconds=1))
        await peer.request()
        with pytest.raises(TimeoutError):
            await sender.invoke(request(), deadline_seconds=0.02)
        assert len(sender.pending) == 1 and peer.outgoing.empty()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not sender.pending


async def test_authenticated_flood_response_is_mapped_without_resending():
    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        sent = await peer.request()
        error = protocol.CODEC.encode(
            protocol.object("rpc_error", error_code=420, error_message="FLOOD_WAIT_7")
        )
        await peer.push(struct.pack("<Iq", 0xF35C6D01, sent.message_id) + error)
        with pytest.raises(FloodWait) as caught:
            await task
        assert caught.value.seconds == 7
        assert sender.content_count == 1 and not sender.pending


async def test_bad_salt_explicit_rejection_resends_once_with_correct_salt():
    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        sent = await peer.request()
        body = protocol.CODEC.encode(
            protocol.object(
                "bad_server_salt",
                bad_msg_id=sent.message_id,
                bad_msg_seqno=sent.sequence,
                error_code=48,
                new_server_salt=-900,
            )
        )
        await peer.push(body, salt=-900)
        resent = await peer.request()
        assert resent.salt == -900 and resent.body == sent.body
        assert resent.message_id > sent.message_id
        response = struct.pack("<Iq", 0xF35C6D01, resent.message_id) + Codec().encode(result("OK"))
        await peer.push(response, salt=-900)
        assert (await task).country == "OK"
        assert sender.salt == -900


async def test_repeated_salt_rejection_fails_closed_instead_of_looping():
    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        for _ in range(2):
            sent = await peer.request()
            await peer.push(
                protocol.CODEC.encode(
                    protocol.object(
                        "bad_server_salt",
                        bad_msg_id=sent.message_id,
                        bad_msg_seqno=sent.sequence,
                        error_code=48,
                        new_server_salt=SALT,
                    )
                )
            )
        await sender.disconnected
        with pytest.raises(TransportError):
            await task
        assert isinstance(sender.error, SerializationError)
        assert sender.content_count == 2


async def test_container_correlates_each_nested_response_and_rejects_replay():
    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        sent = await peer.request()
        inner = struct.pack("<Iq", 0xF35C6D01, sent.message_id) + Codec().encode(result("OK"))
        nested_id = peer.next_id()
        outer_id = peer.next_id()
        container = struct.pack("<IIQii", 0x73F1F8DC, 1, nested_id, 1, len(inner)) + inner
        await peer.push(container, ident=outer_id)
        assert (await task).country == "OK"
        await peer.push(container, ident=outer_id)
        await asyncio.sleep(0)
        assert not sender.disconnected.done()
        assert outer_id in sender.seen and nested_id in sender.seen


@pytest.mark.parametrize(
    "body", [struct.pack("<II", 0x73F1F8DC, 1025), struct.pack("<I", 0xDEADBEEF)]
)
async def test_malformed_authenticated_protocol_data_fails_pending_requests(body):
    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        await peer.request()
        await peer.push(body)
        await sender.disconnected
        with pytest.raises(TransportError):
            await task
        assert isinstance(sender.error, SerializationError)
        assert peer.closed


async def test_bounded_update_queue_overflow_disconnects_explicitly():
    async with pair(queue_size=1) as (sender, peer):
        update = Codec().encode(
            types.UpdateShort(
                update=types.UpdateUserStatus(user_id=12, status=types.UserStatusEmpty()),
                date=int(time.time()),
            )
        )
        await peer.push(update)
        await peer.push(update)
        await sender.disconnected
        assert sender.updates.qsize() == 1
        assert isinstance(sender.error, TransportError)
        assert "overflow" in str(sender.error)


async def test_write_failure_cleans_correlation_and_closes_connection():
    async with pair() as (sender, peer):
        peer.closed = True
        with pytest.raises(TransportError):
            await sender.invoke(request())
        assert not sender.pending and sender.disconnected.done()


def test_replay_floor_blocks_evicted_message_ids():
    async def run():
        peer = Peer()
        sender = Sender(peer, AUTH, SALT)
        ids = []
        for _ in range(4100):
            ident = peer.next_id()
            ids.append(ident)
            assert sender._validate_id(ident)
        assert len(sender.seen) == 4096
        assert not sender._validate_id(ids[0])
        assert not sender._validate_id(ids[-1])

    asyncio.run(run())


def test_gzip_limits_and_trailing_data():
    import gzip

    data = gzip.compress(b"x" * 100)
    assert unpack_gzip(data) == b"x" * 100
    with pytest.raises(SerializationError):
        unpack_gzip(data, limit=99)
    with pytest.raises(SerializationError):
        unpack_gzip(data + b"extra")
    with pytest.raises(SerializationError):
        unpack_gzip(data[:-1])


async def test_salt_rotation_inside_container_with_correlated_rpc_result():
    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        sent = await peer.request()
        body = struct.pack("<Iq", 0xF35C6D01, sent.message_id) + Codec().encode(result("rotated"))
        nested = peer.next_id()
        outer = peer.next_id()
        container = struct.pack("<IIQii", 0x73F1F8DC, 1, nested, 1, len(body)) + body
        await peer.push(container, ident=outer, salt=-800)
        assert (await task).country == "rotated"
        assert sender.salt == -800
        # A previously seen envelope must never roll salt backward before deduplication.
        await peer.push(container, ident=outer, salt=SALT)
        await asyncio.sleep(0)
        assert sender.salt == -800


async def test_authenticated_clock_rejection_resynchronizes_and_reissues_once():
    async with pair() as (sender, peer):
        sender.offset = 1000
        task = asyncio.create_task(sender.invoke(request()))
        bad = await peer.request()
        notice = protocol.CODEC.encode(
            protocol.object(
                "bad_msg_notification",
                bad_msg_id=bad.message_id,
                bad_msg_seqno=bad.sequence,
                error_code=17,
            )
        )
        await peer.push(notice, sequence=0)
        corrected = await peer.request()
        assert corrected.message_id < bad.message_id
        assert abs(corrected.message_id / 2**32 - time.time()) < 2
        await peer.result(corrected, result("corrected"))
        assert (await task).country == "corrected"
        assert abs(sender.offset) < 2


async def test_detailed_answer_notification_requests_missing_answer_once():
    async with pair() as (sender, peer):
        answer = peer.next_id()
        detailed = protocol.CODEC.encode(
            protocol.object("msg_new_detailed_info", answer_msg_id=answer, bytes=100, status=0)
        )
        await peer.push(detailed, sequence=0)
        outgoing = await peer.request()
        request_object = protocol.CODEC.decode(outgoing.body)
        assert request_object.definition.name == "msg_resend_req"
        assert request_object.msg_ids == [answer]
        await peer.push(detailed, sequence=0)
        await asyncio.sleep(0)
        assert not sender.disconnected.done()


async def test_message_ids_have_fractional_bits_even_at_exact_second(monkeypatch):
    peer = Peer()
    sender = Sender(peer, AUTH, SALT)
    monkeypatch.setattr("gramflux.mtproto.sender.time.time_ns", lambda: 10**18)
    first = sender.next_id()
    second = sender.next_id()
    assert first % 4 == second % 4 == 0
    assert first & 0xFFFFFFFF and second > first


async def test_server_session_reset_signals_update_difference_recovery():
    async with pair() as (sender, peer):
        for unique in (100, 200):
            task = asyncio.create_task(sender.invoke(request()))
            sent = await peer.request()
            notification = protocol.CODEC.encode(
                protocol.object(
                    "new_session_created",
                    first_msg_id=sent.message_id,
                    unique_id=unique,
                    server_salt=SALT,
                )
            )
            await peer.push(notification)
            await peer.result(sent, result("OK"))
            assert (await task).country == "OK"
        assert sender.updates.qsize() == 1
        marker = sender.updates.get_nowait()
        assert marker.definition.name == "new_session_created" and marker.unique_id == 200


async def test_clock_correction_retains_recent_ids_assigned_after_other_rejection():
    peer = Peer()
    sender = Sender(peer, AUTH, SALT)
    now = peer.next_id()
    assigned = now + 2**20
    sender.last_id = assigned
    sender._adjust_clock(now)
    assert sender.last_id == assigned
    assert sender.next_id() > assigned
    sender.last_id = now + 1000 * 2**32
    sender._adjust_clock(now)
    assert sender.last_id == 0


async def test_heartbeat_control_slot_is_available_when_application_window_is_full():
    async with pair(max_pending=1) as (sender, peer):
        application = asyncio.create_task(sender.invoke(request()))
        await peer.request()
        control = asyncio.create_task(
            sender.invoke(protocol.object("ping", ping_id=123), _control=True)
        )
        sent = await peer.request()
        assert sent.body[:4] == struct.pack("<I", 0x7ABE77EC)
        await peer.push(
            protocol.CODEC.encode(protocol.object("pong", msg_id=sent.message_id, ping_id=123)),
            sequence=0,
        )
        assert (await control).ping_id == 123 and not application.done()
        application.cancel()
        with pytest.raises(asyncio.CancelledError):
            await application
        with pytest.raises(ValueError):
            await sender.invoke(request(), _control=True)


async def test_cancelled_codec_work_holds_admission_until_worker_is_joined(monkeypatch):
    import threading

    started, release = threading.Event(), threading.Event()
    async with pair(max_pending=1) as (sender, peer):
        encode = sender.codec.encode

        def slow_encode(value):
            started.set()
            assert release.wait(5)
            return encode(value)

        monkeypatch.setattr(sender.codec, "encode", slow_encode)
        operation = asyncio.create_task(sender.invoke(request()))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            operation.cancel()
            await asyncio.sleep(0)
            operation.cancel()
            with pytest.raises(TimeoutError):
                await sender.invoke(request(), deadline_seconds=0.02)
            assert not operation.done() and peer.outgoing.empty()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await operation
        assert not sender.pending and sender.content_count == 0


async def test_update_byte_overflow_closes_before_count_limit_and_clears_on_shutdown():
    body = Codec().encode(
        types.UpdateShort(
            update=types.UpdateUserStatus(user_id=12, status=types.UserStatusEmpty()),
            date=100,
        )
    )
    async with pair(queue_size=256, queue_bytes=len(body)) as (sender, peer):
        await peer.push(body)
        await peer.push(body)
        await sender.disconnected
        assert sender.updates.qsize() == 1
        assert sender.updates.queued_bytes == len(body)
        assert isinstance(sender.error, TransportError)
    assert sender.updates.empty() and sender.updates.queued_bytes == 0


async def test_lost_response_is_explicitly_ambiguous_but_closed_admission_is_not():
    from gramflux.errors import RequestOutcomeUnknown

    async with pair() as (sender, peer):
        task = asyncio.create_task(sender.invoke(request()))
        await peer.request()
        sender.reader_task.cancel()
        with pytest.raises(RequestOutcomeUnknown):
            await task
        with pytest.raises(TransportError) as caught:
            await sender.invoke(request())
        assert not isinstance(caught.value, RequestOutcomeUnknown)
