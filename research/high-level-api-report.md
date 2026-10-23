# Direct high-level Client API engineering report

## Scope and architecture

The inspected baseline is commit a08bf60. It had **82 public Client methods**.
The additive implementation introduces **57 public methods**, bringing the actual
introspected count to **139**, plus the `is_connected` property. These numbers include
lifecycle, subscriptions and aliases; they are not a count of distinct Telegram RPCs.

The exact old inventory and every added signature are committed in
[high-level-inventory.json](high-level-inventory.json). The generated
[public inventory](../docs/api-surface.json) remains separate from the 783 raw functions
and 1573 constructors of the unchanged pinned official layer 225 schema.

HighLevelMethods and ManagementMethods are explicit typed mixins on Client. They reuse
existing peer resolution, Client.invoke, request admission, upload/download and
cancellation. Sending normalization was extracted without changing its logic from
backend.py into sending.py so text, media, inline results and albums share correlation.
Photo location selection was extracted from files.py to support real profile metadata
without fabricating a Message. No crypto, MTProto protocol, session storage, generated
TL source or dependency lockfile changed. No competing Telegram client was introduced.

Direct Client methods are primary. Existing optional Router, CommandContext, domains,
ChatResource, client.api/client.raw and invoke retain their contracts and event engine.
The existing 82-method signature/default snapshot is still exercised unchanged.

## Existing versus added

| Area | Existing retained operations | Additions |
| --- | --- | --- |
| Lifecycle/auth | connect/disconnect/login, staged login, get_me, is_authorized, log_out | is_bot; is_connected property |
| Entities | resolve_peer, get_chat/get_user/full variants | get_entity, get_input_entity, get_peer_id, get_users |
| Messages/history | send/edit/delete/forward/get_messages, history/search iterators, read/pin/reactions/drafts | iter_messages, get_message, copy_message, counts, caption/media/markup edits |
| Media/files | upload_file, download_file/media and ranged iterators, send_photo/document/contact/location/dice | video, round video, audio, voice, animation, sticker, cached media, albums, venue, game, poll, rich send_media |
| Groups/members | members/iter_members, join/leave, title/about, invite inspection/export | participant/member lookup/count; ban/unban/restrict/promote/default permissions; group/channel creation; chat photos; invite revocation/join-request approval |
| Account/contacts | contacts, block/unblock, profile text, active remote sessions and termination | username, profile photo upload/list/delete/download |
| Bots | callbacks/inline answers, bot command get/set, inline result retrieval | command deletion, menus, familiar result getter and actual inline result sending |
| Dialog/admin | get/iter_dialogs and save_draft | archive moves, draft snapshot getter/lazy start, paginated admin log |

Some additions deliberately delegate existing functionality (for example iter_messages,
get_participants and get_inline_bot_results). They are not advertised as new protocol
capabilities. `get_messages` keeps its existing ordered list/missing-slot contract;
`get_message` supplies single-ID convenience without breaking it.

### Improved existing method

`send_file` additionally accepts local paths and supported caller-owned binary streams.
Its implementation signature/defaults and previously accepted uploaded/native input
behavior remain unchanged. Typed overloads advertise local inputs. Local JPG/JPEG/PNG
sources infer photo unless document mode or MIME is explicit; pre-uploaded handles
retain old document behavior. Upload and send are not an atomic transaction.

## Source and documentation

New production files:
- src/gramflux/highlevel.py
- src/gramflux/management.py
- src/gramflux/sending.py

Modified production/tool files:
- src/gramflux/client.py, backend.py, files.py, __init__.py
- src/gramflux/tools/api_inventory.py, docs.py
- src/gramflux/tools/data/client_reference.json (canonical handwritten reference metadata)

New tests: tests/integration/test_highlevel_p0.py,
test_highlevel_methods.py and tests/unit/test_highlevel_documentation.py.
Existing tests were not weakened. Browser expectations for the public count and primary
quick-start syntax were updated to reflect the implemented additive contract.

Documentation source:
- [High-Level API overview](../docs/client-methods/index.md)
- [Messages/entities/iteration](../docs/client-methods/messages.md)
- [Media/transfers/AlbumItem](../docs/client-methods/media.md)
- [Administration/permissions/bots](../docs/client-methods/administration.md)
- [Coverage and explicit deferred work](../docs/client-methods/coverage.md)
- 57 new individual generated Client method pages; Client index and send_file updated
- Quick Start, quick reference, files guides, Next API overview, README, documentation map,
  sidebar and machine-readable inventory updated
- examples/high_level.py and examples/high_level_legacy.py are equivalent complete
  executable applications, checked through controlled native boundaries; live use requires
  an authorized session and application secrets

All **975** generated reference pages pass deterministic verification. Generation uses
canonical metadata and actual signatures; no generated TL source was hand-edited.
Detailed signatures/parameters/returns/errors/examples are in the individual method pages,
linked from the coverage table, rather than duplicated in this report.

## Verification executed

Environment: **Linux x86_64, Python 3.12.3 and 3.13.16**. Node 22.23.3 for Docusaurus.

