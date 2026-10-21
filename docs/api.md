# Public API reference

Import `Client`, `Config`, `LoginChallenge`, `MessageEvent`, `Session`, `LoginPrompts`, `Dialog`, `ChatMember`, `filters` from `gramflux`.
Signatures and annotations are maintained in source; `python -m pydoc gramflux.client`
shows the complete reference without a documentation build dependency.

| API | Return / semantics |
| --- | --- |
| Client(session=None, *, api_id, api_hash, config=None, on_handler_error=None) | Client; explicit Session or async Storage; bare path opens saved authorization; `None` uses memory |
| async connect() / disconnect() | None; explicit lifecycle, disconnect joins cleanup even on cancellation |
| connected | bool; native connection status, not authorization |
| async is_authorized() | bool; server authorization check |
| Session.open(name, *, require_authorized=True) | Existing GramFlux file only; authorization checked at connect |
| Session.create(name) | New named file only; refuses replacement |
| Session.temporary() | Process-local memory only |
| async login(*, phone=None, bot_token=None, max_attempts=3, prompts=None) | User; explicit interactive login or reuse authorized user; bounded input retries |
| async request_login_code(phone) | LoginChallenge; explicit code request |
| async sign_in(challenge, code) | native User; may raise PasswordRequired |
| async check_password(password) | native User; SRP computation off-loop |
| async sign_in_bot(token) | native User; refuses replacement of authorized session |
| async get_me() | native User; missing auth raises AuthenticationError |
| async resolve_peer(peer, *, refresh=False) | InputPeer; known numeric IDs, usernames, explicit input peers, or self |
| async get_chat(peer) / get_user(peer="me") | raw User/Chat/Channel or User; permissions apply |
| async get_user_full(peer="me") / get_chat_full(peer) | raw users.UserFull / messages.ChatFull |
| async get_contacts() | list[raw User] |
| async block_user(peer) / unblock_user(peer) | bool from Telegram |
| async send_message(peer, text, *, reply_to=None, silent=False, link_preview=True) | native Message; literal text |
| iter_dialogs(*, limit=None, folder_id=0, page_size=100) | AsyncIterator[Dialog]; pins first, selected folder |
| async get_dialogs(*, limit=100, folder_id=0) | list[Dialog]; finite limit required |
| iter_history(peer, *, limit=None, offset_id=0, page_size=100) | AsyncIterator[Message or MessageService]; newest first, exclusive offset |
| async get_history(peer, *, limit=100, offset_id=0) | list[Message or MessageService] |
| iter_search(peer, query, *, limit=None, sender=None, page_size=100) | AsyncIterator[Message or MessageService] |
| async search_messages(peer, query, *, limit=100, sender=None) | list[Message or MessageService] |
| async get_messages(peer, ids) | list[Message or MessageService or None]; preserves input order/duplicates, checks chat |
| async edit_message(peer, message_id, text, *, link_preview=True) | raw Updates; literal text |
| async delete_messages(peer, ids, *, revoke=False) | list[raw messages.AffectedMessages]; preflight chat scope; channels require explicit revoke=True |
| async forward_messages(peer, from_peer, ids, *, silent=False, drop_author=False) | list[raw Updates], one per batch |
| async read_history(peer, *, max_id=0) | raw AffectedMessages for non-channel, bool for channel |
| async pin_message(peer, message_id, *, silent=True) / unpin_message(peer, message_id) | raw Updates |
| iter_members(peer, *, limit=None, query="", page_size=100) | AsyncIterator[ChatMember]; server permissions/visibility apply |
| async get_members(peer, *, limit=100, query="") | list[ChatMember] |
| async join_chat(peer) / leave_chat(peer) | raw Updates; join supports channels/supergroups; leave also basic groups |
| async import_invite(invite_hash) | raw Updates; hash only, explicit membership action |
| async log_out() | None; revokes current authorization then clears saved key/cache; client cannot reconnect |
| async invoke(request) | native result; use gramflux.raw.functions/types and LAYER |
| on_message(predicate=filters.all_messages, *, edited=False, priority=0) | async callback decorator; lower priority runs first, stable registration order for ties |
| off_message(callback) | int; number of registrations removed |
| async run_until_disconnected() | None; wait without disconnecting on waiter cancellation |
| async upload_file(source, *, name=None, on_progress=None, part_size=524288, concurrency=1) | native InputFile or InputFileBig |
| async send_file(peer, file, *, caption="", reply_to=None, as_document=False, mime_type=None) | native Message; uploaded handle or raw InputMedia |
| async send_document(peer, source, *, caption="", name=None, mime_type=None, on_progress=None, reply_to=None, part_size=524288, concurrency=1) | native Message; streamed upload then document send |
| async send_photo(peer, source, *, caption="", on_progress=None, reply_to=None, part_size=524288, concurrency=1) | native Message; streamed upload then explicit photo media |
| iter_download(location, *, size, offset=0, length=None, request_size=524288) | AsyncIterator[bytes]; exact range, aligned requests, no prefetch |
| iter_download_media(message, *, offset=0, length=None, request_size=524288) | AsyncIterator[bytes]; document/photo metadata |
| async download_file(location, destination, *, size, on_progress=None, offset=0, length=None, request_size=524288) | Path for path target, None for caller stream |
| async download_media(message, destination, *, on_progress=None, offset=0, length=None, request_size=524288) | Path for path target, None for caller stream; supported document/photo |

