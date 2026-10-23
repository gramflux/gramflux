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
| [check_password](../reference/client/check_password.md) | Fetch fresh SRP parameters, compute the proof off-loop and finish two-step account authorization. | `await` |
| [is_authorized](../reference/client/is_authorized.md) | Ask Telegram whether this authorization key is attached to an authorized account. | `await` |
| [is_bot](../reference/client/is_bot.md) | Inspect the authorized server identity to determine whether it is a bot. | `await` |
| [log_out](../reference/client/log_out.md) | Explicitly revoke the current remote authorization, clear local key/cache metadata and disconnect. | `await` |
| [login](../reference/client/login.md) | Explicitly run bounded interactive user login, authorize a bot token, or return the already authorized user. | `await` |
| [request_login_code](../reference/client/request_login_code.md) | Request a Telegram login code and commit its phone/code-hash checkpoint before returning. | `await` |
| [sign_in](../reference/client/sign_in.md) | Submit a login code using an explicit or saved challenge and persist completed authorization. | `await` |
| [sign_in_bot](../reference/client/sign_in_bot.md) | Authorize a bot account once with its token and persist the resulting authorization. | `await` |

## Users and peers

| Method | Use it to | Call shape |
| --- | --- | --- |
| [get_chat](../reference/client/get_chat.md) | Fetch the current basic entity for a supported peer and update peer metadata. | `await` |
| [get_chat_full](../reference/client/get_chat_full.md) | Request full basic-group or channel/supergroup metadata using the appropriate endpoint. | `await` |
| [get_entity](../reference/client/get_entity.md) | Fetch an accessible full user/chat/channel from common references, including public username links. | `await` |
| [get_input_entity](../reference/client/get_input_entity.md) | Resolve an input peer suitable for requests without constructing TL objects manually. | `await` |
| [get_me](../reference/client/get_me.md) | Fetch the current authorized account identity. | `await` |
| [get_peer_id](../reference/client/get_peer_id.md) | Return a marked identity without confusing identity knowledge with access rights. | `await` |
| [get_profile_photos](../reference/client/get_profile_photos.md) | Collect visible user profile photos with bounded server paging. | `await` |
| [get_user](../reference/client/get_user.md) | Fetch a basic entity and require it to be a user. | `await` |
| [get_user_full](../reference/client/get_user_full.md) | Request the full Telegram user profile for a user peer. | `await` |
| [get_users](../reference/client/get_users.md) | Resolve multiple user references and fetch native user batches. | `await` |
| [resolve_peer](../reference/client/resolve_peer.md) | Resolve a supported peer representation into a native input peer without inventing access hashes. | `await` |

## Contacts

| Method | Use it to | Call shape |
| --- | --- | --- |
| [add_contact](../reference/client/add_contact.md) | Add a resolved user to contacts with explicit name and phone-sharing choices. | `await` |
| [block_user](../reference/client/block_user.md) | Block a resolved user through the contacts API. | `await` |
| [delete_contacts](../reference/client/delete_contacts.md) | Remove the selected user contacts from the account. | `await` |
| [get_contacts](../reference/client/get_contacts.md) | Fetch the current complete contacts response with a zero cache hash. | `await` |
| [unblock_user](../reference/client/unblock_user.md) | Remove a block on a resolved user. | `await` |

## Account

| Method | Use it to | Call shape |
| --- | --- | --- |
| [delete_profile_photos](../reference/client/delete_profile_photos.md) | Delete explicit native account photo references using their actual hashes. | `await` |
| [get_active_sessions](../reference/client/get_active_sessions.md) | List Telegram authorizations attached to the current account. | `await` |
| [get_drafts](../reference/client/get_drafts.md) | Fetch actual nonempty cloud drafts in one server snapshot. | `await` |
| [iter_drafts](../reference/client/iter_drafts.md) | Delay fetching the cloud-draft snapshot until iteration begins. | `async for` |
| [set_profile_photo](../reference/client/set_profile_photo.md) | Upload and set a still account profile photo. | `await` |
| [set_username](../reference/client/set_username.md) | Set or clear the current account ordinary username with local syntax validation. | `await` |
| [terminate_session](../reference/client/terminate_session.md) | Revoke the specific remote authorization identified by its hash. | `await` |
| [update_profile](../reference/client/update_profile.md) | Update only explicitly supplied name/biography fields for the current user. | `await` |

## Messages

