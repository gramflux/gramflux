"""Bounded concurrent uploads, lazy ranged downloads and safe disk ownership."""

import asyncio
import hashlib
import inspect
import logging
import os
import secrets
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any, BinaryIO

from .errors import FileTransferError, UnsupportedFeature
from .raw import functions, types

Progress = Callable[[int, int], Awaitable[None] | None]
CHUNK = 512 * 1024
BIG_FILE = 10 * 1024 * 1024
MAX_PARTS = 4000
logger = logging.getLogger("gramflux.files")


def _validate_chunk_size(value: int, *, download: bool = False) -> int:
    minimum = 4096 if download else 1024
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= CHUNK
        or value & (value - 1)
    ):
        raise ValueError(f"chunk size must be a power of two between {minimum} and {CHUNK}")
    return value


def part_count(size: int, chunk_size: int = CHUNK) -> int:
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("file size must be a positive integer")
    _validate_chunk_size(chunk_size)
    count = (size + chunk_size - 1) // chunk_size
    if count > MAX_PARTS:
        raise UnsupportedFeature("upload exceeds conservative 4000-part limit")
    return count


async def progress(callback: Progress | None, done: int, total: int) -> None:
    if callback is not None:
        result = callback(done, total)
        if inspect.isawaitable(result):
            await result


async def _settle(task: asyncio.Future[Any]) -> None:
    """Join a worker despite repeated caller cancellation, without cancelling it."""
    while not task.done():
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            # Cleanup must finish before the file can be closed/reused.
            continue


