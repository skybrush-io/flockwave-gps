"""Simple HTTP request object for the low-level HTTP library."""

from io import BytesIO
from typing import Optional, OrderedDict
from urllib.parse import quote, urlparse

from .response import Response

__all__ = ("Request",)


class Request:
    """HTTP request object."""

    data: Optional[bytes]
    """The data to send in the body of the HTTP request."""

    headers: OrderedDict[str, bytes]
    """The headers to send with the HTTP request."""

    def __init__(
        self,
        url: bytes,
        data: Optional[bytes] = None,
        headers: Optional[dict[str, bytes]] = None,
    ):
        """Constructs a new HTTP request object.

        Parameters:
            url: the URL to load
            data: the data to POST to the URL or ``None`` if no data should be
                posted. Currently unused, we have it here for compatibility with
                Python's own Request class from ``urllib2``.
            headers: additional headers of the request.
        """
        self.url = url
        self.data = data
        self.headers = OrderedDict()
        for key, value in (headers or {}).items():
            self.add_header(key, value)

    def add_header(self, key: str, val: bytes) -> None:
        """Adds an HTTP header to the request.

        Parameters:
            key: the name of the header to add. It will be capitalized.
            val: the value of the header to add
        """
        self.headers[key.capitalize()] = val

    def has_header(self, key: str) -> bool:
        """Checks whether the request contains the given HTTP header.

        Parameters:
            key: the name of the header to check. It will be capitalized.
        """
        return key.capitalize() in self.headers

    async def send(self, timeout: float = 10) -> Response:
        """Sends the HTTP request and returns a Response_ object.

        Returns:
            the response object corresponding to the request

        Raises:
            NotImplementedError: when you have defined some data to POST
                because POST requests are not supported yet
        """
        try:
            from trio import open_tcp_stream
        except ImportError:
            raise ImportError("You need to install 'trio' to use this method") from None

        if self.data is not None:
            raise NotImplementedError("POST requests not supported yet")

        method = "GET"
        parts = urlparse(self.url)

        if not self.has_header("Host"):
            assert parts.hostname is not None

            hostname = parts.hostname.decode("utf-8")
            port = parts.port

            if parts.port and parts.port != 80:
                self.add_header("Host", f"{hostname}:{port}".encode("ascii"))
            else:
                self.add_header("Host", hostname.encode("ascii"))

        if not self.has_header("Connection"):
            self.add_header("Connection", b"close")

        request = BytesIO()
        request.write(
            "{0} {1} HTTP/1.1\r\n".format(method, quote(parts.path)).encode("ascii")
        )
        for header, value in self.headers.items():
            header = header.encode("ascii")
            if header == b"User-agent":
                # Some buggy NTRIP servers don't recognize User-agent so we
                # spell it like this
                header = b"User-Agent"
            request.write(header)
            request.write(b": ")
            request.write(value)
            request.write(b"\r\n")
        request.write(b"\r\n")

        stream = await open_tcp_stream(parts.hostname, parts.port)
        await stream.send_all(request.getvalue())

        return Response(stream)
