---
title: Accounts, administration and bots
---

# Accounts, administration and bots

Direct methods reuse the same authorized Client. Creating optional domain views does
not create another connection. Local session storage is distinct from remote account
authorizations returned by `get_active_sessions`/removed by `terminate_session`.

## Authentication and identity

`connect` never logs in implicitly. `login`, `request_login_code`, `sign_in`,
`check_password`, `sign_in_bot`, `is_authorized`, `get_me` and `log_out` keep their
existing behavior and resumable checkpoints. `is_bot` reads the actual authorized
identity; `is_connected` is an additive property matching `connected`.

## Permissions are positive settings

```python
from gramflux import AdminPrivileges, ChatPermissions

await client.restrict_chat_member(
    group_peer, user_peer, ChatPermissions(send_media=False), until_date=0
)
await client.promote_chat_member(
    group_peer, user_peer, AdminPrivileges(delete_messages=True), rank="Moderator"
)
```

ChatPermissions fields send_messages, send_media, send_polls and embed_links default
True. change_info, invite_users, pin_messages and manage_topics default False. All are
booleans describing allowed actions, translated to Telegram forbidden-right flags.
`set_chat_permissions` applies defaults; individual restriction changes use
`restrict_chat_member`. These channel/supergroup operations do not upgrade basic groups.

AdminPrivileges fields all default False: change_info, post_messages, edit_messages,
delete_messages, ban_users, invite_users, pin_messages, add_admins, anonymous,
manage_call, manage_topics, post_stories, edit_stories and delete_stories.
An all-false value demotes. Telegram enforces caller grants, ownership and bot rules.

`ban_chat_member` forbids viewing; `unban_chat_member` clears individual restrictions
without rejoining. until_date is a Unix timestamp, with 0 meaning permanent. It is not
a duration. Server rules interpret short/very distant dates as permanent.

## Chat and account lifecycle

`create_group` resolves 1–200 users and returns the actual Chat. Some invitees may be
omitted because of privacy restrictions. `create_supergroup` and `create_channel`
return actual Channel entities; ambiguous creation results fail rather than guess.
Use set_chat_title/description/photo and delete_chat_photo with sufficient permissions.

Invite creation/revocation and join-request approval are explicit writes.
`get_chat_invite_link` only reads exposed full metadata and returns None when absent.
It never creates a link as a side effect. Joining public peers remains distinct from
accepting invite hashes. `get_chat_members_count` rejects unavailable counts rather
than estimating from a partial visible list.

`set_username` accepts ordinary names or an empty string to clear. Profile photo
upload/history/deletion use native server references; integer photo IDs are insufficient
for deletion. Account photos and channel photos use different server pathways.

## Dialogs and administration history

`edit_folder(peers, folder_id=1)` archives up to 100 peers; folder_id=0 unarchives.
Custom dialog filters are a different feature. `get_drafts` returns Draft(peer, draft)
records with real peer and DraftMessage. `iter_drafts` delays the initial RPC, then
iterates the complete server snapshot; it is not server-paged.

`get_admin_log` collects a finite list; `iter_admin_log` pages backwards lazily with
an exclusive event cursor, bounded deduplication and stalled-cursor detection. It
returns native ChannelAdminLogEvent records, subject to Telegram access permissions.

## Bots

Existing callbacks and inline answers remain available, including event.answer().
`get_inline_bot_results` and `send_inline_bot_result` use real query and result IDs.
Bot command deletion respects explicit scope/language. Menu helpers support Telegram's
default, commands and HTTPS Web App buttons. No helper grants bot eligibility.

`UpdateResult` in signatures is the native Updates sum: Updates, UpdatesCombined,
UpdateShort, UpdateShortMessage, UpdateShortChatMessage, UpdateShortSentMessage or
UpdatesTooLong. It is not a promise that an edit returns a Message object.

Every method's [reference](../reference/client.md) includes its exact signature,
parameters and result. RPC errors, cancellation and uncertain writes propagate through
the original runtime; these wrappers do not add hidden retries.
