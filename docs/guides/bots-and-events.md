# Bot operations and typed events

Register handlers before connecting. All handlers use the same bounded, ordered
async dispatcher, including raw updates. Handler priority is stable; failures are
reported without private exception text, then subsequent handlers continue.
StopPropagation stops handlers for that event, not other derived events.

```python
from gramflux import buttons, events, filters


@client.on_message(filters.command("start"))
async def start(event: events.MessageEvent) -> None:
    await client.send_message(
        event.chat_id,
        "Choose an action",
        reply_markup=buttons.inline([[buttons.callback("Confirm", "confirm")]]),
    )


@client.on_callback_query(filters.data("confirm"))
async def confirm(event: events.CallbackQueryEvent) -> None:
    await event.answer("Confirmed")


@client.on_inline_query()
async def inline(event: events.InlineQueryEvent) -> None:
    await event.answer([buttons.article("help", "Help", "Literal answer text")], private=True)
```

Inline mode must be configured for the bot. Native operations follow Telegram's
[inline query](https://core.telegram.org/api/bots/inline) and
[button](https://core.telegram.org/api/bots/buttons) flows; no HTTP Bot API client is used.
Callback data limits apply to UTF-8 bytes. Builders return normal native TL objects,
which remain available for advanced parameters through client.invoke.

| Subscription | Payload |
| --- | --- |
| on_message | MessageEvent for new messages |
| on_edited_message | MessageEvent with edited=True |
| on_deleted_messages | DeletedMessagesEvent: message_ids, optional chat_id |
| on_read_history | ReadHistoryEvent: chat_id, max_id, outbox |
| on_user_status | UserStatusEvent: sender_id, native status, online |
| on_chat_action | ChatActionEvent: service message, action, user_ids, chat_id |
| on_callback_query | CallbackQueryEvent: query_id, sender_id, data, normal/inline message identifiers |
| on_inline_query | InlineQueryEvent: query_id, sender_id, query, offset |
| on_raw_update | RawUpdateEvent containing the actual accepted native Update |

`client.on(events.CallbackQueryEvent, predicate)` is the generic typed route;
`off_event(callback)` removes subscriptions. New/edit message subscriptions retain
old on_message(..., edited=True) behavior. Error callbacks now accept the Event
union rather than assuming every event has a message. Payload fields are omitted
from event reprs; do not explicitly log them in production.

Raw updates are emitted after update acceptance checks, before the corresponding
message event. Recovered difference.new_messages contains Messages, not Updates:
message and chat-action events are emitted, but raw Update wrappers are not invented.
Cancellation before dispatch completion leaves that update's counter uncommitted.
Read-state snapshots with pts_count=0 can repeat; handlers should be idempotent.
No exactly-once guarantee is made. qts/secret-chat synchronization remains unsupported.

Global non-channel deletions do not contain a peer; chat_id is None rather than a
guess. Inline callback queries have inline_message_id and no normal chat/message ID.
Use edit_inline_message for those IDs. Status updates preserve online/offline/
recently/last-week/last-month variants as native status objects.

chat/sender filters work when the event has those fields; data matches callback
bytes exactly. Text/media/chat-type/direction filters remain message-oriented and
fail closed on incompatible event kinds. Inline query text is event.query, not
message text. Raw events expose update fields directly.

## New high-level operations

| Area | Client methods |
| --- | --- |
| Callbacks and inline bots | answer_callback_query, answer_inline_query, edit_inline_message, get_inline_results, get_callback_answer |
| Bot setup | set_bot_commands, get_bot_commands, start_bot |
| Messaging | set_typing, send_reaction, save_draft |
| Chat settings/invites | export_invite_link, check_invite, set_chat_title, set_chat_description |
| Contacts/profile/sessions | add_contact, delete_contacts, update_profile, get_active_sessions, terminate_session |
| Media messages | send_contact, send_location, send_dice |

send_message also accepts native reply_markup and entities. Formatting is literal
unless explicit native MessageEntity values are supplied; entity offsets use TL's
UTF-16 conventions. An empty reaction list or None removes reactions; an empty draft
string clears the draft. Bot command lists can be emptied. Profile changes distinguish
None (unchanged) from an empty optional field (clear). Chat title changes route basic
groups and channels to the appropriate official method. Telegram permissions and
server errors apply; mutations are never blindly retried.

The complete executable [bot example](../../examples/bot_events.py) uses these APIs.
The [surface inventory](../api-surface.json) is generated from the actual Client and
checked in CI. It separates lifecycle/subscription/iterator methods from generated
raw requests. It is a surface report, not live-account feature certification.
The new operations and event paths have controlled serialization/dispatch tests;
account-level bot behavior is not yet verified in this environment.
