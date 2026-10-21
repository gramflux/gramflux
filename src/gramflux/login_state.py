"""Minimal resumable authentication metadata; never contains codes or passwords."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class PendingLogin:
    stage: Literal["code", "password"]
    phone: str | None = field(default=None, repr=False)
    code_hash: str | None = field(default=None, repr=False)

    def dump(self) -> dict[str, str | None]:
        return {"stage": self.stage, "phone": self.phone, "code_hash": self.code_hash}

    @classmethod
    def load(cls, value: object) -> "PendingLogin | None":
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) != {"stage", "phone", "code_hash"}:
            raise ValueError("invalid pending login metadata")
        stage, phone, code_hash = value["stage"], value["phone"], value["code_hash"]
        if stage == "password" and phone is None and code_hash is None:
            return cls("password")
        if (
            stage == "code"
            and isinstance(phone, str)
            and 0 < len(phone) <= 128
            and isinstance(code_hash, str)
            and 0 < len(code_hash) <= 4096
        ):
            return cls("code", phone, code_hash)
        raise ValueError("invalid pending login metadata")
