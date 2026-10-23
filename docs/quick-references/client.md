---
title: Client methods at a glance
description: Find every public Client method by task and follow its full parameter and behavior reference.
---

# Client methods at a glance

Find the operation by purpose, then open its individual page for the exact signature,
all parameters, return values, constraints and examples. These are GramFlux methods;
similarly named methods from another client can have different behavior.

[Construction and credentials](../reference/client/constructor.md) ·
[Parameter conventions](../guides/parameters.md) ·
[Complete Client reference](../reference/client.md)

## Reading the result column

`await` means a coroutine; `async for` means a stream factory; `register` means
a synchronous subscription factory. Creating a stream or registering a callback is
not itself an executed Telegram RPC. Raw data constructor coverage is a separate count.

## Lifecycle

| Method | Use it to | Call shape |
| --- | --- | --- |
| [connect](../reference/client/connect.md) | Open storage, restore native session metadata, establish the MTProto connection and start update dispatch. Does not prompt for account login. | `await` |
| [disconnect](../reference/client/disconnect.md) | Cancel and join outstanding requests and callbacks, stop native update production, close the transport and save the session snapshot. | `await` |
| [run_until_disconnected](../reference/client/run_until_disconnected.md) | Wait for backend disconnection while allowing other asyncio tasks to run. | `await` |

## Authentication

| Method | Use it to | Call shape |
| --- | --- | --- |
| [is_authorized](../reference/client/is_authorized.md) | Ask Telegram whether this authorization key is attached to an authorized account. | `await` |
| [login](../reference/client/login.md) | Explicitly run bounded interactive user login, authorize a bot token, or return the already authorized user. | `await` |
| [request_login_code](../reference/client/request_login_code.md) | Request a Telegram login code and commit its phone/code-hash checkpoint before returning. | `await` |
| [sign_in](../reference/client/sign_in.md) | Submit a login code using an explicit or saved challenge and persist completed authorization. | `await` |
| [check_password](../reference/client/check_password.md) | Fetch fresh SRP parameters, compute the proof off-loop and finish two-step account authorization. | `await` |
| [sign_in_bot](../reference/client/sign_in_bot.md) | Authorize a bot account once with its token and persist the resulting authorization. | `await` |
| [log_out](../reference/client/log_out.md) | Explicitly revoke the current remote authorization, clear local key/cache metadata and disconnect. | `await` |

## Users and peers

| Method | Use it to | Call shape |
| --- | --- | --- |
| [get_me](../reference/client/get_me.md) | Fetch the current authorized account identity. | `await` |
| [resolve_peer](../reference/client/resolve_peer.md) | Resolve a supported peer representation into a native input peer without inventing access hashes. | `await` |
| [get_chat](../reference/client/get_chat.md) | Fetch the current basic entity for a supported peer and update peer metadata. | `await` |
| [get_user](../reference/client/get_user.md) | Fetch a basic entity and require it to be a user. | `await` |
| [get_user_full](../reference/client/get_user_full.md) | Request the full Telegram user profile for a user peer. | `await` |
| [get_chat_full](../reference/client/get_chat_full.md) | Request full basic-group or channel/supergroup metadata using the appropriate endpoint. | `await` |

## Messages

| Method | Use it to | Call shape |
| --- | --- | --- |
| [send_message](../reference/client/send_message.md) | Send nonempty literal text, optionally with a reply, explicit entities and native keyboard markup. | `await` |
| [edit_message](../reference/client/edit_message.md) | Edit nonempty literal message text in a known peer. | `await` |
| [delete_messages](../reference/client/delete_messages.md) | Delete validated IDs from an explicitly selected conversation. | `await` |
| [forward_messages](../reference/client/forward_messages.md) | Forward messages from an explicit source peer into a destination peer with independent secure random IDs. | `await` |
| [read_history](../reference/client/read_history.md) | Mark history as read using the user/group or channel endpoint. | `await` |
| [pin_message](../reference/client/pin_message.md) | Pin a message in the selected conversation. | `await` |
| [unpin_message](../reference/client/unpin_message.md) | Unpin the selected message in its conversation. | `await` |
| [get_messages](../reference/client/get_messages.md) | Retrieve explicit IDs while preserving requested order and duplicate IDs. | `await` |
| [set_typing](../reference/client/set_typing.md) | Send a native typing or other SendMessageAction notification, optionally in a topic. | `await` |
| [send_reaction](../reference/client/send_reaction.md) | Set, replace or remove the current account's reaction on a message. | `await` |
| [save_draft](../reference/client/save_draft.md) | Set or clear a literal draft in one conversation with optional reply context. | `await` |

