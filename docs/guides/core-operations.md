# Core operations

These services use GramFlux's pinned layer-225 types and native MTProto runtime.
The native engine has no competing Telegram client dependency. The operations below
have deterministic tests; personal-account end-to-end interoperability remains pending.
Raw constructors are keyword-only and raw dates are Unix seconds.

## Peers and persistent access hashes

Use a username, `"me"`, a marked numeric ID, or an explicit raw InputPeer:

```python
peer = await client.resolve_peer("@some_username")
user = await client.get_user(peer)
chat = await client.get_chat(peer)
full_profile = await client.get_user_full(peer)
```

Marked IDs follow Telegram Python conventions: user IDs are positive, basic groups
negative, and channel/supergroup ID N is `-(1000000000000 + N)`. This marking is a
library convention, not the wire's ID encoding. Unknown user/channel numeric IDs
require an access hash: resolve a username, load contacts/dialogs, or supply an explicit
InputPeer. The library never manufactures a zero access hash to make an ID appear valid.
Basic groups and InputPeerSelf do not require one. Context-dependent input peers such
as InputPeerUserFromMessage remain available through `gramflux.raw.types`.

RPC results and incoming event entity tables update an account-local LRU (default
2048 records, Config.peer_cache_size between 1 and 4096). Min entities do not overwrite
full access hashes. The session snapshot stores only IDs, access hashes, primary
usernames and the self flag; not message text, titles, full names or phone numbers.
Numeric lookup works after a clean restart without downloading all dialogs again.

Primary username lookups have a 60-second monotonic lifetime; explicit
`resolve_peer(name, refresh=True)` forces a lookup and invalidates the old binding even
if lookup fails. Persisted names are not trusted after restart because ownership can
change. Additional username aliases are resolved by Telegram rather than guessed or
permanently bound. For identity-sensitive operations, resolve freshly and pass that
input peer. A cache is not a permanent assertion of username ownership.

Session format remains version 1 with optional additive peer metadata; old snapshots
load with an empty peer cache. Older clients can discard this cache on saving. New
entries persist on auth changes and clean shutdown, not in a crash-consistent journal.

## Dialogs, histories and search

```python
async for dialog in client.iter_dialogs(limit=200):
    print(dialog.id, dialog.name, dialog.unread_count)

async for message in client.iter_history("me", limit=500):
    print(message.id)  # message.message contains private text; print deliberately

found = await client.search_messages("me", "meeting", limit=50)
selected = await client.get_messages("me", [123, 124, 123])
```

Async iterators fetch on demand, keep one decoded page plus bounded overlap tracking,
and default to no total result limit. `page_size` is 1–100 (members: 1–200). List-returning
helpers default to 100 and require a finite nonnegative limit. Zero limits perform no
network resolution. Breaking iteration does not prefetch additional pages. Request
cancellation follows the ordinary per-RPC deadline and cancellation rules.

Dialogs fetch pins separately, then ordinary dialogs excluding pins. This preserves
pins even with page_size=1. `folder_id=0` selects the main folder; `folder_id=1` selects
the archive. Dialog exposes id, name, entity, message, unread_count, pinned, folder_id
and raw. Cursor progression uses top-message date, ID and input peer; message IDs alone
cannot paginate across different channels safely. Missing/stalled cursor data raises
PaginationError instead of looping forever or fabricating a page.

Histories and searches return newest first and continue through short sliced pages.
History supports exclusive offset_id for older messages; search supports optional
sender. ID retrieval preserves order and duplicates, with None for missing/deleted or
other-chat messages. Requests for explicit IDs are chunked into at most 100 IDs per RPC
and accept up to 10,000 input IDs. These helpers do not provide a snapshot transaction
while other users change dialog order, membership or message history. Overlap suppression
is bounded and is not durable exactly-once delivery.

Message/User/Chat payloads remain the native TL types, including raw service messages.
Use GramFlux client methods and MessageEvent helpers for GramFlux execution policy;
raw native objects expose data; execute operations through Client or MessageEvent.
Raw invocation always returns the actual raw result, not synthetic success objects.

## Sending and managing messages

```python
sent = await client.send_message("me", "Literal **text**", silent=True, link_preview=False)
await client.send_message("me", "A reply", reply_to=sent.id)
await client.edit_message("me", sent.id, "Edited literal text")
await client.pin_message("me", sent.id)
await client.unpin_message("me", sent.id)
await client.forward_messages("me", source_peer, [source_message_id])
await client.read_history("me", max_id=sent.id)
```

Text/captions have no implicit Markdown parsing. edit_message/pin/unpin return actual
Telegram Updates, forward_messages returns Updates per batch, and read_history returns
the protocol's affected-state result or bool. These are not all Message objects.
Forwarding assigns independent secure random IDs to each message, fixes source and
destination explicitly, and never creates a replacement request to retry ambiguity.

Deletion is intentionally explicit:

```python
await client.delete_messages("me", [message_id], revoke=False)
await client.delete_messages(channel_peer, [channel_message_id], revoke=True)
```

For private/basic-group global IDs, the helper fetches and validates **all** requested
IDs against the target before issuing any delete. Missing or other-chat IDs fail without
sending a deletion. This also means already-deleted unknown IDs are rejected rather
than assumed to belong to the supplied peer. Channel/supergroup deletion is peer-scoped
by its own endpoint, always affects everyone, and requires explicit revoke=True.
Default revoke=False therefore cannot silently become global deletion in a channel.

Batches are not an atomic transaction: if a later RPC fails, earlier deletes/forwards
may already have succeeded. No broad retries, flood bypass or rollback are promised.
A timeout can leave a completed remote action; do not blindly repeat sends/forwards.

## Groups, users, contacts and membership

```python
contacts = await client.get_contacts()
full_group = await client.get_chat_full(group_peer)
async for member in client.iter_members(group_peer, limit=100, query="alice"):
    print(member.id, member.role)
await client.join_chat(public_channel_peer)
await client.leave_chat(group_peer)
```

ChatMember exposes id, user (possibly None), role and raw participant. Basic groups
use full participants; channels/supergroups use offset-based paginated requests.
Hidden/forbidden lists and server privacy/admin limits are not bypassed. A forbidden
basic-group list fails explicitly instead of pretending to be complete.

join_chat resolves a public channel/supergroup peer. import_invite(invite_hash) is a
separate explicit action for private invite hashes; URLs are not silently joined during
peer resolution. leave_chat handles basic groups and channel peers, not deleting private
user dialogs. block_user/unblock_user validate user peers and surface actual server
results. Bots cannot call every user-only API; permissions and rate limits are server
rules, not features to evade.

## Logout

`await client.log_out()` explicitly revokes the remote authorization, clears saved
key/peer/update metadata and disconnects. It requires a new Client afterwards and is
not called automatically for temporary sessions. Use it from the main task, not a
handler. Failure before a confirmed server response preserves local state. A network
timeout still has an ambiguous remote outcome. SQLite backups/journal/free pages and
Python memory are not guaranteed cryptographically erased by updating a snapshot.
