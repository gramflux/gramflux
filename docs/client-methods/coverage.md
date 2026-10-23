---
title: Coverage and compatibility
---

# Coverage and compatibility

The baseline at a08bf60 had 82 public Client methods. This change adds 57, totaling
139; these counts include lifecycle/registration/resource methods, not just Telegram
operations. Raw coverage stays 783 methods at layer 225 and is a separate metric.
No declaration count proves end-to-end Telegram interoperability.

## Newly implemented direct methods

| Method | Exact contract |
| --- | --- |
| `approve_chat_join_request` | [Parameters, returns, errors and example](../reference/client/approve_chat_join_request.md) |
| `ban_chat_member` | [Parameters, returns, errors and example](../reference/client/ban_chat_member.md) |
| `copy_message` | [Parameters, returns, errors and example](../reference/client/copy_message.md) |
| `create_channel` | [Parameters, returns, errors and example](../reference/client/create_channel.md) |
| `create_chat_invite_link` | [Parameters, returns, errors and example](../reference/client/create_chat_invite_link.md) |
| `create_group` | [Parameters, returns, errors and example](../reference/client/create_group.md) |
| `create_supergroup` | [Parameters, returns, errors and example](../reference/client/create_supergroup.md) |
| `delete_bot_commands` | [Parameters, returns, errors and example](../reference/client/delete_bot_commands.md) |
| `delete_chat_photo` | [Parameters, returns, errors and example](../reference/client/delete_chat_photo.md) |
| `delete_profile_photos` | [Parameters, returns, errors and example](../reference/client/delete_profile_photos.md) |
| `download_profile_photo` | [Parameters, returns, errors and example](../reference/client/download_profile_photo.md) |
| `edit_folder` | [Parameters, returns, errors and example](../reference/client/edit_folder.md) |
| `edit_message_caption` | [Parameters, returns, errors and example](../reference/client/edit_message_caption.md) |
| `edit_message_media` | [Parameters, returns, errors and example](../reference/client/edit_message_media.md) |
| `edit_message_reply_markup` | [Parameters, returns, errors and example](../reference/client/edit_message_reply_markup.md) |
| `get_admin_log` | [Parameters, returns, errors and example](../reference/client/get_admin_log.md) |
| `get_chat_history_count` | [Parameters, returns, errors and example](../reference/client/get_chat_history_count.md) |
| `get_chat_invite_link` | [Parameters, returns, errors and example](../reference/client/get_chat_invite_link.md) |
| `get_chat_member` | [Parameters, returns, errors and example](../reference/client/get_chat_member.md) |
| `get_chat_members_count` | [Parameters, returns, errors and example](../reference/client/get_chat_members_count.md) |
| `get_chat_menu_button` | [Parameters, returns, errors and example](../reference/client/get_chat_menu_button.md) |
| `get_drafts` | [Parameters, returns, errors and example](../reference/client/get_drafts.md) |
| `get_entity` | [Parameters, returns, errors and example](../reference/client/get_entity.md) |
| `get_inline_bot_results` | [Parameters, returns, errors and example](../reference/client/get_inline_bot_results.md) |
| `get_input_entity` | [Parameters, returns, errors and example](../reference/client/get_input_entity.md) |
| `get_message` | [Parameters, returns, errors and example](../reference/client/get_message.md) |
| `get_participants` | [Parameters, returns, errors and example](../reference/client/get_participants.md) |
| `get_peer_id` | [Parameters, returns, errors and example](../reference/client/get_peer_id.md) |
| `get_profile_photos` | [Parameters, returns, errors and example](../reference/client/get_profile_photos.md) |
| `get_users` | [Parameters, returns, errors and example](../reference/client/get_users.md) |
| `is_bot` | [Parameters, returns, errors and example](../reference/client/is_bot.md) |
| `iter_admin_log` | [Parameters, returns, errors and example](../reference/client/iter_admin_log.md) |
| `iter_drafts` | [Parameters, returns, errors and example](../reference/client/iter_drafts.md) |
| `iter_messages` | [Parameters, returns, errors and example](../reference/client/iter_messages.md) |
| `promote_chat_member` | [Parameters, returns, errors and example](../reference/client/promote_chat_member.md) |
| `restrict_chat_member` | [Parameters, returns, errors and example](../reference/client/restrict_chat_member.md) |
| `revoke_chat_invite_link` | [Parameters, returns, errors and example](../reference/client/revoke_chat_invite_link.md) |
| `search_messages_count` | [Parameters, returns, errors and example](../reference/client/search_messages_count.md) |
| `send_animation` | [Parameters, returns, errors and example](../reference/client/send_animation.md) |
| `send_audio` | [Parameters, returns, errors and example](../reference/client/send_audio.md) |
| `send_cached_media` | [Parameters, returns, errors and example](../reference/client/send_cached_media.md) |
| `send_game` | [Parameters, returns, errors and example](../reference/client/send_game.md) |
| `send_inline_bot_result` | [Parameters, returns, errors and example](../reference/client/send_inline_bot_result.md) |
| `send_media` | [Parameters, returns, errors and example](../reference/client/send_media.md) |
| `send_media_group` | [Parameters, returns, errors and example](../reference/client/send_media_group.md) |
| `send_poll` | [Parameters, returns, errors and example](../reference/client/send_poll.md) |
| `send_sticker` | [Parameters, returns, errors and example](../reference/client/send_sticker.md) |
| `send_venue` | [Parameters, returns, errors and example](../reference/client/send_venue.md) |
| `send_video` | [Parameters, returns, errors and example](../reference/client/send_video.md) |
| `send_video_note` | [Parameters, returns, errors and example](../reference/client/send_video_note.md) |
| `send_voice` | [Parameters, returns, errors and example](../reference/client/send_voice.md) |
| `set_chat_menu_button` | [Parameters, returns, errors and example](../reference/client/set_chat_menu_button.md) |
| `set_chat_permissions` | [Parameters, returns, errors and example](../reference/client/set_chat_permissions.md) |
| `set_chat_photo` | [Parameters, returns, errors and example](../reference/client/set_chat_photo.md) |
| `set_profile_photo` | [Parameters, returns, errors and example](../reference/client/set_profile_photo.md) |
| `set_username` | [Parameters, returns, errors and example](../reference/client/set_username.md) |
| `unban_chat_member` | [Parameters, returns, errors and example](../reference/client/unban_chat_member.md) |

