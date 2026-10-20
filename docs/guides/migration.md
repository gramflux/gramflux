# Migration guide

These are source-level mappings, not drop-in or session compatibility promises.
Do not reuse a competitor database. Authorize a new GramFlux session and keep the
original intact. Pyrofork was not separately audited; only familiar operation patterns
are mapped, with no interoperability claim.

| Operation | Telethon | Pyrogram/Hydrogram/Pyrofork style | GramFlux |
| --- | --- | --- | --- |
| Construct | TelegramClient(name, id, hash) | Client(name, api_id=..., api_hash=...) | Client(name, api_id=..., api_hash=...) |
| Authorization | start/sign_in | start or context often prompts | explicit request_login_code/sign_in/check_password or sign_in_bot |
| Identity | get_me() | get_me() | get_me() |
| Text | send_message(peer, text) | send_message(chat_id, text) | send_message(peer, text), literal text |
| Raw | await client(functions.X(...)) | invoke(raw.functions.X(...)) | invoke(gramflux.raw.functions.XRequest(...)) |
| New events | on(events.NewMessage(...)) | on_message(filters...) | on_message(gramflux.filters...) |
| Edited events | MessageEdited builder | on_edited_message | on_message(predicate, edited=True) |
| Upload | upload_file / send_file | save_file / send_document | upload_file then send_file |
| Download | download_media | download_media | download_media(message, explicit_path) |
| Wait | run_until_disconnected | idle | await client.run_until_disconnected() |
| Flood limit | FloodWaitError, .seconds | FloodWait, often .value | gramflux.errors.FloodWait, .seconds |

Important changes: the context manager never prompts; handlers should be registered
before connect; callbacks are sequential; the default queue is bounded locally;
exceptions are redacted and fail without automatic flood sleeping; timeouts include
request admission; session files use a new format. Raw types/results in this alpha
are Telethon objects because the runtime depends on Telethon. GramFlux's independent
TL objects are for offline tooling and serialization, not wire invocation.

No equivalents yet for conversations, arbitrary custom event builders, QR/passkey auth,
secret chats, foreign session conversion, plugins, parallel/resumable transfers, CDN,
proxy configuration or full chat/entity helper families. Use supported raw requests
where applicable; a generated method existing does not prove live usability.
