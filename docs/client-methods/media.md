---
title: Media, albums and file transfers
---

# Media, albums and file transfers

`Source` in method signatures means str, pathlib.Path, BinaryIO, InputFile or
InputFileBig. Native media references use separate explicit cached-media methods.

## Upload is distinct from send

```python
uploaded = await client.upload_file("report.pdf", concurrency=2)
sent = await client.send_file("me", uploaded, as_document=True)
photo = await client.send_file("me", "photo.jpg", caption="Photo")
```

`send_file` now accepts paths and supported binary streams in addition to all previous
uploaded/native inputs. Local JPG/JPEG/PNG sources infer photo mode unless as_document
or MIME is explicit. Previously accepted uploaded handles retain document behavior.
Its existing signature/defaults remain compatible, with additional typed overloads.

Use `send_media` for a photo/document with caption entities, markup, silent delivery,
progress, chunk size and concurrency. Its default is photo; as_document=True selects
document mode, where MIME may be explicit or inferred from the uploaded filename.
Neither helper fetches an HTTP source URL automatically.

```python
await client.send_media("me", "photo.jpg", caption="Photo", silent=True)
await client.send_video("me", "clip.mp4", duration=3.5, width=640, height=360)
await client.send_audio("me", "track.mp3", duration=120, title="Track")
await client.send_voice("me", "voice.ogg", duration=8)
await client.send_video_note("me", "note.mp4", duration=3, length=240)
await client.send_animation("me", "loop.gif")
await client.send_sticker("me", "sticker.webp", emoji="🙂")
```

The application supplies real duration and dimensions; there is no media probe or
transcoder. Video/round video use MP4, audio uses MPEG, voice uses OGG. Animation accepts
GIF or explicit MP4 MIME; sticker accepts WebP, TGS or WebM MIME. Telegram validates
encoded content and server limits. A filename extension does not convert a file.

## Albums and reusable media

```python
from gramflux import AlbumItem

messages = await client.send_media_group(
    "me",
    [
        AlbumItem("one.jpg", caption="First"),
        AlbumItem("two.jpg", caption="Second"),
    ],
)
await client.send_cached_media("me", messages[0], caption="Again")
```

`AlbumItem(source, caption="", as_document=False, entities=None)` is a frozen settings
record. All 2–10 items must be photos or all documents. Each upload is materialized
using uploadMedia before sendMultiMedia; actual response random-ID correlations recover
requested order. Mixed/video/audio album workflows are not exposed. Progress resets
per uploaded item. Uploaded server files are not rolled back after a failed send.

Cached media requires real Photo/Document/Message metadata with hashes/file references.
Cross-library encoded file IDs are not decoded, and expired references are not refreshed
automatically. Protected Message inputs fail explicitly.

## Download and cancellation

`download_media`, `download_file` and lazy `iter_download` retain existing destinations,
part size, concurrency, progress and byte-range contracts. `download_profile_photo`
selects the largest supported visible photo and uses the same downloader. Missing
photo returns None without creating output; caller-owned streams remain open.

The default transfer part size remains 524288 bytes and concurrency remains 1. Each
progress callback receives completed and total bytes under the existing awaited callback
contract. Cancel the transfer task to stop it; no client-global stop_transmission is
added that might terminate unrelated work. CDN, missing file-DC authorization and
resumability limitations remain explicit. See [file transport contracts](../guides/files.md).

Other real content helpers include `send_contact`, `send_location`, `send_venue`,
`send_dice`, `send_poll` and `send_game`. Poll supports 2–10 distinct options and a
single correct zero-based quiz index; it does not expose every advanced poll flag.
Each helper's [reference](../reference/client.md) lists its exact supported options.
