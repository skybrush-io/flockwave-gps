"""Simple HTTP response object for the low-level HTTP library."""

from __future__ import absolute_import

from contextlib import closing
from .dechunkers import NullDechunker, ResponseDechunker
from .errors import ResponseError

__all__ = ("Response", )


class Response(object):
    """Simple HTTP response object."""

    def __init__(self, sock):
        """Constructor.

        Parameters:
            sock (socket): the socket to read the response from
        """
        self.sock = sock
        self._headers = None
        self._protocol = None
        self._dechunker = None

    def _read_headers(self):
        """Reads all the headers from the response and ensures that the
        socket points to the first body byte.
        """
        # Use a non-buffered file so we can switch to non-blocking mode
        # later
        self._headers = {}
        with closing(self.sock.makefile("rb", 0)) as fp:
            line = fp.readline().strip()
            parts = line.split(None, 2) if line else []
            if len(parts) < 3 or parts[0] not in ("HTTP/1.1", "ICY"):
                raise ValueError("Invalid response line: {0!r}".format(line))

            self._protocol = parts[0]
            code = parts[1]
            if code != b"200":
                raise ResponseError("Received HTTP response: {0!r}"
                                    .format(code))

            if self._protocol == b"ICY":
                # Special case for NTRIP caster version 1; it has no headers
                return

            while line:
                line = fp.readline().strip()
                if not line:
                    break
                key, sep, value = line.partition(b":")
                if not sep:
                    raise ValueError("Found invalid HTTP header line: {0!r}"
                                     .format(line))
                self._headers[key.capitalize()] = value.lstrip()

    def _process_headers(self):
        if self.getheader("Transfer-Encoding") == "chunked":
            self._dechunker = ResponseDechunker()
        else:
            self._dechunker = NullDechunker()

    def close(self):
        """Closes the response object."""
        self.sock.close()

    def fileno(self):
        """Returns the file descriptor corresponding to the response
        object.
        """
        return self.sock.fileno()

    def getheader(self, header, default=None):
        """Returns the value of the given header or the given default value."""
        return self.headers.get(header.capitalize(), default)

    @property
    def headers(self):
        """Returns a dictionary containing the response headers."""
        if self._headers is None:
            self._read_headers()
            self._process_headers()
        return self._headers

    @property
    def protocol(self):
        """Returns the protocol string found in the response; typically
        ``HTTP/1.0`` or ``HTTP/1.1``, but it may also be ``ICY`` for NTRIP
        caster v1 servers for instance.
        """
        if self._protocol is None:
            self._read_headers()
            self._process_headers()
        return self._protocol

    def read(self, num_bytes=None):
        """Reads the given number of bytes from the response.

        Parameters:
            num_bytes (int or None): the number of bytes to read; ``None``
                means to read all the available bytes from the response.

        Returns:
            bytes: the bytes read from the response stream
        """
        if self._headers is None:
            self._read_headers()
            self._process_headers()

        block_size = 4096
        bytes_left = num_bytes if num_bytes is not None else None
        result = []
        while True:
            if bytes_left is None:
                to_read = block_size
            else:
                to_read = min(bytes_left, block_size)
            chunk = self.sock.recv(to_read)
            if self._dechunker is not None:
                chunk = self._dechunker.feed(chunk)
            result.append(chunk)
            if bytes_left is not None:
                bytes_left -= len(chunk)
            if len(chunk) < to_read:
                break
        return b"".join(result)
