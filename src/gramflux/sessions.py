"""Explicit choices between saved, newly created and process-local sessions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .errors import ConfigurationError
from .storage import MemoryStorage, SQLiteStorage, Storage


def session_path(name: str | Path) -> Path:
    """Resolve a name using the same suffix convention as legacy Client paths."""
    if isinstance(name, str) and not name.strip():
        raise ConfigurationError("session name must not be empty")
    path = Path(name)
    if not path.name:
        raise ConfigurationError("session name must identify a file")
    return path if path.suffix else path.with_suffix(".session")


@dataclass(frozen=True, slots=True)
class Session:
    """Session intent. Files are acquired at connect time, not construction time.

    ``open`` requires an existing, authorized GramFlux session by default.
    ``create`` exclusively creates a new file, never overwriting an existing one.
    ``temporary`` keeps its authorization key only in this process's memory.
    """

    mode: Literal["open", "create", "temporary"]
    path: Path | None = None
    require_authorized: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"open", "create", "temporary"}:
            raise ConfigurationError("unknown session mode")
        if not isinstance(self.require_authorized, bool):
            raise ConfigurationError("require_authorized must be bool")
        if (self.mode == "temporary") != (self.path is None):
            raise ConfigurationError("saved sessions require a path; temporary sessions have none")
        if self.require_authorized and self.mode != "open":
            raise ConfigurationError("only saved-session open can require existing authorization")

    @classmethod
    def open(cls, name: str | Path, *, require_authorized: bool = True) -> "Session":
        return cls("open", session_path(name), require_authorized)

    @classmethod
    def create(cls, name: str | Path) -> "Session":
        return cls("create", session_path(name))

    @classmethod
    def temporary(cls) -> "Session":
        return cls("temporary")

    def _storage(self) -> Storage:
        if self.mode == "temporary":
            return MemoryStorage()
        assert self.path is not None
        return SQLiteStorage(self.path, mode=self.mode)