| Actual command | Result |
| --- | --- |
| `.venv/bin/ruff check .` | Passed |
| `.venv/bin/ruff format --check .` | Passed, 195 files |
| `.venv/bin/mypy src` | Passed, 62 source files |
| `.venv/bin/python -m pytest -q` | 1817 passed, 6 skipped, 4 warnings |
| `/tmp/gramflux-python313/bin/python -m pytest -q` | 1817 passed, 6 skipped, 4 warnings |
| `.venv/bin/python -m pytest -q tests/unit/test_highlevel_documentation.py tests/integration/test_highlevel_methods.py tests/integration/test_highlevel_p0.py` | 116 passed |
| `.venv/bin/python -m gramflux.tools.schema verify` | Passed; unchanged pinned layer 225 |
| `.venv/bin/python -m gramflux.tools.api_inventory --check` | Passed |
| `.venv/bin/python -m gramflux.tools.docs --check` | Passed, 975 pages |
| `.venv/bin/python -m gramflux.tools.next_reference --check` | Passed |
| `.venv/bin/python -m gramflux.tools.docs_sources verify` | Passed |
| `.venv/bin/python -m compileall -q examples` | Passed |
| `.venv/bin/python -m build` | Wheel and source distribution built |
| `/tmp/gramflux-next-wheel/bin/pip install --force-reinstall --no-deps dist/gramflux-0.5.0a2-py3-none-any.whl` | Installed in isolated environment |
| `/tmp/gramflux-next-wheel/bin/python -I -m pytest /root/gramjet/tests -q` | 1817 passed, 6 skipped, 4 warnings |
| `/tmp/gramflux-next-actionlint-v1712/actionlint` | Passed |
| `.venv/bin/python -m pip_audit -r requirements-runtime.lock` | No known vulnerabilities found |
| `PATH=/root/.npm/_npx/d18f28baf1132559/node_modules/node/bin:$PATH npm --prefix website run build` | Passed; static site and search index generated |
| `PATH=/root/.npm/_npx/d18f28baf1132559/node_modules/node/bin:$PATH npm --prefix website test` | 13 browser tests passed |

Docusaurus validates links/anchors and generated a search index of 11344 sections
(not 11344 independent API methods). Browser tests cover navigation, mobile overflow,
search, clipboard, legacy examples and new direct method parameter pages. Node emitted
only environment color-setting warnings during browser startup.

The six skips are opt-in Telegram account tests, not successful live authorization.
The four warnings are the existing cryptography finite-field-DH deprecations required
by Telegram's current protocol; nothing was suppressed. During development, new test
fixtures initially lacked required native `topics` and used the wrong FloodWait test
constructor. Those fixtures were corrected. The new complete-example assertion also
initially used the public as_document keyword to inspect a backend call; it now checks
the existing backend force_document keyword. A new documentation snippet test also
initially treated the callable chat cached-property as a class method; it now checks
bound callables. No existing expected behavior was removed to obtain a pass.

The final metadata-only parameter clarifications were rebuilt into the wheel and checked
from the installed distribution. Request behavior had no changes after the full runs.

## Behavior and security boundaries

Real TL request encoding, result normalization/correlation, reversed album result order,
progress/stream ownership, input validation and server error identity/no automatic retry
are exercised by controlled fixtures. Existing engine, auth, session, update, Router,
queue and cancellation tests continue passing. These are not substitutes for real-account
interoperability or independent security review.

Access hashes and file references always come from real supplied/cached/server metadata.
Protected messages are rejected by copying/cached helpers. Album uploads can outlive a
failed final send. No write retry, permission bypass or arbitrary URL fetch was added.
Settings DTOs use positive allowed-action/grant semantics and native TL rights encoding.
Draft/caption representations avoid exposing message text through these new DTO reprs.

## Differences and deferred capabilities

See [the explicit evaluation table](../docs/client-methods/coverage.md). Important limits:
- Literal text and explicit entities; no parse_mode parser, media probe or transcoding.
- Application-supplied video dimensions/durations; appropriate encoded sources required.
- Albums are homogeneous photos or documents, not all media combinations.
- Copying supports ordinary text/photo/document, not arbitrary polls/games/service events.
- Cancel the individual transfer task; no global stop_transmission that could cancel others.
- Draft iteration is lazy-start over a full server snapshot, not falsely paginated.
- No portable session strings, combined destructive delete_dialog, global search,
  custom dialog-filter lifecycle, advanced 2FA settings, statistics DC/graph workflow,
  profile video or new CDN/resume support is claimed.
- New helper restrictions and bot/user/admin eligibility remain server enforced.

Competitor references reviewed for public API scope, without copying implementation:
[Telethon client reference](https://docs.telethon.dev/en/stable/quick-references/client-reference.html),
[TelegramClient](https://docs.telethon.dev/en/stable/modules/client.html),
[Hydrogram available methods](https://docs.hydrogram.org/en/latest/api/methods/index.html),
[Hydrogram methods](https://docs.hydrogram.org/en/latest/api/methods/).
Protocol shapes were checked against the pinned schema and official Telegram method/
constructor documentation, especially layer-225 Poll/TextWithEntities/correct-answer indices.

## Next priorities

1. Run dedicated opt-in real user/bot validation of each new media/admin family and reconcile
   server eligibility/format constraints; do not publish production-readiness claims first.
2. Independently review native crypto and exercise disconnect/uncertain-result/fault soaks.
3. Implement tested file-DC/CDN authorization and expired-reference recovery before promising
   broad cross-DC media support; keep write reconciliation explicit.
4. Extend album types, optional text parsing and statistics only with separate tested contracts.

Version remains 0.5.0a2 development; this task does not publish a new PyPI release.

## Complete equivalent applications

[Existing direct API application](../examples/high_level_legacy.py) uploads explicitly
then sends the real handle and uses iter_history.
[Extended direct API application](../examples/high_level.py) sends the local path and
uses iter_messages. Both preserve document mode, edit/fetch the same Saved Messages
content and close the Client through its existing context manager. Configure
GRAMFLUX_API_ID/GRAMFLUX_API_HASH and run either with `--session account --file report.pdf`.
The saved session must already be authorized; neither script silently creates or logs in.
