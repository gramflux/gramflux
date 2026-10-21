---
title: Installation
description: Install GramFlux from source or a built wheel and verify your Python environment.
---

# Installation

## Requirements

- Python **3.11 or newer**. Local validation covers 3.11 through 3.14 on Linux x86-64.
- A Telegram API ID and API hash for your application.
- A supported network route to Telegram's TCP endpoints.
- POSIX file locking for persistent SQLite sessions. Windows persistent storage is
  currently unsupported; other platform behavior is not certified.

The sole direct runtime dependency is `cryptography`, pinned in the package
metadata. GramFlux does not install Telethon, Pyrogram or Hydrogram.

## Install from a checkout

Use an isolated environment so your interpreter and installation match:

```bash
git clone https://github.com/gramflux/gramflux.git
cd gramflux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -c "import gramflux; print(gramflux.__version__)"
```

This guide does not assume that a matching release has been published to PyPI.
Normal installation uses shipped generated bindings and pinned schemas; it does
not need to download or regenerate Telegram's schema.

## Install a locally built distribution

From the checkout, build a wheel and source archive:

```bash
python -m pip install build
python -m build
python -m pip install dist/gramflux-0.5.0a2-py3-none-any.whl
```

Keep session files and secrets outside your source tree and version control.

## Contributor installation

```bash
python -m pip install -r requirements-dev.lock -e '.[dev]'
ruff check .
mypy src
pytest
```

Node.js is needed only to maintain the Docusaurus website; it is not a Python
runtime requirement. See [documentation development](../documentation.md).

Continue with the [quick start](quickstart.md).
