# Evidence snapshots

Collected 2026-10-20. Repository metadata JSON contains primary GitHub API observations;
test inventory records filenames/counts, not executed competitor tests. No competitor
implementation source is included. Current Telethon package metadata and source links
are described in docs/design/competitive-analysis.md; its old GitHub mirror is archived.

- `schema-coverage.json`: offline generated/official-JSON verification output.
- `schema-diff.json`: explicit fresh-fetch comparison with the pinned source.
- `native-probe.json`: actual credential-free DC-2 handshake over three transports.
- `native-probe.txt`: initial single intermediate-mode handshake observation.
- `benchmark.json`: measured local codec timings and environment; no network measurement.
- `dependency-audit.json`: runtime dependency vulnerability query at scan time.
- `dependency-audit.txt`: earlier audit of the same pinned runtime set.
- `secret-scan.json`: limited heuristic source scan, not a confidentiality guarantee.

Exact official schema bytes and provenance live inside the installed package's `tl/data`.
See docs/release-report.md for validation commands and limitations. No account tests or
competitor benchmark results beyond the documented local codec comparison are implied.