## Existing capabilities retained

All 82 previous methods retain their runtime signatures/defaults. This includes direct
message send/edit/delete/forward, ID lookup, history/search/dialog iteration, peer lookup,
contact management/blocking, joining/leaving, titles/descriptions/invites, remote sessions,
raw invocation, callbacks/inline answers, bot commands and file transfers.
`send_file` additionally accepts paths/streams; previously supported inputs keep their
behavior. The [machine-readable inventory](../api-surface.json) and committed
research/high-level-inventory.json distinguish old/new names and exact signatures.

## Evaluated but deferred

| Capability | Current alternative / reason |
| --- | --- |
| parse_mode and implicit text parsing | Literal text and explicit entities; a parser requires its own UTF-16/escaping contract. |
| stop_transmission | Cancel the specific asyncio transfer task; a global stop risks unrelated transfers. |
| Portable session strings | Existing SQLite/memory sessions; no validated portable encrypted export/import format. |
| get_chat_members aliases | get_members/get_participants/get_chat_member/count cover supported operations without synonym proliferation. |
| delete_dialog | Leaving membership and deleting history differ destructively; no combined policy is guessed. |
| Global search | Per-chat search works; cross-peer offset/rate/DC pagination needs separate implementation. |
| Advanced 2FA settings | Existing password login works; changing settings needs SRP/email confirmation recovery coverage. |
| Channel/group statistics | Dedicated statistics DC and asynchronous graph resolution need tested routing support. |
| Mixed/video/audio albums | Current tested album contract is homogeneous photo or document only. |
| Arbitrary media copying | Text/photo/document supported; protected, polls, games and service messages are not rewritten. |
| CDN/file-DC authorization and resume | Existing explicit limitations retained; no hidden proxy or resume claims. |
| Custom dialog filters | Main/archive moves implemented; custom filter lifecycle/order semantics are separate. |
| Profile video, sticker packs, advanced polls | Still-photo/profile and basic sticker/poll sending are implemented; advanced lifecycle not claimed. |

These choices follow real runtime boundaries, not a claim of parity with
[Telethon](https://docs.telethon.dev/en/stable/quick-references/client-reference.html)
or [Hydrogram](https://docs.hydrogram.org/en/latest/api/methods/index.html).
Their public documentation informed scope; implementation is original and shares
GramFlux's independent native engine. No competitor dependency was introduced.

## Verification boundary

Controlled fixtures encode actual TL requests and verify returned server-shaped data,
correlation, invalid inputs and error propagation. They do not establish real-account
eligibility or successful live operations. See the repository verification report for
executed commands and totals. Crypto, session formats and connection policy are unchanged.
