# Release assessment — 0.1.0a1

**Engineering alpha; not a production release candidate and not completion of the
master engineering specification.** A real dependency-backed client and independently
tested schema/tooling subsystem exist. An independent encrypted MTProto runtime,
measured product advantage, complete recovery and live-account verification do not.
No account credentials were available or requested for automatic testing.

## Implementation

Original modules implement explicit async lifecycle and request admission, immutable
configuration, sanitized structured errors/logs, code/bot/password login entrypoints,
own SQLite/memory session format, ordered event handlers and filters, bounded streaming
file pipelines, independent TL parser/generator/codec, transport reference and native
req_pq probe. Telethon 1.45.0 supplies actual encrypted MTProto and wire bindings.
Its pyaes/rsa/pyasn1 dependencies remain separately licensed. There is no vendored
competitor implementation or new home-grown cryptographic primitive.

## Verification commands

Command spellings below use the current package name. Network probe and explicit
schema-refresh observations were collected before the rename; local quality, schema,
package build and clean-install checks were repeated after renaming.

Executed in the local CPython 3.12.3 Linux x86_64 environment using `.venv/bin/`
executables (equivalent to activating the documented virtual environment):

| Command | Result |
| --- | --- |
| `python -m pip install -e '.[dev]'` | Succeeded; environment recreated after correcting initial Ruff exclusions |
| `pip install -r requirements-dev.lock` | Succeeded in recreated development environment |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed |
| `mypy src` | Passed strict mode, 24 production source files including generated declarations |
| `pytest -q` | 111 passed, 1 skipped (explicit opt-in real-account identity test) |
| `pytest tests/protocol/test_generated_roundtrips.py -q` | Passed; minimal shapes of all 1,572 non-vector constructors |
| `python -m gramflux.tools.schema generate` | Succeeded; regenerated checked-in output from exact source |
| `python -m gramflux.tools.schema verify` | Passed; 2,356 declaration IDs/fields match official JSON and deterministic output |
| `python -m gramflux.tools.schema update /tmp/gramflux-schema-refresh-20261020` | Succeeded; explicit new snapshot, did not change shipped sources |
| `python -m gramflux.tools.schema diff src/gramflux/tl/data/api.tl /tmp/gramflux-schema-refresh-20261020/api.tl` | No additions/removals/changes |
| `python -m gramflux.tools.probe` | Valid native req_pq_multi responses over full, intermediate and abridged TCP from DC 2, 149.154.167.51:443 |
| `python -m gramflux.tools.benchmark --iterations 5000 --rounds 5` | Succeeded; recorded local results below |
| `pip-audit -r requirements-runtime.lock --format json` | Succeeded; no known vulnerabilities reported for four runtime packages |
| `python -m compileall -q examples` | Passed; does not execute credential-dependent network examples |
| `python -m build` | Wheel and source distribution built successfully |
| `/tmp/gramflux-wheel-smoke/bin/pip install dist/gramflux-0.1.0a1-py3-none-any.whl` | Clean environment installation succeeded |
| `/tmp/gramflux-wheel-smoke/bin/python -I -m gramflux.tools.schema verify` | Offline installed-package verification passed |
| `/tmp/gramflux-sdist-smoke/bin/pip install dist/gramflux-0.1.0a1.tar.gz` | Clean environment installation succeeded |
| `/tmp/gramflux-sdist-smoke/bin/python -I -m gramflux.tools.schema verify` | Offline installed-package verification passed |

The full deterministic suite also passed against the installed wheel using
`/tmp/gramflux-wheel-smoke/bin/python -I -m pytest tests -q` (111 passed, 1 skipped).

The wheel smoke also constructs a disconnected client, imports raw layer 229 and
round-trips a generated object under Python isolated mode, verifying imports resolve
from site-packages rather than the source checkout. Source distribution includes tests,
examples, maintainers' docs, pinned schemas and license notices. Neither artifact has
been uploaded to a package index. CI is configured, not remotely executed here.

Earlier development failures were diagnosed and corrected: unsupported bare protocol
record handling in the parser; the Python keyword `True` in a generated class name;
backend requests incorrectly checked for a nonexistent content_related attribute;
generic BAD_REQUEST messages masking specific login errors; an unnecessary typing
suppression; Ruff default exclusions accidentally replaced rather than extended.
The latter touched only disposable environment/research files; the environment was
recreated from the pinned development snapshot before final checks.

