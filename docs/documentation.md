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

The reference contains 975 pages: individual pages for the 139 public Client methods
and its constructor, 783 raw functions, eight event classes and 13 builder/filter/
session helpers, plus indexes. Curated parameter explanations live in
`src/gramflux/tools/data/client_reference.json`. Edit that source rather than
generated pages; the renderer reads actual signatures and schema fields.

The official-reference snapshot records URLs, retrieval times, content hashes,
method-ID checks, parameter coverage and documented RPC error identifiers. It
retains at most 25 prose words from each official method page. This documentation
snapshot does not establish live interoperability for those methods.

Refresh it explicitly when internet access is available:

```bash
python -m gramflux.tools.docs_sources update --workers 4
python -m gramflux.tools.docs_sources verify
python -m gramflux.tools.docs
python -m gramflux.tools.docs --check
```

Normal generation and verification use committed data offline. Review source and
generated diffs before committing. Building hundreds of static routes can take
several minutes.

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
workflow builds and checks relevant pushes to the repository's default branch,
`v0.x-dev`, then deploys to the `github-pages` environment. Pull requests only build
and test; they never publish. You can also run the workflow manually and leave
`deploy` enabled to publish the verified site. Local builds never publish.

### Enable GitHub Pages once

A repository administrator must enable the hosting source at
[Repository Settings → Pages](https://github.com/gramflux/gramflux/settings/pages):
under **Build and deployment**, set **Source** to **GitHub Actions**.
This is separate from pushing files with Git. The workflow's GITHUB_TOKEN can
publish after Pages is enabled, but cannot perform initial enablement itself.
No PyPI token or Trusted Publisher configuration is involved.

Once enabled, push a documentation change to `v0.x-dev`, or open
[Actions → Documentation](https://github.com/gramflux/gramflux/actions/workflows/docs.yml)
and run the workflow on `v0.x-dev` with `deploy` enabled. The deployment job reports
the final `page_url`. The expected project URL is
[gramflux.github.io/gramflux](https://gramflux.github.io/gramflux/).

If a first run failed because Pages was disabled, enable the source and rerun that
workflow. A configured deployment URL is not proof of a successful live deployment.

See [Docusaurus deployment](https://docusaurus.io/docs/deployment) for supported
static hosts and base-path configuration.

## Organize explanations by reader intent

The sidebar separates Getting started, Tutorials, How-to guides, Concepts, Quick
references, API reference and Help. Keep existing document paths when reorganizing
navigation so published links and bookmarks continue to work.

- A tutorial supplies a complete application, prerequisites, observable test steps
  and an explanation of the control flow. It must distinguish a manual live-test
  procedure from a live test actually performed by maintainers.
- A how-to guide solves one task with stated client/session prerequisites and links
  to exact method contracts. It should explain meaningful parameter interactions.
- A concept chapter explains a model shared by several operations, including its
  failure/reliability boundaries. It should not become another signature dump.
- A quick reference groups operations by purpose and links to individual pages.
  Update the Client table when the public surface changes; a contract test checks
  that every public method appears exactly once.
- Generated API pages remain the detailed parameter reference. Handwritten learning
  chapters do not silently add keywords or features absent from those signatures.

The learning-documentation tests parse Python snippets, bind direct Client calls
against real signatures and verify local Markdown targets. Browser tests check the
quick-start Next link, conceptual chapters, quick-reference coverage and tutorial
navigation. These checks do not substitute for authenticated Telegram integration.

## Next-Generation API reference

Run `python -m gramflux.tools.next_reference` and its `--check` mode for the separate
Next-Generation reference. This generator reads actual view signatures and the
packaged `tools/data/next_api_mapping.json`, linking each operation to its legacy
contract. Generated reference Markdown is excluded from handwritten code formatting.
Router and command behavior belong in the handwritten next-api chapters and tests.