`Config` is a frozen slots dataclass; defaults: request_timeout=30.0 seconds,
max_concurrent_requests=32, event_queue_size=256, reconnect_attempts=3,
peer_cache_size=2048 (1..4096), transport="intermediate". All client calls must use one event loop.

Independent offline API: `gramflux.tl.Codec(registry=None, max_bytes=16777216,
max_vector=100000, max_depth=64)`; `encode(value, type="Object") -> bytes`,
`decode(data, type="Object") -> object`. Generated classes are in
`gramflux.tl.generated.objects`, named with capitalized namespace prefixes and Request
suffix for methods. Primitive/list fields are annotated; optional fields default to
None, optional `true` fields to False. Flags are calculated, not constructor arguments.
Fields sharing a bit must be present together. Repr omits field values.

`gramflux.tl.parser.parse(text)` returns validated Definition descriptors. Specialized
bare MTProto records are recognized but not generated as normal boxed objects.
Framing is used by the native connection. `probe_datacenter` remains the earlier
unencrypted probe. `gramflux.tools.native_probe.probe_native` performs authenticated
RSA/DH plus encrypted ping/pong without a user login; its result distinguishes
successful exchanges, an anonymous API rejection and uncertain remote key cleanup.

`LoginPrompts` accepts async `phone(prompt)`, `code(prompt)` and `password(prompt)`
callbacks returning strings, and a synchronous `notify(message)` callback. Terminal
defaults use input/getpass in worker threads. Callbacks may raise EOFError or
CancelledError; neither is retried. `LoginAttemptsExceeded` reports `stage`, `attempts`
and the safe `last_error_name`. Low-level sign_in/check_password remain single-attempt.

`Dialog` is a frozen slots record with `id`, `name`, `entity`, `message`,
`unread_count`, `pinned`, `folder_id`, `raw`. `ChatMember` has `id`, `user` (possibly
None), `role`, `raw`. Roles summarize constructor categories; inspect `raw` for
individual permissions/restrictions. Sensitive entity/message/raw fields are omitted
from these records' repr. Underlying Telegram types can expose content in their repr.

`MessageEvent` includes the client, chat type, and async `reply`, `edit`, `delete`,
`download` helpers. Detached test events cannot execute operations. See
[events](guides/events.md) for dispatch and [core operations](guides/core-operations.md)
for cursor, visibility, identifier, batching and safety semantics. Raw results are
GramFlux-generated dataclasses with value-free repr. There are no inherited competitor
convenience methods. Use Client and MessageEvent operations. Raw constructor arguments
are keyword-only; dates are Unix seconds. Primitive fields are typed, but generated
sum/generic types and many raw returns still use TLObject/Any rather than precise
result unions. This typing limitation is separate from verified constructor coverage.

See [the actual Client inventory](api-surface.json) and [bot/event methods](guides/bots-and-events.md) for the expanded typed surface. Raw TL request counts are separate from high-level operation coverage.

See [all typed asynchronous raw functions](guides/async-api.md) through `client.api`.
