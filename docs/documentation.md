---
title: Documentation development
description: Maintain and build the English Docusaurus site and its generated Python and TL reference.
---

# Documentation development

The English site uses Docusaurus 3.10.2. Handwritten content lives in `docs/`;
React pages, styles and website tooling live in `website/`. The Python runtime does
not depend on Node.js or Docusaurus.

## Prerequisites

- Node.js 22 or newer; `website/.nvmrc` pins the tested Node 22 release.
- npm and the committed `website/package-lock.json`.
- The editable Python development installation for reference generation.

Docusaurus's [official installation guide](https://docusaurus.io/docs/installation)
describes its runtime requirements. The local-search plugin builds a browser-side
index and needs no Algolia account or external search credentials.

## Preview and build

```bash
python -m gramflux.tools.docs --check
cd website
npm ci
npm start
```

The development server serves the configured project path `/gramflux/`. Search is
available in the production build, not the live development index.

```bash
npm run build
npm run serve
```

The production build writes `website/build/`. Broken document links, anchors,
missing images and duplicate routes fail the build. The site does not require
external fonts or analytics to render.

## Regenerate the API reference

From the repository root:

```bash
python -m gramflux.tools.api_inventory --write
python -m gramflux.tools.docs
python -m gramflux.tools.docs --check
```

The generator inspects public Client signatures, Config, session factories,
event fields/helpers, filter/button functions and error inheritance. It also emits
all 783 pinned raw API methods by namespace, with IDs, results, required parameters,
optional flags and official source links. Generated pages are committed and marked;
normal website browsing and builds do not need Telegram credentials or network
schema downloads. Changed handwritten files in the generated directory are never
overwritten silently.

Generated reference code blocks are excluded from Ruff formatting so generation
is deterministic. Handwritten Markdown Python blocks remain format checked.

## Browser checks

```bash
cd website
npx playwright install chromium
npm test
```

Tests serve the production build and check navigation, responsive layout, theme
switching, code copy behavior, local search and raw API reference routes. They do
not authenticate to Telegram. Review screenshots on desktop and mobile when changing
the visual design.

## Hosting

The default target is the GitHub project path
`https://gramflux.github.io/gramflux/`. This is configuration, not evidence that a
site has been deployed. Override both deployment settings for a different host:

```bash
DOCS_URL=https://docs.example.com DOCS_BASE_URL=/ npm run build
```

Keep `DOCS_BASE_URL` rooted with a trailing slash. The GitHub Actions documentation
workflow builds and checks the site on relevant changes. Deployment, when requested
through its manual input, uses the `github-pages` environment and requires Pages
configured to use GitHub Actions. No publish action is executed by a local build.

See [Docusaurus deployment](https://docusaurus.io/docs/deployment) for supported
static hosts and base-path configuration.
