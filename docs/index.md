# Documentation

- [Installation and usage](../README.md)
- [Core operations](guides/core-operations.md)
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
- [Initial release assessment (historical)](release-report.md)
- [0.1.0a2 session/login fix report](releases/0.1.0a2.md)

For a searchable Python signature/docstring reference, run `python -m pydoc gramflux.client`
or use your editor. `py.typed` ships in the package. Generated dataclass fields carry
primitive/list annotations; named object unions currently use `TLObject`, so constructor
union narrowing is a known typing limitation. Native raw dataclasses share the wire
codec, but complex sum/result types are not yet fully narrowed by the generator.

- [0.2.0a1 development report](releases/0.2.0a1.md)

- [0.2.0a2 transfer pipeline report](releases/0.2.0a2.md)

- [0.3.0a1 independent runtime report](releases/0.3.0a1.md)

- [Native update ordering and recovery](design/update-state.md)

- [0.3.0a2 production assessment](releases/0.3.0a2.md)
- [Dedicated live validation](guides/live-validation.md)

- [Bot operations and typed events](guides/bots-and-events.md)
- [Public API inventory](api-surface.json)

- [0.4.0a1 operations and events](releases/0.4.0a1.md)
