# Contributing

Start with the [architecture](docs/design/architecture.md), [roadmap](docs/roadmap.md)
and [security model](docs/design/security-model.md). Changes should be small and
include evidence appropriate to the behavior. Do not claim live Telegram verification
from a controlled backend test.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy src
pytest
python -m gramflux.tools.schema verify
python -m build
```

`requirements-dev.lock` records the complete CPython 3.12/Linux development environment,
without hashes. Use `pip install -r requirements-dev.lock` to reproduce that environment;
it is not a platform-independent resolver lock. Runtime versions are also pinned in
`requirements-runtime.lock`. Never commit session files, account data, or credentials.

Schema updates are explicit:

```bash
python -m gramflux.tools.schema update /tmp/gramflux-new-schema
python -m gramflux.tools.schema diff src/gramflux/tl/data/api.tl /tmp/gramflux-new-schema/api.tl
```

Review both snapshots' layer advertisement, all hashes, TL/JSON consistency, removals,
changed signatures, and unsupported grammar. Copy reviewed files into `tl/data`, run
`generate`, then `verify`, lint, typing and tests. Generated code is never hand-edited.
Protocol preludes and bare message records have special binary semantics; parser
acceptance is not equivalent to standalone runtime support. A backend upgrade requires
its own schema/protocol/session interoperability review and differential regression run.

For release: update version and changelog, run CI and clean wheel/sdist installs,
review third-party notices and security scan, execute opt-in account tests using a
dedicated authorized test account, and update `docs/release-report.md` with actual
results. Reproduce benchmark inputs before discussing performance. Publishing a GitHub
Release triggers `.github/workflows/publish.yml`, which validates the matching version
tag, runs quality checks, builds distributions, and publishes them to PyPI. Configure
a PyPI Trusted Publisher for this repository, workflow `publish.yml`, and GitHub
environment `pypi` first. The tag must be the package version, optionally prefixed
with `v` (for example, `v0.1.0a1`). No long-lived PyPI API token is required.

Alpha interfaces may change. After 1.0 use semantic versioning, document deprecations
and keep deprecated public APIs for at least one minor release unless security requires
faster removal. Report private security issues using SECURITY.md.


To exercise transfer scheduling without Telegram credentials:

```bash
python -m gramflux.tools.transfer_benchmark --size-mib 4 --part-size 65536 --concurrency 1 4 --latency-ms 2 --rounds 3
```

This uses synthetic per-RPC latency and temporary disk input, not a Telegram service.
Record the complete JSON and environment; do not advertise it as live throughput.


The production runtime and test suite must not import a competing Telegram client.
Native raw namespaces are generated alongside objects by the schema CLI; both are
verified deterministically. Protocol-vector JSON includes recorded external reference
outputs as data, not a runtime/test dependency. Do not edit generated files by hand.

Native protocol verification without personal credentials is explicit:

```bash
GRAMFLUX_NATIVE_NETWORK=1 pytest tests/integration/test_native_live.py
python -m gramflux.tools.native_probe --mode intermediate
python -m gramflux.tools.native_benchmark --size 524288 --rounds 5
```

The first two commands contact Telegram and create anonymous auth keys. The probe
reports remote key cleanup as uncertain if no confirmation is parsed. These are not
account login/media/update-recovery tests. Do not set their opt-in flag in default CI.

The English documentation uses Docusaurus. Read [the documentation workflow](docs/documentation.md).
Run `python -m gramflux.tools.docs --check` for generated references and
`cd website && npm ci && npm run build` to check the site.
