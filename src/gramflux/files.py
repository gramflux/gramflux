"""Streaming small/large file upload and bounded sequential download."""

import asyncio
import hashlib
import inspect
import os
import secrets
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, BinaryIO

from telethon.tl import functions, types

from .errors import FileTransferError, UnsupportedFeature

Progress = Callable[[int, int], Awaitable[None] | None]
CHUNK = 512 * 1024
BIG_FILE = 10 * 1024 * 1024
MAX_PARTS = 4000


def part_count(size: int, chunk_size: int = CHUNK) -> int:
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("file size must be a positive integer")
    if (
        chunk_size <= 0
        or chunk_size > CHUNK
        or chunk_size % 1024
        or (chunk_size & (chunk_size - 1))
    ):
        raise ValueError("chunk size must be a power of two between 1 and 512 KiB")
    count = (size + chunk_size - 1) // chunk_size
    if count > MAX_PARTS:
        raise UnsupportedFeature("upload exceeds conservative 4000-part limit")
    return count


async def progress(callback: Progress | None, done: int, total: int) -> None:
    if callback is not None:
        result = callback(done, total)
        if inspect.isawaitable(result):
            await result


async def disk(function: Callable[..., Any], *args: Any) -> Any:
    """Join cancelled disk work before releasing its file handle."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


async def upload(
    invoke: Callable[[Any], Awaitable[Any]],
    source: str | Path | BinaryIO,
    *,
    name: str | None = None,
    on_progress: Progress | None = None,
) -> Any:
    owned = isinstance(source, (str, Path))
    stream: Any = await disk(open, source, "rb") if owned else source
    try:
        if not stream.seekable():
            raise UnsupportedFeature("upload requires a seekable binary stream")
        start = await disk(stream.tell)
        await disk(stream.seek, 0, os.SEEK_END)
        size = await disk(stream.tell) - start
        await disk(stream.seek, start)
        count = part_count(size)
        filename = name or Path(str(getattr(stream, "name", "upload.bin"))).name
        if not filename or filename in {".", ".."} or any(c in filename for c in ("/", "\\", "\0")):
            raise ValueError("upload name must be a plain filename")
        file_id = secrets.randbits(63)
        checksum = hashlib.md5(usedforsecurity=False)
        done = 0
        await progress(on_progress, 0, size)
        for index in range(count):
            length = min(CHUNK, size - done)
            chunk = bytearray()
            while len(chunk) < length:
                block = await disk(stream.read, length - len(chunk))
                if not isinstance(block, bytes) or not block:
                    raise FileTransferError("upload source ended early or is not binary")
                chunk.extend(block)
            data = bytes(chunk)
            if size > BIG_FILE:
                request = functions.upload.SaveBigFilePartRequest(file_id, index, count, data)
            else:
                checksum.update(data)
                request = functions.upload.SaveFilePartRequest(file_id, index, data)
            if await invoke(request) is not True:
                raise FileTransferError("Telegram did not accept file part")
            done += len(data)
            await progress(on_progress, done, size)
        if size > BIG_FILE:
            return types.InputFileBig(file_id, count, filename)
        return types.InputFile(file_id, count, filename, checksum.hexdigest())
    finally:
        if owned:
            await disk(stream.close)


async def download(
    invoke: Callable[[Any], Awaitable[Any]],
    location: Any,
    destination: str | Path | BinaryIO,
    *,
    size: int,
    on_progress: Progress | None = None,
) -> Path | None:
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError("download size must be nonnegative")
    owned = isinstance(destination, (str, Path))
    path = Path(destination) if isinstance(destination, (str, Path)) else None
    temporary: str | None = None
    stream: Any
    if path is not None:
        # No server-provided path. Existing files are never overwritten.
        fd, temporary = await disk(tempfile.mkstemp, ".part", ".gramflux-", str(path.parent))
        stream = os.fdopen(fd, "wb")
    else:
        stream = destination
    try:
        done = 0
        await progress(on_progress, 0, size)
        while done < size:
            result = await invoke(functions.upload.GetFileRequest(location, done, CHUNK))
            if isinstance(result, types.upload.FileCdnRedirect):
                raise UnsupportedFeature("CDN download redirects are not implemented")
            block = result.bytes
            if not isinstance(block, bytes) or not 0 < len(block) <= min(CHUNK, size - done):
                raise FileTransferError("invalid or truncated download part")
            # Next request offsets must remain aligned; a short block is only final.
            if len(block) < CHUNK and done + len(block) != size:
                raise FileTransferError("short nonfinal download part")
            offset = 0
            while offset < len(block):
                written = await disk(stream.write, block[offset:])
                if not isinstance(written, int) or not 0 < written <= len(block) - offset:
                    raise FileTransferError("destination made no write progress")
                offset += written
            done += len(block)
            await progress(on_progress, done, size)
        if path is not None and temporary is not None:
            await disk(stream.flush)
            await disk(os.fsync, stream.fileno())
            await disk(stream.close)
            # Atomic no-overwrite publication on the same filesystem.
            await disk(os.link, temporary, path)
        return path
    finally:
        if owned:
            if not stream.closed:
                await disk(stream.close)
            if temporary is not None:
                await disk(os.unlink, temporary)
