# Security policy

This is an unaudited engineering alpha. Do not use it for sensitive production accounts.
The release blockers and threat model are documented in `docs/design/security-model.md`.

Do not put authorization keys, session databases, phone numbers, API hashes, bot tokens,
passwords, codes, or private messages into public issues. For a security report, use the
hosting project's private vulnerability reporting facility once the repository is hosted.
No private reporting address or hosted repository has yet been configured. Until one
exists, a sensitive deployment should not rely on this project's response process.
A public report can describe the affected component without exploit secrets or account data.

Currently only the latest alpha is supported on a best-effort basis; there is no
security support SLA. Before release, the maintainer must configure a private reporting
channel, triage owner and advisory process. Dependency scanning does not constitute a
cryptographic audit or guarantee absence of vulnerabilities.
