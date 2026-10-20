# Third-party notices

GramFlux's original implementation is MIT licensed. No competitor Telegram-client
implementation is vendored or required at runtime. The former Telethon dependency
was removed in 0.3.0a1; historical reports describe earlier versions only.

The direct runtime dependency is cryptography (Apache-2.0 OR BSD-3-Clause), distributed
separately with its upstream notices and OpenSSL-backed primitives. Transitive CFFI
(MIT) and pycparser (BSD-3-Clause) retain their own notices. GramFlux does not relicense
these distributions. Consult exact dependency metadata when redistributing binaries.

Official Telegram schema definitions are retained with provenance in
src/gramflux/tl/data/metadata.json. Public protocol constants (RSA public keys, safe DH
prime, DC addresses) have official-source URL/commit/hash provenance in trust.json.
These are protocol data; no Telegram Desktop GPL implementation source was copied.
Telegram API/service use remains subject to upstream terms. MIT is not a claim to
exclusive rights in Telegram API definitions or public cryptographic constants.

Test vector JSON includes reference outputs produced using Telethon 1.45.0 (MIT) and
system OpenSSL; only serialized protocol data is retained. Tests and runtime do not
import those reference Telegram libraries. Prior Pyrogram/Hydrogram/gotd research
remains documentary; no implementation from them is shipped. Review branding and
redistribution obligations before a public stable release.
