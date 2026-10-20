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
results. Reproduce benchmark inputs before discussing performance. Publishing is a
separate maintainer action; this repository's automation does not upload distributions.

Alpha interfaces may change. After 1.0 use semantic versioning, document deprecations
and keep deprecated public APIs for at least one minor release unless security requires
faster removal. Report private security issues using SECURITY.md.
