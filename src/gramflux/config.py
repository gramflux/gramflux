"""Validated, immutable client settings."""

import math
from dataclasses import dataclass
from typing import Literal

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class Config:
    request_timeout: float = 30.0
    max_concurrent_requests: int = 32
    event_queue_size: int = 256
    reconnect_attempts: int = 3
    peer_cache_size: int = 2048
    transport: Literal["full", "intermediate", "abridged"] = "intermediate"
    update_queue_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if (
            isinstance(self.request_timeout, bool)
            or not isinstance(self.request_timeout, (float, int))
            or not math.isfinite(self.request_timeout)
            or self.request_timeout <= 0
        ):
            raise ConfigurationError("request_timeout must be finite and positive")
        for name in ("max_concurrent_requests", "event_queue_size", "update_queue_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConfigurationError(f"{name} must be a positive integer")
        if (
            isinstance(self.reconnect_attempts, bool)
            or not isinstance(self.reconnect_attempts, int)
            or self.reconnect_attempts < 0
        ):
            raise ConfigurationError("reconnect_attempts must be nonnegative")
        if (
            isinstance(self.peer_cache_size, bool)
            or not isinstance(self.peer_cache_size, int)
            or not 1 <= self.peer_cache_size <= 4096
        ):
            raise ConfigurationError("peer_cache_size must be between 1 and 4096")
        if self.transport not in {"full", "intermediate", "abridged"}:
            raise ConfigurationError("unknown TCP transport")