async def disk(
    function: Callable[..., Any],
    *args: Any,
    _on_cancel: Callable[[Any], Any] | None = None,
) -> Any:
    """Join cancelled disk work; release newly acquired resources if result is lost."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await _settle(task)
        # Cancellation remains the public outcome even if the worker also failed.
        error = task.exception() if not task.cancelled() else None
        if error is None and not task.cancelled() and _on_cancel is not None:
            cleanup = asyncio.create_task(asyncio.to_thread(_on_cancel, task.result()))
            await _settle(cleanup)
            if not cleanup.cancelled() and (failure := cleanup.exception()) is not None:
                # Preserve cancellation, report cleanup failures without paths/payloads.
                logger.error(
                    "cancelled disk acquisition cleanup failed (%s)", type(failure).__name__
                )
        raise


def _close_upload(stream: BinaryIO) -> None:
    stream.close()


def _create_download(directory: str) -> tuple[BinaryIO, str]:
    descriptor, name = tempfile.mkstemp(".part", ".gramflux-", directory)
    try:
        return os.fdopen(descriptor, "wb"), name
    except BaseException:
        os.close(descriptor)
        os.unlink(name)
        raise


def _remove_download(resource: tuple[BinaryIO, str]) -> None:
    stream, name = resource
    try:
        stream.close()
    finally:
        os.unlink(name)


async def upload(
    invoke: Callable[[Any], Awaitable[Any]],
    source: str | Path | BinaryIO,
    *,
    name: str | None = None,
    on_progress: Progress | None = None,
    part_size: int = CHUNK,
    concurrency: int = 1,
) -> types.InputFile | types.InputFileBig:
    _validate_chunk_size(part_size)
    if (
        isinstance(concurrency, bool)
        or not isinstance(concurrency, int)
        or not 1 <= concurrency <= 16
    ):
        raise ValueError("upload concurrency must be between 1 and 16")
    owned = isinstance(source, (str, Path))
    stream: Any = await disk(open, source, "rb", _on_cancel=_close_upload) if owned else source
    try:
        if not stream.seekable():
            raise UnsupportedFeature("upload requires a seekable binary stream")
        start = await disk(stream.tell)
        await disk(stream.seek, 0, os.SEEK_END)
        size = await disk(stream.tell) - start
        await disk(stream.seek, start)
        count = part_count(size, part_size)
        filename = name or Path(str(getattr(stream, "name", "upload.bin"))).name
        if not filename or filename in {".", ".."} or any(c in filename for c in ("/", "\\", "\0")):
            raise ValueError("upload name must be a plain filename")
        file_id = secrets.randbits(63)
        checksum = hashlib.md5(usedforsecurity=False)
        done = 0
        pending: dict[asyncio.Task[Any], tuple[int, int]] = {}

        async def send(request: Any) -> Any:
            return await invoke(request)

        async def acknowledge() -> None:
            nonlocal done
            finished, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in sorted(finished, key=lambda item: pending[item][0]):
                _, length = pending.pop(task)
                if task.result() is not True:
                    raise FileTransferError("Telegram did not accept file part")
                done += length
                # Producer owns callbacks; they never run concurrently or count unaccepted bytes.
                await progress(on_progress, done, size)

        await progress(on_progress, 0, size)
        try:
            for index in range(count):
                if len(pending) >= concurrency:
                    await acknowledge()
                length = min(part_size, size - index * part_size)
                chunk = bytearray()
                while len(chunk) < length:
                    block = await disk(stream.read, length - len(chunk))
                    if not isinstance(block, bytes) or not 0 < len(block) <= length - len(chunk):
                        raise FileTransferError(
                            "upload source ended early or returned invalid binary data"
                        )
                    chunk.extend(block)
                data = bytes(chunk)
                if size > BIG_FILE:
                    request: Any = functions.upload.SaveBigFilePartRequest(
                        file_id=file_id, file_part=index, file_total_parts=count, bytes=data
                    )
                else:
                    checksum.update(data)
                    request = functions.upload.SaveFilePartRequest(
                        file_id=file_id, file_part=index, bytes=data
                    )
                task = asyncio.create_task(send(request), name=f"gramflux-upload-part-{index}")
                pending[task] = (index, length)
            while pending:
                await acknowledge()
        finally:
            # No transfer tasks may outlive success, failure, progress exceptions or cancellation.
            for task in pending:
                task.cancel()
            if pending:
                cleanup = asyncio.ensure_future(asyncio.gather(*pending, return_exceptions=True))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await _settle(cleanup)
                    raise
        if size > BIG_FILE:
            return types.InputFileBig(id=file_id, parts=count, name=filename)
        return types.InputFile(
            id=file_id, parts=count, name=filename, md5_checksum=checksum.hexdigest()
        )
    finally:
        if owned:
            await disk(stream.close)


def download_range(size: int, offset: int, length: int | None) -> tuple[int, int]:
    for name, value in (("size", size), ("offset", offset)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63:
            raise ValueError(f"download {name} must be a nonnegative signed 64-bit integer")
    if offset > size:
        raise ValueError("download offset exceeds file size")
    if length is None:
        length = size - offset
    if isinstance(length, bool) or not isinstance(length, int) or not 0 <= length <= size - offset:
        raise ValueError("download length exceeds the available range")
    return offset, offset + length


async def iter_download(
    invoke: Callable[[Any], Awaitable[Any]],
    location: Any,
    *,
    size: int,
    offset: int = 0,
    length: int | None = None,
    request_size: int = CHUNK,
) -> AsyncIterator[bytes]:
    """Yield exactly the requested byte range, on demand, with no prefetch tasks.

    Requests are aligned to request_size boundaries, satisfy Telegram's 1-MiB
    boundary rule, and may fetch extra bytes at the edges. CDN/migration and
    file-reference refresh remain explicit errors. No retry or resume is implied.
    """
    _validate_chunk_size(request_size, download=True)
    position, end = download_range(size, offset, length)
    while position < end:
        aligned = position // request_size * request_size
        result = await invoke(
            functions.upload.GetFileRequest(location=location, offset=aligned, limit=request_size)
        )
        if isinstance(result, types.upload.FileCdnRedirect):
            raise UnsupportedFeature("CDN download redirects are not implemented")
        block = getattr(result, "bytes", None)
        expected = min(request_size, size - aligned)
        if not isinstance(block, bytes) or len(block) != expected:
            raise FileTransferError("invalid or truncated download part")
        stop = min(aligned + len(block), end)
        yield block[position - aligned : stop - aligned]
        position = stop


async def download(
    invoke: Callable[[Any], Awaitable[Any]],
    location: Any,
    destination: str | Path | BinaryIO,
    *,
    size: int,
    on_progress: Progress | None = None,
    offset: int = 0,
    length: int | None = None,
    request_size: int = CHUNK,
) -> Path | None:
    start, end = download_range(size, offset, length)
    _validate_chunk_size(request_size, download=True)
    owned = isinstance(destination, (str, Path))
    path = Path(destination) if isinstance(destination, (str, Path)) else None
    temporary: str | None = None
    stream: Any
    if path is not None:
        # Acquire/open together in the worker so cancellation cannot orphan an fd/temp.
        stream, temporary = await disk(
            _create_download, str(path.parent), _on_cancel=_remove_download
        )
    else:
        stream = destination
    try:
        done = 0
        total = end - start
        await progress(on_progress, 0, total)
        async for block in iter_download(
            invoke, location, size=size, offset=start, length=total, request_size=request_size
        ):
            written_offset = 0
            while written_offset < len(block):
                written = await disk(stream.write, block[written_offset:])
                if (
                    isinstance(written, bool)
                    or not isinstance(written, int)
                    or not 0 < written <= len(block) - written_offset
                ):
                    raise FileTransferError("destination made no write progress")
                written_offset += written
            done += len(block)
            await progress(on_progress, done, total)
        if path is not None and temporary is not None:
            await disk(stream.flush)
            await disk(os.fsync, stream.fileno())
            await disk(stream.close)
            # Atomic no-overwrite publication on the same filesystem.
            await disk(os.link, temporary, path)
        return path
    finally:
        if owned:
            # A single joined worker completes both actions even under repeated cancellation.
            assert temporary is not None
            await disk(_remove_download, (stream, temporary))


def media_location(message: Any) -> tuple[Any, int]:
    """Resolve document/full photo metadata; never use a server-provided local path."""
    document = getattr(message, "document", None)
    photo = getattr(message, "photo", None)
    if document is not None:
        download_range(document.size, 0, None)
        return (
            types.InputDocumentFileLocation(
                id=document.id,
                access_hash=document.access_hash,
                file_reference=document.file_reference,
                thumb_size="",
            ),
            document.size,
        )
    if photo is not None:
        return photo_location(photo)
    raise UnsupportedFeature("message must contain a document or downloadable photo")


def photo_location(photo: Any) -> tuple[Any, int]:
    """Choose downloadable server photo metadata, shared by message/profile helpers."""
    choices = []
    for item in photo.sizes:
        if isinstance(item, types.PhotoSize):
            size = item.size
        elif isinstance(item, types.PhotoSizeProgressive) and item.sizes:
            size = max(item.sizes)
        else:
            continue
        download_range(size, 0, None)
        choices.append((size, item.type))
    if choices:
        size, kind = max(choices)
        return (
            types.InputPhotoFileLocation(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference,
                thumb_size=kind,
            ),
            size,
        )
    raise UnsupportedFeature("message must contain a document or downloadable photo")
