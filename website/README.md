# GramFlux documentation website

English documentation, built with Docusaurus 3.10.2 and local search. Content is
served from `../docs`; there is no second copied set of guides to maintain.

Use Node.js 22 (see `.nvmrc`). From the repository root, install the Python package
and run `python -m gramflux.tools.docs --check` to verify the committed API reference.

```bash
cd website
npm ci
npm start
```

Production preview and browser checks:

```bash
npm run build
npx playwright install chromium
npm test
npm run serve
```

Open `http://localhost:3000/gramflux/`. Local search is generated during production
builds, so use `build` + `serve` when reviewing search. The build fails on broken
internal links, anchors or images. No external search keys, fonts or analytics are
required.

See [documentation development](../docs/documentation.md) for regeneration, hosting,
base-path overrides and the manually triggered Pages deployment job. Merely building
or adding the workflow does not publish a site.

## Dependency maintenance

`package-lock.json` is committed. Tinypool, serialize-javascript, UUID and the
PostCSS selector parser have explicit patched-version overrides; check the production build and browser tests before
changing these boundaries. Run `npm audit` when updating dependencies. Outstanding
build-tool advisories must be assessed separately from the emitted static site;
do not treat a successful build as a dependency security certification. The local
development server binds to loopback by default.

The local audit on 2026-10-21 reported 29 high-severity dependency entries, all
propagating the still-unpatched braces stack-exhaustion advisory
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
No critical or moderate entries remained after the reviewed overrides. These are
Node build/development dependencies, not a deployed Node service or Python runtime
dependencies. Treat glob patterns and build inputs as trusted; the advisory remains
open and is not represented as fixed.
