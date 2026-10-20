# Changelog

## 0.3.0a1 — unreleased

- Reset full-TCP framing counters on reopen, bound connection/preamble waits and close started senders on setup failure.
- Keep rejected/uncertain API initialization uncached without replaying the failed request.
- Preserve update-batch entities once and attach only relevant peer metadata to each event; add a reproducible event-emission benchmark.

- Replace the competing-client backend with an independent MTProto implementation; no Telethon runtime or fallback.
- Native RSA_PAD/DH key establishment, AES-IGE envelopes, SRP, bounded concurrent requests, response correlation, acknowledgments and salt/clock correction.
- Native global/channel update recovery and bounded event admission; generated raw requests share the pinned layer 225 codec.
- Verify anonymous key establishment and encrypted ping against Telegram over full, intermediate and abridged TCP. Account authorization and media remain unverified against Telegram.
- Breaking: raw constructors use keyword arguments and native TL objects; raw timestamps use Unix seconds.
- Independent cryptographic audit, authenticated interoperability and transport performance comparisons remain release blockers.

## 0.2.0a2 — unreleased

- Bounded concurrent upload parts (1–16, default 1), configurable protocol-valid
  part sizes, source-order checksums and serialized accepted-byte progress.
- Lazy raw/media byte streams and exact download ranges with aligned requests;
  path and caller-stream destinations share the same validation and read pipeline.
- Upload cancellation/failures join all outstanding parts. Cancelled disk acquisitions
  close/unlink resources even when cancellation is repeated while the worker runs.
- Photo download selection uses the largest supported size, tolerating empty
  progressive-size lists; no guessed paths or synthetic responses.
- Fix a flaky deadline/shutdown test by separating the cases and synchronizing startup
  with an Event instead of relying on a 10-ms sleep inside a 50-ms deadline.
- Add property/race/boundary tests and a reproducible synthetic-latency transfer benchmark.
- No live Telegram transfer, CDN, cross-DC recovery or resumability claim.

## 0.2.0a1 — unreleased

- Native high-level raw-API services for dialogs, histories/search, ID lookup, message
  mutations, contacts, membership, join/leave/invites, blocking and full entities.
- Pinned-first lazy pagination, explicit cursors, short-page handling, ordered missing
  ID results, bounded overlap tracking and no-progress errors.
- Non-channel deletion preflights chat ownership; channel deletion requires revoke=True.
- Per-session bounded peer cache persisted with additive version-1 metadata; min hashes
  never replace full hashes; username TTL/invalidation avoids indefinitely stale names.
- Reply/silent/preview send options, streamed send_document/send_photo and explicit logout.
- Command/media/chat-type filters, event action helpers, priorities, handler removal
  and StopPropagation; startup callbacks wait until the client is ready.
- New examples, controlled-RPC regression tests and core operations reference.


## 0.1.0a2 — unreleased

- Explicit `Session.open`, `Session.create` and `Session.temporary` modes; open-only
  rejects missing/unauthorized sessions, and create never replaces existing files.
- **Alpha behavior change:** bare Client session paths now mean open-only instead
  of silently creating a new database. Use Session.create for first-time login.
- New explicit `await client.login()` with bounded, separate phone/code/password
  re-prompts, expired-code refresh, injectable async prompts and safe error messages.
- Invalid input retries do not blindly repeat network failures or bypass flood waits.
- Backend warnings no longer reach stderr through logging.lastResort when logging
  is unconfigured; explicitly configured handlers still receive redacted diagnostics.
- Login CLI separates --create, --open, --resume and --temporary; examples updated.

## 0.1.0a1 — unreleased

- Project and distribution renamed to GramFlux (`gramflux`); import with `import gramflux`.

- Initial engineering alpha with explicit Telethon 1.45.0 runtime integration.
- Official schema provenance, deterministic typed generation, JSON cross-check and diff CLI.
- Independent bounded TL codec and reference TCP framing, with native initial handshake probe.
- Bounded public request admission, cancellation/deadline behavior and safe error mapping.
- GramFlux SQLite/memory session snapshots, ordered events, composable filters and streaming files.
- Deterministic tests, opt-in identity test, local codec benchmark, documentation and CI.

Not a production release candidate. Real-account authorization, message exchange,
update recovery and media interoperability have not been verified.