| Method | Use it to | Call shape |
| --- | --- | --- |
| [copy_message](../reference/client/copy_message.md) | Copy accessible ordinary text or cached photo/document content without a forward header. | `await` |
| [delete_messages](../reference/client/delete_messages.md) | Delete validated IDs from an explicitly selected conversation. | `await` |
| [edit_message](../reference/client/edit_message.md) | Edit nonempty literal message text in a known peer. | `await` |
| [edit_message_caption](../reference/client/edit_message_caption.md) | Edit literal caption/text with explicit entities and optional keyboard markup. | `await` |
| [edit_message_media](../reference/client/edit_message_media.md) | Upload replacement photo/document media and optionally replace the literal caption. | `await` |
| [edit_message_reply_markup](../reference/client/edit_message_reply_markup.md) | Replace message keyboard markup without editing text. | `await` |
| [forward_messages](../reference/client/forward_messages.md) | Forward messages from an explicit source peer into a destination peer with independent secure random IDs. | `await` |
| [get_message](../reference/client/get_message.md) | Fetch one peer-scoped message while preserving get_messages list semantics. | `await` |
| [get_messages](../reference/client/get_messages.md) | Retrieve explicit IDs while preserving requested order and duplicate IDs. | `await` |
| [pin_message](../reference/client/pin_message.md) | Pin a message in the selected conversation. | `await` |
| [read_history](../reference/client/read_history.md) | Mark history as read using the user/group or channel endpoint. | `await` |
| [save_draft](../reference/client/save_draft.md) | Set or clear a literal draft in one conversation with optional reply context. | `await` |
| [send_message](../reference/client/send_message.md) | Send nonempty literal text, optionally with a reply, explicit entities and native keyboard markup. | `await` |
| [send_reaction](../reference/client/send_reaction.md) | Set, replace or remove the current account's reaction on a message. | `await` |
| [set_typing](../reference/client/set_typing.md) | Send a native typing or other SendMessageAction notification, optionally in a topic. | `await` |
| [unpin_message](../reference/client/unpin_message.md) | Unpin the selected message in its conversation. | `await` |

## Pagination

| Method | Use it to | Call shape |
| --- | --- | --- |
| [edit_folder](../reference/client/edit_folder.md) | Move explicit conversations between the main list and archive. | `await` |
| [get_chat_history_count](../reference/client/get_chat_history_count.md) | Request a minimal history page and read its actual server count. | `await` |
| [get_dialogs](../reference/client/get_dialogs.md) | Materialize a finite collection of dialogs using the lazy iterator. | `await` |
| [get_history](../reference/client/get_history.md) | Collect a finite newest-first message history. | `await` |
| [get_members](../reference/client/get_members.md) | Materialize a finite list of accessible participant records. | `await` |
| [iter_dialogs](../reference/client/iter_dialogs.md) | Create a lazy iterator over pinned dialogs followed by regular dialogs in one folder. | `async for` |
| [iter_history](../reference/client/iter_history.md) | Lazily traverse accessible messages newest first, starting before offset_id when supplied. | `async for` |
| [iter_members](../reference/client/iter_members.md) | Lazily enumerate accessible basic-group or channel/supergroup participants. | `async for` |
| [iter_messages](../reference/client/iter_messages.md) | Use the familiar message iterator name for the existing lazy history traversal. | `async for` |
| [iter_search](../reference/client/iter_search.md) | Lazily search one conversation through Telegram, optionally restricting the author. | `async for` |
| [search_messages](../reference/client/search_messages.md) | Collect a finite set of server-side search results in one peer. | `await` |
| [search_messages_count](../reference/client/search_messages_count.md) | Count a conversation search using Telegram search semantics. | `await` |

## Membership

