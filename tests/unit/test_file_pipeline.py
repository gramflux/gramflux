"""Bounded transfer correctness; controlled RPCs are not Telegram integration."""

import asyncio
import hashlib
import io
import threading
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gramflux import files
from gramflux.errors import FileTransferError, FloodWait, UnsupportedFeature
from gramflux.raw import types
from tests.native_fixtures import native_date


@pytest.mark.parametrize("part_size", [True, 0, -1, 512, 3072, files.CHUNK * 2, 1024.0, "1024"])
async def test_upload_rejects_chunk_size_before_opening(tmp_path, part_size):

    async def invoke(request):
        pytest.fail("invalid parameters must not send requests")

    with pytest.raises(ValueError):
        await files.upload(invoke, tmp_path / "absent", part_size=part_size)


@pytest.mark.parametrize("concurrency", [True, 0, -1, 17, 2.0, "2"])
async def test_upload_rejects_parallelism_before_opening(tmp_path, concurrency):

    async def invoke(request):
        pytest.fail("invalid parameters must not send requests")

    with pytest.raises(ValueError):
        await files.upload(invoke, tmp_path / "absent", concurrency=concurrency)


@pytest.mark.parametrize("large", [False, True])
async def test_upload_out_of_order_acceptance_has_ordered_checksum_and_serial_progress(
    monkeypatch, large
):
    payload = bytes(range(251)) * 17
    if large:
        monkeypatch.setattr(files, "BIG_FILE", 2000)
    source = io.BytesIO(payload)
    entered = set()
    active = set()
    maximum = 0
    barrier = asyncio.Event()
    gates = [asyncio.Event() for _ in range(5)]
    completion = [2, 0, 4, 1, 3]
    blocks = {}
    progress = []
    inside_callback = False

    async def invoke(request):
        nonlocal maximum
        index = request.file_part
        entered.add(index)
        active.add(index)
        maximum = max(maximum, len(active))
        blocks[index] = request.bytes
        if len(entered) == 5:
            barrier.set()
            gates[2].set()
        try:
            await barrier.wait()
            await gates[index].wait()
            position = completion.index(index)
            if position + 1 < len(completion):
                gates[completion[position + 1]].set()
            return True
        finally:
            active.remove(index)

    async def report(done, total):
        nonlocal inside_callback
        assert not inside_callback
        inside_callback = True
        await asyncio.sleep(0)
        progress.append((done, total))
        inside_callback = False

    async with asyncio.timeout(5):
        result = await files.upload(
            invoke, source, part_size=1024, concurrency=5, on_progress=report
        )
    assert maximum == 5
    assert not active
    assert not source.closed
    assert b"".join(blocks[index] for index in sorted(blocks)) == payload
    assert result.parts == 5
    assert progress[0] == (0, len(payload))
    assert progress[-1] == (len(payload), len(payload))
    assert len(progress) == 6
    assert progress == sorted(progress)
    if large:
        assert isinstance(result, types.InputFileBig)
    else:
        assert result.md5_checksum == hashlib.md5(payload, usedforsecurity=False).hexdigest()


async def test_upload_window_bounds_reads_and_joins_peers_on_flood():
    source = io.BytesIO(b"x" * 1024 * 20)
    started = set()
    active = set()
    barrier = asyncio.Event()
    never = asyncio.Event()

    async def invoke(request):
        index = request.file_part
        assert index not in started
        started.add(index)
        active.add(index)
        if len(started) == 3:
            barrier.set()
        try:
            await barrier.wait()
            if index == 2:
                raise FloodWait(420, 9)
            await never.wait()
        finally:
            active.remove(index)

    async with asyncio.timeout(5):
        with pytest.raises(FloodWait) as error:
            await files.upload(invoke, source, part_size=1024, concurrency=3)
    assert error.value.seconds == 9
    assert started == {0, 1, 2}
    assert source.tell() == 3072
    assert not active
    assert not any(
        task.get_name().startswith("gramflux-upload-part-") for task in asyncio.all_tasks()
    )


async def test_cancel_parallel_upload_joins_every_request():
    active = 0
    barrier = asyncio.Event()
    never = asyncio.Event()

    async def invoke(request):
        nonlocal active
        active += 1
        if active == 3:
            barrier.set()
        try:
            await never.wait()
        finally:
            active -= 1

    source = io.BytesIO(b"a" * 8192)
    task = asyncio.create_task(files.upload(invoke, source, concurrency=3, part_size=1024))
    async with asyncio.timeout(5):
        await barrier.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert active == 0
    assert not source.closed


async def test_progress_failure_cancels_remaining_upload_parts():
    active = 0

    async def invoke(request):
        nonlocal active
        active += 1
        try:
            if request.file_part:
                await asyncio.Event().wait()
            return True
        finally:
            active -= 1

    def progress(done, total):
        if done:
            raise LookupError("application callback failed")

    with pytest.raises(LookupError):
        await files.upload(
            invoke, io.BytesIO(b"a" * 4096), part_size=1024, concurrency=3, on_progress=progress
        )
    assert active == 0


