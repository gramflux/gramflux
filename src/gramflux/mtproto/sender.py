"""Native encrypted request correlation. No automatic retries after network ambiguity."""

import asyncio
import secrets
import struct
import time
import zlib
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from gramflux.errors import RequestOutcomeUnknown, RPCError, SerializationError, TransportError
from gramflux.tl import Codec
from gramflux.tl.codec import Reader
from gramflux.tl.model import TLObject

from . import crypto, protocol
from .connection import Connection
from .queue import UpdateQueue
from .workers import compute


def unpack_gzip(data: bytes, limit: int = 16 * 1024 * 1024) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        result = decoder.decompress(data, limit + 1)
    except zlib.error:
        raise SerializationError("invalid gzip stream") from None
    if len(result) > limit or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
        raise SerializationError("gzip payload exceeds bounds or has invalid framing")
    return result


@dataclass(slots=True)
class Pending:
    request: TLObject = field(repr=False)
    future: asyncio.Future[Any] = field(repr=False)
    sequence: int
    resends: int = 0


class Sender:
    def __init__(
        self,
        connection: Connection,
        auth: bytes,
        salt: int,
        *,
        time_offset: float = 0,
        queue_size: int = 256,
        max_pending: int = 32,
        queue_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        self.connection = connection
        self.auth = auth
        self.salt = salt
        self.offset = time_offset
        self.session = int.from_bytes(secrets.token_bytes(8), "little", signed=True)
        self.last_id = 0
        self.content_count = 0
        self.pending: dict[int, Pending] = {}
        self.updates = UpdateQueue(queue_size, queue_bytes)
        self.admission = asyncio.Semaphore(max_pending)
        self.control_admission = asyncio.Semaphore(2)
        self.send_lock = asyncio.Lock()
        from gramflux.tl.generated.objects import REGISTRY

        self.codec = Codec(REGISTRY | protocol.CODEC.registry)
        self.reader_task: asyncio.Task[None] | None = None
        self.disconnected: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self.error: Exception | None = None
        self.seen: set[int] = set()
        self.recent: deque[int] = deque()
        self.acks: list[int] = []
        self.replay_floor = 0
        self.outbound: set[int] = set()
        self.outbound_order: deque[int] = deque()
        self.resend_answers: set[int] = set()
        self.last_new_session: int | None = None

    def start(self) -> None:
        self.reader_task = asyncio.create_task(self._read_loop(), name="gramflux-native-receive")

    def next_id(self) -> int:
        value = ((time.time_ns() + int(self.offset * 10**9)) * 2**32 // 10**9) & ~3
        self.last_id = max(value, self.last_id + 4)
        if self.last_id & 0xFFFFFFFF == 0:
            self.last_id += 4
        return self.last_id

    def _nodes(self, body: bytes, depth: int = 0) -> Iterator[bytes]:
        if depth > 8 or len(body) < 4:
            raise SerializationError("invalid service container")
        reader = Reader(memoryview(body))
        constructor = reader.uint()
        if constructor == 0x73F1F8DC:
            count = reader.uint()
            if not 1 <= count <= 1024:
                raise SerializationError("invalid service container size")
            for _ in range(count):
                _, _, length = struct.unpack("<Qii", reader.take(16))
                if length < 4 or length % 4:
                    raise SerializationError("invalid service container body")
                yield from self._nodes(reader.take(length), depth + 1)
            if reader.offset != len(body):
                raise SerializationError("trailing service container bytes")
        elif constructor == 0x3072CFA1:
            yield from self._nodes(unpack_gzip(protocol.CODEC.decode(body).packed_data), depth + 1)
        else:
            yield body

    def _adjust_clock(self, server_id: int) -> None:
        server_time = server_id / 2**32
        self.offset = server_time - time.time()
        # Reset only a rejected far-future high-water mark; preserve IDs already
        # assigned near the corrected clock while other rejections were in flight.
        if self.last_id / 2**32 > server_time + 30:
            self.last_id = 0

    def _check_control_metadata(self, envelope: crypto.Envelope) -> None:
        if envelope.message_id in self.seen or envelope.message_id <= self.replay_floor:
            return  # Replays must never roll back clock/salt, even before body deduplication.
        now = time.time() + self.offset
        if envelope.salt == self.salt and now - 300 <= envelope.message_id / 2**32 <= now + 30:
            return
        salt_allowed = envelope.salt == self.salt
        for body in self._nodes(envelope.body):
            kind = int.from_bytes(body[:4], "little")
            if kind == 0xF35C6D01 and len(body) >= 16:
                reference = int.from_bytes(body[4:12], "little", signed=True)
                if reference in self.pending:
                    salt_allowed = True
            elif kind in (0xEDAB447B, 0xA7EFF811):
                value = protocol.CODEC.decode(body)
                item = self.pending.get(value.bad_msg_id)
                if item is not None and item.sequence == value.bad_msg_seqno:
                    if value.error_code in (16, 17) and item.resends == 0:
                        self._adjust_clock(envelope.message_id)
                    if (
                        kind == 0xEDAB447B
                        and value.error_code == 48
                        and value.new_server_salt == envelope.salt
                    ):
                        salt_allowed = True
            elif kind == 0x9EC20908:
                value = protocol.CODEC.decode(body)
                if value.first_msg_id in self.outbound and value.server_salt == envelope.salt:
                    salt_allowed = True
        if not salt_allowed:
            raise SerializationError("unrecognized incoming server salt")
        self.salt = envelope.salt

    async def _send(self, body: bytes, pending: Pending | None = None) -> int:
        committed = False

        async def write() -> int:
            nonlocal committed
            async with self.send_lock:
                if self.disconnected.done():
                    raise TransportError("native connection is closed")
                committed = True
                ident = self.next_id()
                self.outbound.add(ident)
                self.outbound_order.append(ident)
                if len(self.outbound_order) > 4096:
                    self.outbound.remove(self.outbound_order.popleft())
                sequence = 2 * self.content_count + (1 if pending else 0)
                if pending:
                    self.content_count += 1
                    pending.sequence = sequence
                    self.pending[ident] = pending
                envelope = crypto.Envelope(self.salt, self.session, ident, sequence, body)
                packet = await compute(crypto.encrypt, self.auth, envelope)
                await self.connection.send(packet)
                return ident

        task = asyncio.create_task(write(), name="gramflux-native-send")
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if not committed:
                task.cancel()
            while not task.done():
                try:
                    await asyncio.wait({task})
                except asyncio.CancelledError:
                    continue
            if not task.cancelled():
                task.exception()
            raise
        except Exception:
            self.error = (
                RequestOutcomeUnknown("native write failed; remote outcome may be unknown")
                if committed
                else TransportError("native request was not committed to the connection")
            )
            if self.reader_task is not asyncio.current_task():
                await self.close()
            raise self.error from None

    async def invoke(
        self, request: TLObject, *, deadline_seconds: float = 30, _control: bool = False
    ) -> Any:
        if not isinstance(request, TLObject) or not request.definition.method:
            raise TypeError("native invoke requires a generated method")
        if _control and request.definition.name not in {"ping", "ping_delay_disconnect"}:
            raise ValueError("reserved control slots accept only native liveness methods")
        admission = self.control_admission if _control else self.admission
        async with asyncio.timeout(deadline_seconds):
            async with admission:
                body = await compute(self.codec.encode, request)
                pending = Pending(request, asyncio.get_running_loop().create_future(), 0)
                try:
                    await self._send(body, pending)
                    return await pending.future
                finally:
                    for ident, item in list(self.pending.items()):
                        if item is pending:
                            self.pending.pop(ident)
                    if not pending.future.done():
                        pending.future.cancel()
                    elif not pending.future.cancelled():
                        pending.future.exception()

    async def service(self, name: str, **fields: Any) -> None:
        await self._send(protocol.CODEC.encode(protocol.object(name, **fields)))

    def _validate_id(self, ident: int) -> bool:
        now = time.time() + self.offset
        if ident % 4 not in (1, 3) or not now - 300 <= ident / 2**32 <= now + 30:
            raise SerializationError("invalid server message identifier or time")
        if ident in self.seen or ident <= self.replay_floor:
            return False
        self.seen.add(ident)
        self.recent.append(ident)
        if len(self.recent) > 4096:
            expired = self.recent.popleft()
            self.seen.remove(expired)
            self.replay_floor = max(self.replay_floor, expired)
        return True

    def _offer(self, update: TLObject, *, wire_size: int) -> None:
        try:
            self.updates.put_nowait(update, size=wire_size)
        except asyncio.QueueFull:
            raise TransportError(
                "native update queue overflow; reconnect and resynchronize"
            ) from None

    async def _process(self, body: bytes, ident: int, sequence: int, *, depth: int = 0) -> None:
        if depth > 8 or len(body) < 4 or len(body) % 4 or sequence < 0:
            raise SerializationError("invalid protocol message/container")
        if not self._validate_id(ident):
            if sequence % 2:
                self.acks.append(ident)
            return
        if sequence % 2:
            self.acks.append(ident)
        self.resend_answers.discard(ident)
        reader = Reader(memoryview(body))
        constructor = reader.uint()
        if constructor == 0x73F1F8DC:
            count = reader.uint()
            if not 1 <= count <= 1024:
                raise SerializationError("invalid container message count")
            for _ in range(count):
                nested_id, nested_seq, length = struct.unpack("<Qii", reader.take(16))
                if nested_id >= ident or length < 4 or length % 4:
                    raise SerializationError("invalid nested message metadata")
                await self._process(reader.take(length), nested_id, nested_seq, depth=depth + 1)
            if reader.offset != len(body):
                raise SerializationError("trailing container data")
        elif constructor == 0x3072CFA1:
            compressed = protocol.CODEC.decode(body).packed_data
            # Wrapper and decompressed object represent the same message, so do not recheck ID.
            self.seen.remove(ident)
            self.recent.remove(ident)
            await self._process(unpack_gzip(compressed), ident, sequence, depth=depth + 1)
        elif constructor == 0xF35C6D01:
            request_id = int.from_bytes(reader.take(8), "little", signed=True)
            item = self.pending.get(request_id)
            if item is None or item.future.done():
                return
            result = reader.take(len(body) - reader.offset)
            if result[:4] == struct.pack("<I", 0x3072CFA1):
                result = unpack_gzip(protocol.CODEC.decode(result).packed_data)
            if result[:4] == struct.pack("<I", 0x2144CA19):
                error = protocol.CODEC.decode(result)
                from gramflux.backend import rpc_error

                item.future.set_exception(rpc_error(error.error_code, error.error_message))
            else:
                request = item.request
                while request.definition.result == "X":
                    request = request.query
                value = await compute(self.codec.decode, result, request.definition.result)
                if not item.future.done():
                    item.future.set_result(value)
        elif constructor == 0xEDAB447B:
            value = protocol.CODEC.decode(body)
            item = self.pending.get(value.bad_msg_id)
            if (
                item is None
                or item.sequence != value.bad_msg_seqno
                or value.error_code != 48
                or item.resends >= 1
            ):
                raise SerializationError("invalid/repeated bad salt rejection")
            self.pending.pop(value.bad_msg_id)
            self.salt = value.new_server_salt
            item.resends += 1
            await self._send(self.codec.encode(item.request), item)
        elif constructor == 0x9EC20908:
            value = protocol.CODEC.decode(body)
            if value.first_msg_id not in self.outbound:
                raise SerializationError("invalid new-session reference")
            self.salt = value.server_salt
            if self.last_new_session is not None and self.last_new_session != value.unique_id:
                self._offer(value, wire_size=len(body))
            self.last_new_session = value.unique_id
        elif constructor == 0xA7EFF811:
            value = protocol.CODEC.decode(body)
            item = self.pending.get(value.bad_msg_id)
            if item is None or item.sequence != value.bad_msg_seqno:
                raise SerializationError("bad-message notification has no matching request")
            if value.error_code in (16, 17) and item.resends < 1:
                self._adjust_clock(ident)
                self.pending.pop(value.bad_msg_id)
                item.resends += 1
                await self._send(self.codec.encode(item.request), item)
            elif not item.future.done():
                item.future.set_exception(
                    TransportError(
                        f"protocol rejected message ({value.error_code}); reconnect explicitly"
                    )
                )
        elif constructor in (0x276D3EC6, 0x809DB6DF):
            value = protocol.CODEC.decode(body)
            answer = value.answer_msg_id
            if answer % 4 not in (1, 3) or answer >= ident:
                raise SerializationError("invalid detailed answer identifier")
            if answer in self.seen or answer <= self.replay_floor:
                self.acks.append(answer)
            elif answer not in self.resend_answers:
                if len(self.resend_answers) >= 1024:
                    raise TransportError("answer-resend tracking budget exceeded")
                self.resend_answers.add(answer)
                await self.service("msg_resend_req", msg_ids=[answer])
        elif constructor == 0xDA69FB52:
            value = protocol.CODEC.decode(body)
            if len(value.msg_ids) > 8192:
                raise SerializationError("message-state request exceeds protocol bound")
            info = bytes(
                12 if message_id in self.seen or message_id <= self.replay_floor else 1
                for message_id in value.msg_ids
            )
            await self.service("msgs_state_info", req_msg_id=ident, info=info)
        elif constructor in (0xF660E1D4, 0x0A9F2259, 0xEA109B13):
            matches = [
                item
                for item in self.pending.values()
                if item.request.definition.name == "destroy_auth_key"
            ]
            if len(matches) != 1:
                raise SerializationError("ambiguous authorization-key destruction response")
            if not matches[0].future.done():
                matches[0].future.set_result(protocol.CODEC.decode(body))
        elif constructor in (0x62D6B459, 0x347773C5, 0x04DEB57D):
            if constructor == 0x347773C5:
                pong = protocol.CODEC.decode(body)
                item = self.pending.get(pong.msg_id)
                if item and not item.future.done():
                    item.future.set_result(pong)
        else:
            value = await compute(self.codec.decode, body)
            self._offer(value, wire_size=len(body))

    async def _read_loop(self) -> None:
        try:
            while True:
                packet = await self.connection.receive()
                envelope = await compute(crypto.decrypt, self.auth, packet, self.session)
                self._check_control_metadata(envelope)
                await self._process(envelope.body, envelope.message_id, envelope.sequence)
                if self.acks:
                    acknowledged = list(dict.fromkeys(self.acks))
                    self.acks.clear()
                    for offset in range(0, len(acknowledged), 8192):
                        await self.service("msgs_ack", msg_ids=acknowledged[offset : offset + 8192])
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError, RPCError, SerializationError, TransportError) as error:
            self.error = error
        except Exception as error:
            # Unexpected failures are also terminal; never leave waiters hanging or log payloads.
            self.error = TransportError(f"native receive failed ({type(error).__name__})")
        finally:
            for item in self.pending.values():
                if not item.future.done():
                    item.future.set_exception(
                        RequestOutcomeUnknown(
                            "native connection closed; remote outcome may be unknown"
                        )
                    )
            if not self.disconnected.done():
                self.disconnected.set_result(None)
            await self.connection.close()

    async def close(self) -> None:
        await self.connection.close()
        if self.reader_task:
            self.reader_task.cancel()
            await asyncio.gather(self.reader_task, return_exceptions=True)
        else:
            await self.connection.close()
        self.auth = b""
        while not self.updates.empty():
            self.updates.get_nowait()
            self.updates.task_done()