| Method | Use it to | Call shape |
| --- | --- | --- |
| [approve_chat_join_request](../reference/client/approve_chat_join_request.md) | Approve or dismiss one pending join request without bulk admission. | `await` |
| [ban_chat_member](../reference/client/ban_chat_member.md) | Ban a peer from viewing a supergroup/channel until an explicit server timestamp. | `await` |
| [check_invite](../reference/client/check_invite.md) | Inspect an invite hash without calling the join endpoint. | `await` |
| [create_channel](../reference/client/create_channel.md) | Create a broadcast channel and return its uniquely identified server entity. | `await` |
| [create_chat_invite_link](../reference/client/create_chat_invite_link.md) | Create an invite using the existing export_invite_link implementation. | `await` |
| [create_group](../reference/client/create_group.md) | Resolve user references and create a basic group with explicit invitees. | `await` |
| [create_supergroup](../reference/client/create_supergroup.md) | Create a megagroup, optionally with forum topics enabled. | `await` |
| [delete_chat_photo](../reference/client/delete_chat_photo.md) | Remove a basic-group/channel photo through its appropriate endpoint. | `await` |
| [export_invite_link](../reference/client/export_invite_link.md) | Create/export a chat invite with explicit expiry, usage and approval choices. | `await` |
| [get_admin_log](../reference/client/get_admin_log.md) | Collect a finite supergroup/channel administration log. | `await` |
| [get_chat_invite_link](../reference/client/get_chat_invite_link.md) | Read the exported link available in full-chat metadata without creating one. | `await` |
| [get_chat_member](../reference/client/get_chat_member.md) | Retrieve one exposed member through channel lookup or basic-group participants. | `await` |
| [get_chat_members_count](../reference/client/get_chat_members_count.md) | Read an exposed channel/group participant count without guessing a hidden list size. | `await` |
| [get_participants](../reference/client/get_participants.md) | Collect visible members through the existing get_members implementation. | `await` |
| [import_invite](../reference/client/import_invite.md) | Attempt to join through a private invite hash. | `await` |
| [iter_admin_log](../reference/client/iter_admin_log.md) | Stream admin-log pages backwards with bounded overlap and cursor validation. | `async for` |
| [join_chat](../reference/client/join_chat.md) | Join a resolved public channel/supergroup through its channel endpoint. | `await` |
| [leave_chat](../reference/client/leave_chat.md) | Leave a basic group or a channel/supergroup using the corresponding endpoint. | `await` |
| [promote_chat_member](../reference/client/promote_chat_member.md) | Set explicit administrator grants and an optional rank for a channel member. | `await` |
| [restrict_chat_member](../reference/client/restrict_chat_member.md) | Apply explicit allowed-action settings to a supergroup/channel member. | `await` |
| [revoke_chat_invite_link](../reference/client/revoke_chat_invite_link.md) | Revoke a supplied real Telegram invite URL without removing current members. | `await` |
| [set_chat_description](../reference/client/set_chat_description.md) | Set or clear a chat about/description field. | `await` |
| [set_chat_permissions](../reference/client/set_chat_permissions.md) | Set default group member permissions using a positive high-level settings object. | `await` |
| [set_chat_photo](../reference/client/set_chat_photo.md) | Upload and set a basic-group/channel photo without manual TL construction. | `await` |
| [set_chat_title](../reference/client/set_chat_title.md) | Change a basic group or channel/supergroup title using the appropriate endpoint. | `await` |
| [unban_chat_member](../reference/client/unban_chat_member.md) | Clear a supergroup/channel member ban and restriction flags. | `await` |

## Raw API

| Method | Use it to | Call shape |
| --- | --- | --- |
| [invoke](../reference/client/invoke.md) | Execute a native GramFlux-generated TL function object through the shared request engine. | `await` |

## Files

| Method | Use it to | Call shape |
| --- | --- | --- |
| [download_file](../reference/client/download_file.md) | Stream an exact range to a new path or caller-owned binary output stream. | `await` |
| [download_media](../reference/client/download_media.md) | Resolve a supported message's media location and size, then stream an exact range. | `await` |
| [download_profile_photo](../reference/client/download_profile_photo.md) | Fetch visible full profile metadata and download the largest supported photo size. | `await` |
| [iter_download](../reference/client/iter_download.md) | Create a lazy iterator yielding exactly the requested byte range from a native remote location. | `async for` |
| [iter_download_media](../reference/client/iter_download_media.md) | Resolve supported document/photo metadata from a message and yield its requested byte range. | `async for` |
| [send_document](../reference/client/send_document.md) | Upload a source, then send the uploaded result as a document. | `await` |
| [send_file](../reference/client/send_file.md) | Send a local path/stream, uploaded handle or supported native media through the existing upload and send pipeline. | `await` |
| [send_photo](../reference/client/send_photo.md) | Upload a source, explicitly wrap it as photo media, then send it. | `await` |
| [upload_file](../reference/client/upload_file.md) | Read a local binary source in order and submit a bounded number of upload parts. | `await` |

## Bots