## Pagination

| Method | Use it to | Call shape |
| --- | --- | --- |
| [iter_dialogs](../reference/client/iter_dialogs.md) | Create a lazy iterator over pinned dialogs followed by regular dialogs in one folder. | `async for` |
| [get_dialogs](../reference/client/get_dialogs.md) | Materialize a finite collection of dialogs using the lazy iterator. | `await` |
| [iter_history](../reference/client/iter_history.md) | Lazily traverse accessible messages newest first, starting before offset_id when supplied. | `async for` |
| [get_history](../reference/client/get_history.md) | Collect a finite newest-first message history. | `await` |
| [iter_search](../reference/client/iter_search.md) | Lazily search one conversation through Telegram, optionally restricting the author. | `async for` |
| [search_messages](../reference/client/search_messages.md) | Collect a finite set of server-side search results in one peer. | `await` |
| [iter_members](../reference/client/iter_members.md) | Lazily enumerate accessible basic-group or channel/supergroup participants. | `async for` |
| [get_members](../reference/client/get_members.md) | Materialize a finite list of accessible participant records. | `await` |

## Media messages

| Method | Use it to | Call shape |
| --- | --- | --- |
| [send_contact](../reference/client/send_contact.md) | Send a contact card built from literal phone/name/vCard fields. | `await` |
| [send_location](../reference/client/send_location.md) | Send a static geographic point with validated finite coordinates. | `await` |
| [send_dice](../reference/client/send_dice.md) | Send a Telegram-generated dice/game media object. | `await` |

## Files

| Method | Use it to | Call shape |
| --- | --- | --- |
| [upload_file](../reference/client/upload_file.md) | Read a local binary source in order and submit a bounded number of upload parts. | `await` |
| [send_file](../reference/client/send_file.md) | Send an uploaded handle or native supported InputMedia using the selected peer and caption. | `await` |
| [send_document](../reference/client/send_document.md) | Upload a source, then send the uploaded result as a document. | `await` |
| [send_photo](../reference/client/send_photo.md) | Upload a source, explicitly wrap it as photo media, then send it. | `await` |
| [iter_download](../reference/client/iter_download.md) | Create a lazy iterator yielding exactly the requested byte range from a native remote location. | `async for` |
| [iter_download_media](../reference/client/iter_download_media.md) | Resolve supported document/photo metadata from a message and yield its requested byte range. | `async for` |
| [download_file](../reference/client/download_file.md) | Stream an exact range to a new path or caller-owned binary output stream. | `await` |
| [download_media](../reference/client/download_media.md) | Resolve a supported message's media location and size, then stream an exact range. | `await` |

## Membership

| Method | Use it to | Call shape |
| --- | --- | --- |
| [join_chat](../reference/client/join_chat.md) | Join a resolved public channel/supergroup through its channel endpoint. | `await` |
| [leave_chat](../reference/client/leave_chat.md) | Leave a basic group or a channel/supergroup using the corresponding endpoint. | `await` |
| [import_invite](../reference/client/import_invite.md) | Attempt to join through a private invite hash. | `await` |
| [check_invite](../reference/client/check_invite.md) | Inspect an invite hash without calling the join endpoint. | `await` |
| [export_invite_link](../reference/client/export_invite_link.md) | Create/export a chat invite with explicit expiry, usage and approval choices. | `await` |
| [set_chat_title](../reference/client/set_chat_title.md) | Change a basic group or channel/supergroup title using the appropriate endpoint. | `await` |
| [set_chat_description](../reference/client/set_chat_description.md) | Set or clear a chat about/description field. | `await` |

## Contacts

| Method | Use it to | Call shape |
| --- | --- | --- |
| [get_contacts](../reference/client/get_contacts.md) | Fetch the current complete contacts response with a zero cache hash. | `await` |
| [block_user](../reference/client/block_user.md) | Block a resolved user through the contacts API. | `await` |
| [unblock_user](../reference/client/unblock_user.md) | Remove a block on a resolved user. | `await` |
| [add_contact](../reference/client/add_contact.md) | Add a resolved user to contacts with explicit name and phone-sharing choices. | `await` |
| [delete_contacts](../reference/client/delete_contacts.md) | Remove the selected user contacts from the account. | `await` |

