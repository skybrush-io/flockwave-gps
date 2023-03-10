# trio is an optional dependency, but we need to import it directly at the
# top level because we will derive a class from it. That's why this module
# is marked entirely as lazy as _this_ module must be imported lazily.

from typing import Optional

from trio.abc import ReceiveStream

__all__ = ("PushbackStreamWrapper",)


class PushbackStreamWrapper(ReceiveStream):
    """Trio stream that allows us to push some data in front of the "real"
    stream.
    """

    _remainder: bytearray
    _stream: ReceiveStream

    def __init__(self, stream: ReceiveStream):
        """Constructor.

        Parameters:
            stream: the original stream that this stream wraps.
        """
        self._remainder = bytearray()
        self._stream = stream

    async def aclose(self) -> None:
        await self._stream.aclose()

    def push_back(self, data: bytes) -> None:
        self._remainder = bytearray(data) + self._remainder

    async def receive_some(self, max_bytes: Optional[int] = None) -> bytes:
        if self._remainder:
            available = len(self._remainder)
            to_return = (
                min(max_bytes, available) if max_bytes is not None else available
            )
            result = self._remainder[:to_return]
            del self._remainder[:to_return]
            return result

        return await self._stream.receive_some(max_bytes)  # type: ignore
