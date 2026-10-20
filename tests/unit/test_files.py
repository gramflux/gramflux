import asyncio
import hashlib
import io
from types import SimpleNamespace

import pytest
from telethon.tl import functions, types

from gramflux.errors import FileTransferError, UnsupportedFeature
from gramflux.files import BIG_FILE, CHUNK, download, part_count, upload


@pytest.mark.parametrize("size,parts", [(1, 1), (CHUNK, 1), (CHUNK + 1, 2), (CHUNK * 4000, 4000)])
def test_parts(size, parts):
    assert part_count(size) == parts


@pytest.mark.parametrize("size", [0, -1, CHUNK * 4000 + 1])
def test_invalid_size(size):
    with pytest.raises((ValueError, UnsupportedFeature)):
        part_count(size)


@pytest.mark.parametrize("length", [1, CHUNK, CHUNK + 1, BIG_FILE + 1])
async def test_upload_small_and_big(length):
    source = io.BytesIO(b"x" * length)
    requests, events = [], []

    async def invoke(req):
        requests.append(req)
        return True

    result = await upload(
        invoke, source, on_progress=lambda done, total: events.append((done, total))
    )
    assert b"".join(r.bytes for r in requests) == source.getvalue()
    assert result.parts == part_count(length)
    assert not source.closed
    if length > BIG_FILE:
        assert isinstance(result, types.InputFileBig)
        assert all(isinstance(r, functions.upload.SaveBigFilePartRequest) for r in requests)
    else:
        assert (
            result.md5_checksum == hashlib.md5(source.getvalue(), usedforsecurity=False).hexdigest()
        )
    assert events[0] == (0, length)
    assert events[-1] == (length, length)
    assert events == sorted(events)


async def test_failed_upload_and_cancellation():
    source = io.BytesIO(b"x" * (CHUNK + 1))

    async def fail(req):
        return False

    with pytest.raises(FileTransferError):
        await upload(fail, source)

    async def cancel(req):
        raise asyncio.CancelledError

    source.seek(0)
    with pytest.raises(asyncio.CancelledError):
        await upload(cancel, source)
    assert not source.closed


@pytest.mark.parametrize("length", [0, 1, CHUNK, CHUNK + 1])
async def test_download_atomic_no_overwrite(tmp_path, length):
    payload = b"x" * length

    async def invoke(req):
        return SimpleNamespace(bytes=payload[req.offset : req.offset + req.limit])

    path = tmp_path / "file"
    assert await download(invoke, object(), path, size=length) == path
    assert path.read_bytes() == payload
    with pytest.raises(FileExistsError):
        await download(invoke, object(), path, size=length)
    assert list(tmp_path.iterdir()) == [path]


async def test_partial_write_and_short_read():
    class Partial(io.BytesIO):
        def write(self, b):
            return super().write(b[:2])

    stream = Partial()

    async def invoke(req):
        return SimpleNamespace(bytes=b"abcde")

    await download(invoke, object(), stream, size=5)
    assert stream.getvalue() == b"abcde"
    with pytest.raises(FileTransferError):
        await download(invoke, object(), io.BytesIO(), size=CHUNK + 1)


async def test_download_interruption_cleans_temp(tmp_path):
    async def cancel(req):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await download(cancel, object(), tmp_path / "file", size=1)
    assert not list(tmp_path.iterdir())


async def test_async_progress_can_cancel(tmp_path):
    async def invoke(req):
        return True

    async def progress(done, total):
        raise asyncio.CancelledError

    p = tmp_path / "input"
    p.write_bytes(b"hello")
    with pytest.raises(asyncio.CancelledError):
        await upload(invoke, p, on_progress=progress)
    # Caller file can immediately be replaced; owned handle was closed.
    p.unlink()
