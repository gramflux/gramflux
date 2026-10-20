# Public API reference

Import `Client`, `Config`, `LoginChallenge`, `MessageEvent`, `filters` from `gramflux`.
Signatures and annotations are maintained in source; `python -m pydoc gramflux.client`
shows the complete reference without a documentation build dependency.

| API | Return / semantics |
| --- | --- |
| Client(session=None, *, api_id, api_hash, config=None, on_handler_error=None) | Client; path or async Storage; `None` uses memory |
| async connect() / disconnect() | None; explicit lifecycle, disconnect joins cleanup even on cancellation |
| connected | bool; local/backend connection status, not authorization |
| async is_authorized() | bool; server authorization check |
| async request_login_code(phone) | LoginChallenge; explicit code request |
| async sign_in(challenge, code) | backend User; may raise PasswordRequired |
| async check_password(password) | backend User; SRP computation off-loop |
| async sign_in_bot(token) | backend User; refuses replacement of authorized session |
| async get_me() | backend User; missing auth raises AuthenticationError |
| async send_message(peer, text) | backend Message; literal text |
| async invoke(request) | raw backend result; use gramflux.raw.functions/types and LAYER |
| on_message(predicate=filters.all_messages, *, edited=False) | async callback decorator, registration order |
| async run_until_disconnected() | None; wait without disconnecting on waiter cancellation |
| async upload_file(source, *, name=None, on_progress=None) | backend InputFile or InputFileBig |
| async send_file(peer, file, *, caption="") | backend Message |
| async download_file(location, destination, *, size, on_progress=None) | Path for path target, None for caller stream |
| async download_media(message, destination, *, on_progress=None) | Path; supported document/photo |

`Config` is a frozen slots dataclass; defaults: request_timeout=30.0 seconds,
max_concurrent_requests=32, event_queue_size=256, reconnect_attempts=3,
transport="intermediate". All client calls must use one event loop.

Independent offline API: `gramflux.tl.Codec(registry=None, max_bytes=16777216,
max_vector=100000, max_depth=64)`; `encode(value, type="Object") -> bytes`,
`decode(data, type="Object") -> object`. Generated classes are in
`gramflux.tl.generated.objects`, named with capitalized namespace prefixes and Request
suffix for methods. Primitive/list fields are annotated; optional fields default to
None, optional `true` fields to False. Flags are calculated, not constructor arguments.
Fields sharing a bit must be present together. Repr omits field values.

`gramflux.tl.parser.parse(text)` returns validated Definition descriptors. Specialized
bare MTProto records are recognized but not generated as normal boxed objects.
`Framing` and `probe_datacenter` are independent experimental protocol utilities.
The native probe does not establish an authenticated channel or create an auth key.
