"""Simple HTTP response object for the low-level HTTP library."""

from __future__ import annotations

from typing import Dict, Generator, Optional, TYPE_CHECKING

from .dechunkers import Dechunker, NullDechunker, ResponseDechunker
from .errors import AccessDeniedError, AuthenticationNeededError, ResponseError

if TYPE_CHECKING:
    from trio.abc import ReceiveStream

__all__ = ("Response",)


class LineReader:
    """Helper object for Trio that takes a ReceiveStream and parses lines
    out of it.
    """

    stream: "ReceiveStream"
    _buffer: bytearray
    _line_generator: Generator[Optional[bytes], Optional[bytes], None]

    def __init__(self, stream: "ReceiveStream", max_line_length: int = 16384):
        self.stream = stream

        self._buffer = bytearray()
        self._line_generator = self.generate_lines(max_line_length, self._buffer)

    @staticmethod
    def generate_lines(
        max_line_length: int, buffer: bytearray
    ) -> Generator[Optional[bytes], Optional[bytes], None]:
        buf = buffer or bytearray()
        find_start = 0
        while True:
            newline_idx = buf.find(b"\n", find_start)
            if newline_idx < 0:
                # no b'\n' found in buf
                if len(buf) > max_line_length:
                    raise ValueError("line too long")
                # next time, start the search where this one left off
                find_start = len(buf)
                more_data = yield
            else:
                # b'\n' found in buf so return the line and move up buf
                line = buf[: newline_idx + 1]
                # Update the buffer in place, to take advantage of bytearray's
                # optimized delete-from-beginning feature.
                del buf[: newline_idx + 1]
                # next time, start the search from the beginning
                find_start = 0
                more_data = yield line

            if more_data is not None:
                buf += bytes(more_data)

    def get_remainder(self) -> bytes:
        self._line_generator.close()
        return bytes(self._buffer)

    async def readline(self) -> bytes:
        line = next(self._line_generator)
        while line is None:
            more_data = await self.stream.receive_some(1024)
            if not more_data:
                return b""  # this is the EOF indication expected by my caller
            line = self._line_generator.send(more_data)
        return line


class Response:
    """Simple HTTP response object that reads from a Trio ReceiveStream,
    skips over the headers and de-chunks chunked responses automatically.
    """

    _stream: "ReceiveStream"
    _headers: Optional[Dict[str, bytes]]
    _protocol: Optional[bytes]
    _dechunker: Optional[Dechunker]
    _line_reader: LineReader

    def __init__(self, stream: "ReceiveStream"):
        """Constructor.

        Parameters:
            stream: the stream to read the response from
        """
        self._stream = stream

        self._headers = None
        self._protocol = None
        self._dechunker = None
        self._line_reader = LineReader(self._stream)

    async def _read_headers(self) -> None:
        """Reads all the headers from the response and ensures that the
        stream points to the first body byte.
        """
        assert self._headers is None

        self._headers = {}

        readline = self._line_reader.readline

        line = await readline()
        if not line:
            raise ResponseError("Connection closed unexpectedly by the remote server")

        parts = line.strip().split(None, 2) if line else []
        if len(parts) < 3 or parts[0] not in (b"HTTP/1.1", b"ICY"):
            raise ValueError("Invalid response line: {0!r}".format(line))

        self._protocol = parts[0]
        code = parts[1]
        if code == b"401":
            raise AuthenticationNeededError("Authentication needed")
        elif code == b"403":
            raise AccessDeniedError("Access denied")
        elif code != b"200":
            raise ResponseError("Received HTTP response: {0!r}".format(code))

        if self._protocol != b"ICY":
            while line:
                line = await readline()
                line = line.strip()
                if not line:
                    break

                key, sep, value = line.partition(b":")
                if not sep:
                    raise ValueError(
                        "Found invalid HTTP header line: {0!r}".format(line)
                    )

                self._headers[key.decode("ascii").capitalize()] = value.lstrip()

        from ._lazy_deps import PushbackStreamWrapper

        self._stream = PushbackStreamWrapper(self._stream)
        self._stream.push_back(self._line_reader.get_remainder())

    def _process_headers(self):
        if self.getheader("Transfer-Encoding") == b"chunked":
            self._dechunker = ResponseDechunker()
        else:
            self._dechunker = NullDechunker()

    async def aclose(self):
        """Closes the response object."""
        await self._stream.aclose()

    async def ensure_headers_processed(self) -> None:
        """Ensures that the headers of the response are processed."""
        if self._headers is None:
            await self._read_headers()
            self._process_headers()

    def getheader(
        self, header: str, default: Optional[bytes] = None
    ) -> Optional[bytes]:
        """Returns the value of the given header or the given default value,
        assuming that the headers are already processed.

        Use `ensure_headers_processed()` if you want to make sure that the
        headers are already processed.
        """
        assert self._headers is not None, "Headers are not processed yet"
        return self._headers.get(header.capitalize(), default)

    @property
    def headers(self) -> Dict[str, bytes]:
        """Returns a dictionary containing the response headers,
        assuming that the headers are already processed.

        Use `ensure_headers_processed()` if you want to make sure that the
        headers are already processed.
        """
        assert self._headers is not None, "Headers are not processed yet"
        return self._headers

    @property
    def protocol(self) -> bytes:
        """Returns the protocol string found in the response; typically
        ``HTTP/1.0`` or ``HTTP/1.1``, but it may also be ``ICY`` for NTRIP
        caster v1 servers for instance.

        Use `ensure_headers_processed()` if you want to make sure that the
        headers are already processed.
        """
        assert self._protocol is not None, "Headers are not processed yet"
        return self._protocol

    async def receive_some(self, max_bytes: Optional[int] = None) -> bytes:
        """Reads the given number of bytes from the response.

        Parameters:
            max_bytes: the maximum number of bytes to read

        Returns:
            the bytes read from the response stream
        """
        await self.ensure_headers_processed()

        block_size = 4096
        bytes_left = max_bytes if max_bytes is not None else None
        result = []

        while True:
            if bytes_left is None:
                to_read = block_size
            else:
                to_read = min(bytes_left, block_size)

            chunk = await self._stream.receive_some(to_read)
            if not chunk:
                break

            if self._dechunker is not None:
                chunk = self._dechunker.feed(chunk)

            result.append(chunk)
            if bytes_left is not None:
                bytes_left -= len(chunk)

            if len(chunk) < to_read:
                break

        return b"".join(result)

    read = receive_some
