# Explicit Telegram validation

Live tests are disabled by default. Configure a dedicated Telegram test account or bot;
never send credentials, codes, passwords or session databases in issues or chat logs.
An absent opt-in skips the tests. An enabled test with missing configuration fails.

The manually dispatched `.github/workflows/telegram-integration.yml` has three scopes:

| Scope | Operations | Required environment secrets |
| --- | --- | --- |
| read-only | Open saved session, identity, close and reopen, identity consistency | GRAMFLUX_API_ID, GRAMFLUX_API_HASH, GRAMFLUX_TEST_SESSION_BASE64 |
| bot-login | New in-memory authorization, identity, explicit logout of that test authorization | GRAMFLUX_API_ID, GRAMFLUX_API_HASH, GRAMFLUX_BOT_TOKEN |
| self-roundtrip | Read-only checks plus message/event, upload, document send, download checksum and scoped cleanup | Same as read-only; dedicated user account required |

Use the GitHub environment `telegram-test`. The session secret is a base64 encoding of
a **closed GramFlux session**, never another library's database or a live database
missing its WAL. Treat the encoded form exactly like an authentication credential.
The workflow writes it exclusively with mode 0600, serializes test-account access,
never uploads it and runs a cleanup step even after failure. Base64 is not encryption;
GitHub secrets and runner isolation are part of the operator's trust boundary.
This workflow has been added locally, not executed on GitHub in this environment.

Equivalent local execution uses application-controlled environment variables:

```sh
# Credentials and session path must already be supplied securely in this shell.
GRAMFLUX_LIVE=1 pytest tests/integration/test_live.py -q --tb=short
GRAMFLUX_LIVE_BOT=1 pytest tests/integration/test_live.py -q --tb=short
# Explicitly permits writes to the dedicated user's Saved Messages:
GRAMFLUX_LIVE=1 GRAMFLUX_LIVE_WRITE=1 pytest tests/integration/test_live.py -q --tb=short
```

Local saved-session tests use GRAMFLUX_SESSION (a path), not the base64 secret.
Do not enable pytest locals/verbose payload diagnostics with real credentials.
The document test uses random synthetic bytes. Cleanup deletes only returned IDs
created by that test; an ambiguous failed write can leave an unidentified test item
for manual inspection. It never sweeps message history. An event may originate from
an RPC Updates result, so this test alone does not establish unsolicited socket-update
or gap-recovery correctness. Bot test logout affects its new temporary authorization.

A green local/mock suite is not a substitute for these tests. Identity checks do not
prove phone-code/2FA authentication; dedicated manual tests and controlled-disconnect,
DC migration, update-gap and sustained-transfer validation are still necessary.