async def test_short_stream_reads_and_nonzero_start():

    class Short(io.BytesIO):
        def read(self, count):
            return super().read(min(count, 137))

    source = Short(b"prefix" + b"z" * 2051)
    source.seek(6)
    parts = {}

    async def invoke(request):
        parts[request.file_part] = request.bytes
        return True

    result = await files.upload(invoke, source, part_size=1024, concurrency=2)
    assert b"".join(parts[index] for index in sorted(parts)) == b"z" * 2051
    assert result.parts == 3
    assert not source.closed


async def test_upload_rejects_stream_read_exceeding_requested_length():

    class Oversized(io.BytesIO):
        def read(self, count):
            return b"x" * (count + 1)

    async def invoke(request):
        pytest.fail("bad source must not submit a part")

    with pytest.raises(FileTransferError):
        await files.upload(invoke, Oversized(b"x" * 10))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"size": True},
        {"size": -1},
        {"size": 2**63},
        {"size": 3.0},
        {"size": 10, "offset": True},
        {"size": 10, "offset": -1},
        {"size": 10, "offset": 11},
        {"size": 10, "length": 11},
        {"size": 10, "length": True},
        {"size": 10, "length": -1},
        {"size": 10, "request_size": 1024},
        {"size": 10, "request_size": 12288},
        {"size": 10, "request_size": True},
    ],
)
async def test_invalid_download_parameters_do_not_create_files(tmp_path, kwargs):

    async def invoke(request):
        pytest.fail("invalid parameters must not send requests")

    with pytest.raises(ValueError):
        await files.download(invoke, object(), tmp_path / "file", **kwargs)
    assert not list(tmp_path.iterdir())


async def test_download_iterator_is_lazy_and_aligns_both_sides_of_megabyte_boundary():
    payload = bytes(range(256)) * 8192
    calls = []

    async def invoke(request):
        calls.append(request)
        assert request.offset % 4096 == 0
        assert request.offset // 1048576 == (request.offset + request.limit - 1) // 1048576
        return SimpleNamespace(bytes=payload[request.offset : request.offset + request.limit])

    start = 1048576 - 7
    stream = files.iter_download(
        invoke, object(), size=len(payload), offset=start, length=15, request_size=4096
    )
    assert not calls
    assert await anext(stream) == payload[start:1048576]
    assert len(calls) == 1
    assert await anext(stream) == payload[1048576 : start + 15]
    assert len(calls) == 2
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    await stream.aclose()
    assert len(calls) == 2


@given(
    start=st.integers(min_value=0, max_value=1049000),
    length=st.integers(min_value=0, max_value=17000),
    request_size=st.sampled_from([4096, 16384, 131072, files.CHUNK]),
)
@settings(max_examples=30, deadline=None)
async def test_download_ranges_equal_source_slice(start, length, request_size):
    payload = bytes(range(256)) * 8192
    calls = 0

    async def invoke(request):
        nonlocal calls
        calls += 1
        assert request.offset % request_size == 0
        assert request.offset // 1048576 == (request.offset + request.limit - 1) // 1048576
        return SimpleNamespace(bytes=payload[request.offset : request.offset + request.limit])

    blocks = [
        block
        async for block in files.iter_download(
            invoke,
            object(),
            size=len(payload),
            offset=start,
            length=length,
            request_size=request_size,
        )
    ]
    assert b"".join(blocks) == payload[start : start + length]
    if not length:
        assert calls == 0
    else:
        assert calls == (start % request_size + length + request_size - 1) // request_size


async def test_range_download_progress_tracks_only_requested_bytes_and_keeps_stream_open():
    payload = b"z" * 5000 + b"abc" + b"y" * 5000
    target = io.BytesIO(b"prefix")
    target.seek(6)
    events = []

    async def invoke(request):
        return SimpleNamespace(bytes=payload[request.offset : request.offset + request.limit])

    assert (
        await files.download(
            invoke,
            object(),
            target,
            size=len(payload),
            offset=5000,
            length=3,
            request_size=4096,
            on_progress=lambda done, total: events.append((done, total)),
        )
        is None
    )
    assert target.getvalue() == b"prefixabc"
    assert events == [(0, 3), (3, 3)]
    assert not target.closed


async def test_empty_range_and_early_iterator_close_make_no_extra_requests():
    calls = 0

    async def invoke(request):
        nonlocal calls
        calls += 1
        return SimpleNamespace(bytes=b"x" * 4096)

    assert [x async for x in files.iter_download(invoke, object(), size=10000, offset=10000)] == []
    stream = files.iter_download(invoke, object(), size=10000, request_size=4096)
    assert len(await anext(stream)) == 4096
    await stream.aclose()
    assert calls == 1


