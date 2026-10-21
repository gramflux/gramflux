---
title: Contributing
description: Set up a reproducible development environment, update the schema and validate changes.
---

# Contributing

Keep changes small, typed and explicit about what has been verified. Read
[CONTRIBUTING.md](https://github.com/gramflux/gramflux/blob/main/CONTRIBUTING.md),
the [code of conduct](https://github.com/gramflux/gramflux/blob/main/CODE_OF_CONDUCT.md)
and [security policy](https://github.com/gramflux/gramflux/blob/main/SECURITY.md).

## Set up the checkout

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock -e '.[dev]'
```

Use the repository's lockfiles and package metadata rather than substituting
unverified runtime dependencies. Do not use a competing Telegram client as a
runtime fallback.

## Run quality gates

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m gramflux.tools.schema verify
python -m gramflux.tools.api_inventory --check
python -m gramflux.tools.docs --check
python -m build
python -m compileall -q examples
```

Live account tests are opt-in. Controlled protocol doubles are valuable but must
not be described as successful real-account authorization. See
[live validation](guides/live-validation.md).

## Refresh the pinned schema deliberately

```bash
python -m gramflux.tools.schema update /tmp/gramflux-new-schema
python -m gramflux.tools.schema diff src/gramflux/tl/data/api.tl /tmp/gramflux-new-schema/api.tl
```

Update fetches into a **new directory**, retaining official TL/JSON source,
retrieval time and SHA256 metadata. Review differences, compatibility impact and
runtime grammar support before adopting a snapshot. Updating a schema is a review
step, not an implicit side effect of installing the library.

After deliberately replacing the packaged snapshot and reviewing its metadata:

```bash
python -m gramflux.tools.schema generate
python -m gramflux.tools.schema verify
python -m gramflux.tools.api_inventory --write
python -m gramflux.tools.docs
```

Never hand-edit generated Python bindings or generated reference pages. Public
convenience behavior belongs in handwritten modules.

## Benchmarks and release preparation

```bash
python -m gramflux.tools.benchmark
python -m build
```

Record interpreter, dependencies, hardware and inputs for measurements. Separate
local codec/dispatch measurements from Telegram latency and transfer throughput.
Install the resulting wheel and source distribution in clean environments and
verify imports/examples. Review licenses, security-sensitive code and unsupported
workflows before publishing. An alpha build is not production certification.

The [documentation workflow](documentation.md) covers Docusaurus, generated
references, browser checks and deployment configuration.
