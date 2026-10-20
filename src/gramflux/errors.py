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


class FloodWait(RPCError):
    """Server-directed wait; GramFlux does not automatically sleep/retry."""

    def __init__(self, code: int, seconds: int) -> None:
        self.seconds = seconds
        super().__init__(code, f"FLOOD_WAIT_{seconds}")


class MigrationRequired(RPCError):
    """A request requires a different data center."""

    def __init__(self, code: int, dc: int) -> None:
        self.dc = dc
        super().__init__(code, f"MIGRATE_{dc}")


class FileTransferError(GramFluxError):
    """A transfer failed; completed remote parts may remain temporarily."""
