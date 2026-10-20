# Documentation

- [Installation and usage](../README.md)
- [Authentication](guides/authentication.md)
- [Sessions](guides/sessions.md)
- [Events and filters](guides/events.md)
- [File transfers](guides/files.md)
- [Errors, transport and troubleshooting](guides/operations.md)
- [Migration from other libraries](guides/migration.md)
- [Public API reference](api.md)
- [Schema workflow](../CONTRIBUTING.md)
- [Architecture](design/architecture.md)
- [Competitive research](design/competitive-analysis.md)
- [Security model](design/security-model.md)
- [Performance methodology](design/performance-plan.md)
- [Compatibility and coverage](design/compatibility.md)
- [Roadmap](roadmap.md)
- [Release assessment](release-report.md)

For a searchable Python signature/docstring reference, run `python -m pydoc gramflux.client`
or use your editor. `py.typed` ships in the package. Generated dataclass fields carry
primitive/list annotations; named object unions currently use `TLObject`, so constructor
union narrowing is a known typing limitation. Backend raw object types follow Telethon's
typing quality, not a claim of fully strict generated runtime stubs.