Tests cover primitive properties, all constructor minimal round trips, optional/shared
flags, strict length/padding/ID/depth handling, selected differential bytes against
Telethon, fragmented TCP frames/CRC/sequence, native handshake with controlled server,
session persistence/ownership/corrupt/foreign data, bounded deadlines/cancellation,
out-of-order controlled responses, auth error/migration policies, handler failures,
filters, chunk boundaries, big/small uploads, partial writes, atomic paths and
interrupted transfer cleanup. Controlled backend tests are not Telegram integration.
Examples compile and their API operations have controlled tests; interactive examples
have not been fully executed with credentials.

## Performance evidence

Latest stored baseline, identical synthetic 64-byte inputFile, 5 rounds of 5,000
operations, Python 3.12.3 on the recorded shared Linux x86_64 environment:

| Operation | Median microseconds |
| --- | ---: |
| Independent GramFlux encode | 12.23 |
| Independent GramFlux decode | 26.22 |
| Telethon encode | 3.28 |
| Telethon decode | 6.83 |

See `research/benchmark.json` for raw rounds and traced allocation peaks. These are noisy
local measurements of different validation policies. GramFlux is slower on this input.
No RPC/network/file throughput, recovery latency, multiple-session RSS or user-facing
performance advantage has been demonstrated. Do not extrapolate these microbenchmarks.

## Compatibility and provenance

Actually tested platform: Linux x86_64, CPython 3.12.3. Declared Python >=3.11;
Ubuntu CI configured for 3.11–3.14. Persistent store requires POSIX flock. No other
Python/platform combinations have been locally verified. Official page advertised
layer 225; backend runtime layer 229. The source retrieval timestamps, URLs and hashes
are in `src/gramflux/tl/data/metadata.json`. Generated API coverage and live runtime
coverage are separate. PyPI gramflux lookup returned 404 at research time; no name
reservation, legal clearance or public publication is implied.

## Security assessment

Implemented: sensitive repr/log redaction, restrictive session mode, exclusive ownership,
format/version validation, transactions, cancellation-aware worker joining, independent
binary resource bounds, explicit retries/waits, trusted caller paths and temporary
cleanup. Runtime dependency scan reported no known vulnerabilities; heuristic secret
pattern scan reported no matches. These are limited automated checks, not a security
or cryptographic audit. Plaintext session keys, Python memory retention, backend buffer
limits, abrupt shutdown, untrusted local directories and upstream dependency behavior
remain risks. Reporting/maintainer contacts are not configured for this unpublished
alpha; see SECURITY.md and the threat model.

## Feature matrix and production blockers

| Classification | Features |
| --- | --- |
| Implemented and deterministically tested | Schema generation/verification/diff, codec, reference framing, stores, request admission/cancellation, events/filters, streaming transfer boundaries |
| Implemented, partially verified | Backend auth/key creation/encrypted RPC, identity/messaging/session reuse, actual media exchange, update gaps/recovery; local adapter tests but no account integration |
| Experimentally verified | Native credential-free initial handshake over three transports; isolated local codec benchmark |
| Planned/unsupported | Independent encrypted runtime, native schema-to-wire integration, durable/bounded end-to-end updates, CDN/cross-DC/resume, foreign sessions, proxies, Windows persistence, production guarantees |

Highest priorities, in severity order:

1. **Account and protocol interoperability:** real user/SRP/bot auth, login failures,
   session restart, messages/media and controlled real reconnect/migration tests.
2. **Update correctness/resources:** durable cursor/delivery policy, persistent entity
   hashes, bounded upstream buffering, verified gap/difference/channel recovery.
3. **Security/runtime boundaries:** independent review of crypto/session handling,
   remove or rigorously test private backend hooks, audit cancellation/resends and
   event-loop CPU behavior; configure private vulnerability reporting.
4. **Schema/runtime coherence:** verify layer divergence and add negotiated-layer
   adapters before accepting independent generated requests on the network.
5. **Transfer coverage and resilience:** media DC authorization, CDN, reference refresh,
   safe part retries and measured concurrency without unbounded resource use.
6. **Evidence before release:** OS/Python CI runs, crash/soak/memory tests, realistic
   performance profiles, license/branding review and repeatable release attestations.

The repository is useful for continued engineering and deliberate experimental use;
this assessment does not mark the master product's definition of done as achieved.
