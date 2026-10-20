"""Safe errors. Backend RPC messages are intentionally not included in text."""


class GramFluxError(Exception):
    """Base for errors owned by GramFlux."""


class ConfigurationError(GramFluxError, ValueError):
    """Invalid local configuration."""


class SerializationError(GramFluxError, ValueError):
    """Malformed or unsupported TL data."""


class SchemaError(GramFluxError, ValueError):
    """Invalid schema, with source location in the message."""


class LifecycleError(GramFluxError):
    """Operation requires a different client state."""


class TransportError(GramFluxError):
    """Connection failed; the remote outcome may be unknown."""


class SessionError(GramFluxError):
    """Session cannot be safely opened or saved."""


class SessionNotFound(SessionError):
    """Opening a saved session must not create a new file."""


class SessionAlreadyExists(SessionError):
    """Creating a named session must not replace an existing file."""


class StopPropagation(GramFluxError):
    """A handler intentionally stops dispatch of its current event."""


class PeerNotFound(GramFluxError):
    """A peer or required access hash is unavailable; never guess one."""


class PaginationError(GramFluxError):
    """Server pagination made no progress or omitted required cursor data."""


class UnsupportedFeature(GramFluxError):
    """Requested functionality is unavailable."""


class RPCError(GramFluxError):
    """Telegram rejected a request. ``name`` is a sanitized server error identifier."""

    def __init__(self, code: int, name: str) -> None:
        import re

        self.code = code
        self.name = name if re.fullmatch(r"[A-Z][A-Z_0-9]{0,100}", name) else "RPC_ERROR"
        super().__init__(f"Telegram RPC {code}: {self.name}")


class AuthenticationError(RPCError):
    """Invalid or missing authorization."""


class PasswordRequired(AuthenticationError):
    """Continue authorization with the account's two-step password."""


class AuthenticationRequired(AuthenticationError):
    """A connected transport does not imply an authorized account."""

    def __init__(self) -> None:
        super().__init__(401, "AUTH_KEY_UNREGISTERED")
        self.args = (
            "Session is not authorized. For a new or temporary session, call "
            "await client.login() before get_me(). To resume an unfinished saved login, "
            "use Session.open(name, require_authorized=False).",
        )


class LoginAttemptsExceeded(GramFluxError):
    """The local interactive login budget was exhausted, not a Telegram RPC error."""

    def __init__(self, stage: str, attempts: int, last_error_name: str) -> None:
        self.stage = stage
        self.attempts = attempts
        self.last_error_name = last_error_name
        super().__init__(f"Login {stage}: exhausted {attempts} attempts ({last_error_name})")


class FloodWait(RPCError):
    """Server-directed wait; GramFlux does not automatically sleep/retry."""

    def __init__(self, code: int, seconds: int, *, name: str | None = None) -> None:
        self.seconds = seconds
        super().__init__(code, name or f"FLOOD_WAIT_{seconds}")


class MigrationRequired(RPCError):
    """A request requires a different data center."""

    def __init__(self, code: int, dc: int, *, name: str | None = None) -> None:
        self.dc = dc
        self.retry_ready = False
        super().__init__(code, name or f"MIGRATE_{dc}")


class FileTransferError(GramFluxError):
    """A transfer failed; completed remote parts may remain temporarily."""
