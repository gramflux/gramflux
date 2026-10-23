"""Lazy typed raw view; imports generated facade only when requested."""

from typing import Any

from .tl.generated.methods import API
from .tl.model import TLObject


class Raw(API):
    """Existing typed namespaces plus invoke on the original client."""

    async def invoke(self, request: TLObject) -> Any:
        """Delegate to Client.invoke without another runtime or schema mapping."""
        return await self._client.invoke(request)