| Method | Use it to | Call shape |
| --- | --- | --- |
| [answer_callback_query](../reference/client/answer_callback_query.md) | Answer an incoming bot callback query with notification text, an alert, or a permitted URL. | `await` |
| [answer_inline_query](../reference/client/answer_inline_query.md) | Publish at most 50 native inline results with explicit caching and pagination choices. | `await` |
| [delete_bot_commands](../reference/client/delete_bot_commands.md) | Reset commands in one bot-command scope and language. | `await` |
| [edit_inline_message](../reference/client/edit_inline_message.md) | Edit the text/markup of an inline bot message by its native inline identifier. | `await` |
| [get_bot_commands](../reference/client/get_bot_commands.md) | Read the command list for a selected scope/language pair. | `await` |
| [get_callback_answer](../reference/client/get_callback_answer.md) | Invoke a message's supported callback payload and receive the bot answer. | `await` |
| [get_chat_menu_button](../reference/client/get_chat_menu_button.md) | Fetch the bot menu for a user or the default user scope. | `await` |
| [get_inline_bot_results](../reference/client/get_inline_bot_results.md) | Resolve a bot and destination and retrieve server inline results. | `await` |
| [get_inline_results](../reference/client/get_inline_results.md) | Request inline results from a bot for a query and target peer context. | `await` |
| [send_game](../reference/client/send_game.md) | Send a registered bot game using an actual bot reference and short name. | `await` |
| [send_inline_bot_result](../reference/client/send_inline_bot_result.md) | Send a real inline result using its server query identity and result ID. | `await` |
| [set_bot_commands](../reference/client/set_bot_commands.md) | Replace a bot command list for a selected native scope and language. | `await` |
| [set_chat_menu_button](../reference/client/set_chat_menu_button.md) | Set a default/user bot menu to a Web App, commands menu or Telegram default. | `await` |
| [start_bot](../reference/client/start_bot.md) | Start a bot with an explicit target peer and start payload. | `await` |

## Media messages

| Method | Use it to | Call shape |
| --- | --- | --- |
| [send_animation](../reference/client/send_animation.md) | Upload/send GIF or MP4 animation using the animated-document attribute. | `await` |
| [send_audio](../reference/client/send_audio.md) | Upload/send MPEG audio with duration and optional track metadata. | `await` |
| [send_cached_media](../reference/client/send_cached_media.md) | Reuse server photo/document metadata without reupload or foreign file-ID decoding. | `await` |
| [send_contact](../reference/client/send_contact.md) | Send a contact card built from literal phone/name/vCard fields. | `await` |
| [send_dice](../reference/client/send_dice.md) | Send a Telegram-generated dice/game media object. | `await` |
| [send_location](../reference/client/send_location.md) | Send a static geographic point with validated finite coordinates. | `await` |
| [send_media](../reference/client/send_media.md) | Upload/send a photo or document with explicit caption, entities, keyboard and transfer controls. | `await` |
| [send_media_group](../reference/client/send_media_group.md) | Upload and send a real photo/document album with per-item captions and response correlation. | `await` |
| [send_poll](../reference/client/send_poll.md) | Send a text poll or single-answer quiz through the real layer-225 poll media schema. | `await` |
| [send_sticker](../reference/client/send_sticker.md) | Upload/send sticker-format content with a sticker document attribute. | `await` |
| [send_venue](../reference/client/send_venue.md) | Build and send a geographic venue with title, address and optional provider metadata. | `await` |
| [send_video](../reference/client/send_video.md) | Upload/send MP4 video with explicit duration, dimensions and streaming metadata. | `await` |
| [send_video_note](../reference/client/send_video_note.md) | Upload/send a round MP4 video note with explicit square dimensions. | `await` |
| [send_voice](../reference/client/send_voice.md) | Upload/send an OGG voice note with explicit duration and optional waveform bytes. | `await` |

## Event subscriptions

| Method | Use it to | Call shape |
| --- | --- | --- |
| [off_event](../reference/client/off_event.md) | Remove all registrations associated with the same callback object. | `register` |
| [off_message](../reference/client/off_message.md) | Remove all registrations associated with the same callback object. | `register` |
| [on](../reference/client/on.md) | Register an async callback for instances of the selected supported high-level event type. | `register` |
| [on_callback_query](../reference/client/on_callback_query.md) | Register an async callback for bot callback queries; inline identifiers are distinct from ordinary message IDs. | `register` |
| [on_chat_action](../reference/client/on_chat_action.md) | Register an async callback for native service messages describing supported chat actions. | `register` |
| [on_deleted_messages](../reference/client/on_deleted_messages.md) | Register an async callback for message deletions; global non-channel deletions may not identify a chat. | `register` |
| [on_edited_message](../reference/client/on_edited_message.md) | Register an async callback for edited messages only. | `register` |
| [on_inline_query](../reference/client/on_inline_query.md) | Register an async callback for bot inline queries carrying query text and pagination offset. | `register` |
| [on_message](../reference/client/on_message.md) | Register an async callback for new messages; edited=True selects edits. | `register` |
| [on_raw_update](../reference/client/on_raw_update.md) | Register an async callback for accepted native Update objects, without fabricated wrappers for difference.new_messages. | `register` |
| [on_read_history](../reference/client/on_read_history.md) | Register an async callback for read-history changes with max_id and inbox/outbox direction. | `register` |
| [on_user_status](../reference/client/on_user_status.md) | Register an async callback for user status changes, subject to Telegram privacy and visibility. | `register` |