## Account

| Method | Use it to | Call shape |
| --- | --- | --- |
| [update_profile](../reference/client/update_profile.md) | Update only explicitly supplied name/biography fields for the current user. | `await` |
| [get_active_sessions](../reference/client/get_active_sessions.md) | List Telegram authorizations attached to the current account. | `await` |
| [terminate_session](../reference/client/terminate_session.md) | Revoke the specific remote authorization identified by its hash. | `await` |

## Bots

| Method | Use it to | Call shape |
| --- | --- | --- |
| [answer_callback_query](../reference/client/answer_callback_query.md) | Answer an incoming bot callback query with notification text, an alert, or a permitted URL. | `await` |
| [answer_inline_query](../reference/client/answer_inline_query.md) | Publish at most 50 native inline results with explicit caching and pagination choices. | `await` |
| [edit_inline_message](../reference/client/edit_inline_message.md) | Edit the text/markup of an inline bot message by its native inline identifier. | `await` |
| [get_inline_results](../reference/client/get_inline_results.md) | Request inline results from a bot for a query and target peer context. | `await` |
| [get_callback_answer](../reference/client/get_callback_answer.md) | Invoke a message's supported callback payload and receive the bot answer. | `await` |
| [set_bot_commands](../reference/client/set_bot_commands.md) | Replace a bot command list for a selected native scope and language. | `await` |
| [get_bot_commands](../reference/client/get_bot_commands.md) | Read the command list for a selected scope/language pair. | `await` |
| [start_bot](../reference/client/start_bot.md) | Start a bot with an explicit target peer and start payload. | `await` |

## Event subscriptions

| Method | Use it to | Call shape |
| --- | --- | --- |
| [on_message](../reference/client/on_message.md) | Register an async callback for new messages; edited=True selects edits. | `register` |
| [on_edited_message](../reference/client/on_edited_message.md) | Register an async callback for edited messages only. | `register` |
| [on_raw_update](../reference/client/on_raw_update.md) | Register an async callback for accepted native Update objects, without fabricated wrappers for difference.new_messages. | `register` |
| [on_deleted_messages](../reference/client/on_deleted_messages.md) | Register an async callback for message deletions; global non-channel deletions may not identify a chat. | `register` |
| [on_read_history](../reference/client/on_read_history.md) | Register an async callback for read-history changes with max_id and inbox/outbox direction. | `register` |
| [on_user_status](../reference/client/on_user_status.md) | Register an async callback for user status changes, subject to Telegram privacy and visibility. | `register` |
| [on_chat_action](../reference/client/on_chat_action.md) | Register an async callback for native service messages describing supported chat actions. | `register` |
| [on_callback_query](../reference/client/on_callback_query.md) | Register an async callback for bot callback queries; inline identifiers are distinct from ordinary message IDs. | `register` |
| [on_inline_query](../reference/client/on_inline_query.md) | Register an async callback for bot inline queries carrying query text and pagination offset. | `register` |
| [on](../reference/client/on.md) | Register an async callback for instances of the selected supported high-level event type. | `register` |
| [off_event](../reference/client/off_event.md) | Remove all registrations associated with the same callback object. | `call` |
| [off_message](../reference/client/off_message.md) | Remove all registrations associated with the same callback object. | `call` |

## Raw API

| Method | Use it to | Call shape |
| --- | --- | --- |
| [invoke](../reference/client/invoke.md) | Execute a native GramFlux-generated TL function object through the shared request engine. | `await` |

## Properties and API levels

| Property | Meaning |
| --- | --- |
| `connected` | Current connection indicator; not a completed authorization check |
| `login_stage` | Saved local code/password stage, or None; not a server expiry guarantee |
| `login_challenge` | Saved phone/code-hash challenge after connect; sensitive authentication context |
| `api` | Typed raw namespaces; native inputs and method-specific workflows remain your responsibility |

Use `await client.is_authorized()` to check account authorization. Consult
[authentication](../guides/authentication.md), [entities](../concepts/entities.md) and
[raw API usage](../guides/async-api.md) before assuming property access performs an RPC.