@pytest.mark.parametrize("block", [b"", b"x", b"x" * 4097, None, "text"])
async def test_bad_download_responses_fail_without_publishing(tmp_path, block):

    async def invoke(request):
        return SimpleNamespace(bytes=block)

    with pytest.raises(FileTransferError):
        await files.download(invoke, object(), tmp_path / "file", size=4096, request_size=4096)
    assert not list(tmp_path.iterdir())


async def test_cdn_redirect_is_explicit_not_silently_consumed():

    async def invoke(request):
        return types.upload.FileCdnRedirect(
            dc_id=2, file_token=b"token", encryption_key=b"key", encryption_iv=b"iv", file_hashes=[]
        )

    with pytest.raises(UnsupportedFeature):
        await anext(files.iter_download(invoke, object(), size=100))


async def test_cancel_during_source_open_releases_lost_resource(monkeypatch, tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"abc")
    started, release = (threading.Event(), threading.Event())
    resources = []
    real_open = open

    def slow_open(*args):
        stream = real_open(*args)
        resources.append(stream)
        started.set()
        assert release.wait(5)
        return stream

    async def invoke(request):
        pytest.fail("cancelled acquisition must not send requests")

    monkeypatch.setattr(files, "open", slow_open, raising=False)
    task = asyncio.create_task(files.upload(invoke, path))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(resources) == 1 and resources[0].closed
    assert path.read_bytes() == b"abc"


async def test_cancel_during_temp_acquisition_closes_and_unlinks(monkeypatch, tmp_path):
    started, release = (threading.Event(), threading.Event())
    create = files._create_download
    resources = []

    def slow_create(directory):
        resource = create(directory)
        resources.append(resource)
        started.set()
        assert release.wait(5)
        return resource

    async def invoke(request):
        pytest.fail("cancelled acquisition must not send requests")

    monkeypatch.setattr(files, "_create_download", slow_create)
    task = asyncio.create_task(files.download(invoke, object(), tmp_path / "output", size=1))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert resources[0][0].closed
    assert not list(tmp_path.iterdir())


def test_media_location_chooses_largest_photo_not_last():
    photo = types.Photo(
        id=1,
        access_hash=2,
        file_reference=b"reference",
        date=native_date(None),
        sizes=[
            types.PhotoSize(type="large", w=100, h=100, size=500),
            types.PhotoSizeProgressive(type="progressive", w=100, h=100, sizes=[10, 400]),
            types.PhotoSize(type="tiny", w=1, h=1, size=5),
        ],
        dc_id=2,
    )
    location, size = files.media_location(SimpleNamespace(document=None, photo=photo))
    assert size == 500
    assert isinstance(location, types.InputPhotoFileLocation)
    assert location.thumb_size == "large"


def test_media_location_ignores_empty_progressive_list():
    photo = SimpleNamespace(sizes=[types.PhotoSizeProgressive(type="bad", w=1, h=1, sizes=[])])
    with pytest.raises(UnsupportedFeature):
        files.media_location(SimpleNamespace(document=None, photo=photo))


async def test_path_range_contains_only_selected_bytes_and_empty_range_reports_zero(tmp_path):
    payload = bytes(range(256)) * 32
    calls = []
    events = []

    async def invoke(request):
        calls.append(request)
        return SimpleNamespace(bytes=payload[request.offset : request.offset + request.limit])

    target = tmp_path / "excerpt"
    assert (
        await files.download(
            invoke, object(), target, size=len(payload), offset=4093, length=9, request_size=4096
        )
        == target
    )
    assert target.read_bytes() == payload[4093:4102]
    assert len(calls) == 2
    calls.clear()
    empty = tmp_path / "empty"
    await files.download(
        invoke,
        object(),
        empty,
        size=len(payload),
        offset=len(payload),
        on_progress=lambda done, total: events.append((done, total)),
    )
    assert empty.read_bytes() == b""
    assert events == [(0, 0)]
    assert not calls
    assert sorted(p.name for p in tmp_path.iterdir()) == ["empty", "excerpt"]


async def test_repeated_cancellation_joins_active_write_before_closing_temp(monkeypatch, tmp_path):
    entered, release = (threading.Event(), threading.Event())
    create = files._create_download
    resources = []
    writing = False

    class SlowWrite:
        def __init__(self, stream):
            self.stream = stream

        def write(self, block):
            nonlocal writing
            writing = True
            entered.set()
            try:
                assert release.wait(5)
                return self.stream.write(block)
            finally:
                writing = False

        def close(self):
            assert not writing, "must join worker before closing its handle"
            self.stream.close()

    def slow_create(directory):
        stream, name = create(directory)
        wrapper = SlowWrite(stream)
        resources.append(stream)
        return (wrapper, name)

    async def invoke(request):
        return SimpleNamespace(bytes=b"abc")

    monkeypatch.setattr(files, "_create_download", slow_create)
    task = asyncio.create_task(files.download(invoke, object(), tmp_path / "output", size=3))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and (not resources[0].closed)
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert resources[0].closed
    assert not list(tmp_path.iterdir())
