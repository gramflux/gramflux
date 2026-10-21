# Native update ordering and recovery

The engine follows Telegram's independent [message-box and envelope sequences](https://core.telegram.org/api/updates).
It does not equate a repeated envelope with repeated messages.

For each valid `updates`/`updatesCombined` envelope:

1. Process global/channel `pts` updates independently of `seq`.
2. Accept a message-box update only when `local_pts + pts_count == pts`.
   Ignore overlapping/already-applied ranges; recover when the sum is lower.
3. Apply remaining updates using `seq_start`, with zero as the unordered case.
   A combined envelope is checked against its start, not only its final `seq`.
4. Commit counters after the callback boundary; do not regress newer recovered state.

Short private/group messages preserve forwarding, bot attribution, reply/formatting,
notification flags and TTL fields when normalized to native Message objects.

Difference state is validated before delivering that page's messages. Invalid or
regressive counters fail explicitly. An unchanged intermediate global state or a
non-final channel page with unchanged pts fails with a no-progress TransportError.
This is a conservative fail-closed policy, not an attempt to repair unknown server
state. A maximum of 100 pages bounds each recovery. Self-recursive channel recovery
and nesting beyond eight active channels fail before another request; guards are
released on success, error and cancellation.

Completed pages remain committed when a later page is cancelled. An interrupted
page can be delivered again after recovery. Session persistence remains a clean-
shutdown snapshot, not a per-event durable journal; exactly-once delivery is not
promised. Secret-chat/qts and too-long resynchronization remain unsupported.

Tests use controlled native TL responses. Real account/channel recovery has not
been verified against Telegram. The suite covers seq replay carrying fresh pts,
overlapping ranges, seq_start ordering, malformed ranges, regressive snapshots,
non-progressing pages, recursive recovery and interrupted multi-page recovery.
