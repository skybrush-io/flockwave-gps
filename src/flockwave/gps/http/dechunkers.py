"""Dechunker objects that convert a chunked HTTP response into a
normal byte stream.
"""

from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import List, Optional

__all__ = ("NullDechunker", "ResponseDechunker")

ResponseDechunkerState = Enum(
    "ResponseDechunkerState", "START HEADER_ENDING BODY BODY_ENDING"
)


class Dechunker(metaclass=ABCMeta):
    """Base class for dechunkers."""

    @abstractmethod
    def feed(self, data: bytes) -> bytes:
        raise NotImplementedError


class NullDechunker(Dechunker):
    """Null dechunker that is suitable for un-chunked HTTP responses."""

    def feed(self, data: bytes) -> bytes:
        """Returns the data fed into the dechunker without changes.

        Parameters:
            data: the bytes to feed into the dechunker

        Returns:
            bytes: the same bytes
        """
        return data


class ResponseDechunker(Dechunker):
    """Merges the chunks of a HTTP response that is streamed using chunked
    transfer encoding.
    """

    def __init__(self):
        """Constructor."""
        self.reset()

    def feed(self, data: bytes) -> bytes:
        """Feeds some bytes into the dechunker object. Returns dechunked
        data.

        Parameters:
            data: the bytes to feed into the dechunker

        Returns:
            bytes: the dechunked data
        """
        result: List[int] = []
        for byte in data:
            byte = self._feed_byte(byte)
            if byte is not None:
                result.append(byte)
        return bytes(result)

    def reset(self) -> None:
        """Resets the dechunker to its ground state."""
        self._current_chunk = []
        self._chunk_length = 0
        self._state = ResponseDechunkerState.START

    def _feed_byte(self, byte: int) -> Optional[int]:
        if self._state == ResponseDechunkerState.START:
            if byte == b"\r":
                self._state = ResponseDechunkerState.HEADER_ENDING
            else:
                try:
                    self._chunk_length = (self._chunk_length << 4) + int(chr(byte), 16)
                except ValueError:
                    raise ValueError(
                        "chunked transfer encoding protocol "
                        "violation; got {0!r} when expecting a "
                        "hexadecimal number".format(byte)
                    )
        elif self._state == ResponseDechunkerState.HEADER_ENDING:
            if byte != b"\n":
                raise ValueError(
                    "chunked transfer encoding protocol "
                    "violation; got {0!r} when expecting '\\n'".format(byte)
                )
            self._state = ResponseDechunkerState.BODY
        elif self._state == ResponseDechunkerState.BODY:
            if self._chunk_length > 0:
                self._chunk_length -= 1
                return byte
            else:
                if byte != b"\r":
                    raise ValueError(
                        "chunked transfer encoding protocol "
                        "violation; got {0!r} when expecting "
                        "'\\r'".format(byte)
                    )
                self._state = ResponseDechunkerState.BODY_ENDING
        elif self._state == ResponseDechunkerState.BODY_ENDING:
            if byte != b"\n":
                raise ValueError(
                    "chunked transfer encoding protocol "
                    "violation; got {0!r} when expecting "
                    "'\\n'".format(byte)
                )
            self.reset()
        else:
            raise ValueError("invalid decoder state: {0!r}".format(self._state))
