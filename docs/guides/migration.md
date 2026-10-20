# Migration guide

These are source-level mappings, not drop-in or session compatibility promises.
Do not reuse a competitor database. Authorize a new GramFlux session and keep the
original intact. Pyrofork was not separately audited; only familiar operation patterns
are mapped, with no interoperability claim.

| Operation | Telethon | Pyrogram/Hydrogram/Pyrofork style | GramFlux |
| --- | --- | --- | --- |
| Construct | TelegramClient(name, id, hash) | Client(name, api_id=..., api_hash=...) | Client(name, api_id=..., api_hash=...) |
| Authorization | start/sign_in | start or context often prompts | explicit login() with bounded prompts, or single-attempt request_login_code/sign_in/check_password/sign_in_bot |
| Identity | get_me() | get_me() | get_me() |
| Text | send_message(peer, text) | send_message(chat_id, text) | send_message(peer, text), literal text |
| Raw | await client(functions.X(...)) | invoke(raw.functions.X(...)) | invoke(gramflux.raw.functions.XRequest(...)) |
| New events | on(events.NewMessage(...)) | on_message(filters...) | on_message(gramflux.filters...) |
| Edited events | MessageEdited builder | on_edited_message | on_message(predicate, edited=True) |
| Dialogs/history | iter_dialogs / iter_messages | get_dialogs / get_chat_history | iter_dialogs / iter_history; finite get_* helpers |
| Search | iter_messages(search=...) | search_messages | iter_search / search_messages |
| Edit/delete | edit_message / delete_messages | edit_message_text / delete_messages | edit_message / delete_messages; scoped preflight; explicit channel revoke |
| Members | iter_participants | get_chat_members | iter_members / get_members; server visibility limits |
| Entities | get_entity / get_input_entity | get_chat / get_users | get_chat / get_user / resolve_peer |
| Upload | upload_file / send_file | save_file / send_document | upload_file then send_file, or send_document/send_photo; explicit bounded concurrency |
| Download | download_media | download_media | download_media(message, explicit_path) |
| Wait | run_until_disconnected | idle | await client.run_until_disconnected() |
| Flood limit | FloodWaitError, .seconds | FloodWait, often .value | gramflux.errors.FloodWait, .seconds |

Important changes: the context manager never prompts; handlers should be registered
before connect; callbacks are sequential; the default queue is bounded locally;
exceptions are redacted and fail without automatic flood sleeping; timeouts include
request admission; session files use a new format. Raw types/results in 0.3 are GramFlux-generated dataclasses. The network engine is
independent. Use keyword-only constructors; raw dates are integer Unix seconds. An
existing foreign request/object is not accepted by invoke. This intentionally breaks
the previous 0.2 alpha's dependency-type contract. Generated objects and runtime now
share layer 225; no implicit competitor-client fallback exists.

No equivalents yet for conversations, arbitrary custom event builders, QR/passkey auth,
secret chats, foreign session conversion, plugins, parallel downloads/resumable transfers, CDN,
proxy configuration, granular administrative helpers or full chat/entity helper families. Use supported raw requests
where applicable; a generated method existing does not prove live usability.

Since 0.1.0a2, choose Session.open(name), Session.create(name) or Session.temporary().
A bare path now means open-only and checks authorization; it no longer auto-creates.
For a partially completed login use Session.open(name, require_authorized=False)
and explicitly call login(). Session database format remains version 1.

Since 0.2.0a1, numeric user/channel IDs need a known access hash from dialogs,
contacts, updates or username resolution. The bounded minimal peer cache persists
with normal session snapshots; full entity objects do not. Restored usernames are
re-resolved, since usernames may be reassigned. This is not competitor-session import.
