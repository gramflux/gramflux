"""Schema descriptors and the generated-object base class."""

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    id: int
    params: tuple[Parameter, ...]
    result: str
    method: bool = False
    generics: tuple[str, ...] = ()
    line: int = field(default=0, compare=False)


@dataclass(slots=True, repr=False)
class TLObject:
    """Typed generated declaration. Repr deliberately excludes field values."""

    definition: ClassVar[Definition]

    def __repr__(self) -> str:
        return f"<{self.definition.name}>"

    def __bytes__(self) -> bytes:
        from .codec import Codec

        return Codec().encode(self)

    def __getattr__(self, name: str) -> Any:
        if name == "is_self":
            return bool(getattr(self, "self", False))
        if name in {"chat_id", "sender_id"} and self.definition.result == "Message":
            from gramflux.peer_utils import get_peer_id

            peer = getattr(self, "peer_id" if name == "chat_id" else "from_id", None)
            if peer is None and name == "sender_id" and not getattr(self, "out", False):
                remote = getattr(self, "peer_id", None)
                if remote is not None and remote.definition.name == "peerUser":
                    peer = remote
            return get_peer_id(peer) if peer is not None else None
        if name == "message" and self.definition.name == "messageService":
            return ""
        if name in {"document", "photo"} and self.definition.result == "Message":
            media = getattr(self, "media", None)
            return getattr(media, name, None) if media is not None else None
        if name in {"video", "audio", "voice", "sticker"} and self.definition.result == "Message":
            document = self.document
            for attribute in getattr(document, "attributes", []) if document is not None else []:
                kind = attribute.definition.name
                if name == "video" and kind == "documentAttributeVideo":
                    return document
                if (
                    name in {"voice", "audio"}
                    and kind == "documentAttributeAudio"
                    and bool(attribute.voice) == (name == "voice")
                ):
                    return document
                if name == "sticker" and kind == "documentAttributeSticker":
                    return document
            return None
        raise AttributeError(name)


def python_name(name: str) -> str:
    import keyword

    return name + "_" if keyword.iskeyword(name) else name


def class_name(d: Definition) -> str:
    return python_name(
        "".join(s[:1].upper() + s[1:] for s in d.name.split(".")) + ("Request" if d.method else "")
    )
