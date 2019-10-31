"""Simple HTTP request object for the low-level HTTP library."""

import socket

from collections import OrderedDict
from io import BytesIO
from urllib.parse import quote, urlparse

from .response import Response

__all__ = ("Request",)


class Request(object):
    """HTTP request object."""

    def __init__(self, url, data=None, headers={}):
        """Constructs a new HTTP request object.

        Parameters:
            url (bytes): the URL to load
            data (bytes or None): the data to POST to the URL or ``None`` if
                no data should be posted. Currently unused, we have it here
                for compatibility with Python's own Request class from
                ``urllib2``.
            headers (dict): additional headers of the request.
        """
        self.url = url
        self.data = data
        self.headers = OrderedDict()
        for key, value in headers.items():
            self.add_header(key, value)

    def add_header(self, key, val):
        """Adds an HTTP header to the request.

        Parameters:
            key (bytes): the name of the header to add. It will be
                capitalized.
            val (bytes): the value of the header to add
        """
        self.headers[key.capitalize()] = val

    def has_header(self, key):
        """Checks whether the request contains the given HTTP header.

        Parameters:
            key (bytes): the name of the header to add. It will be
                capitalized.
        """
        return key.capitalize() in self.headers

    def send(self, timeout=10):
        """Sends the HTTP request and returns a Response_ object.

        Parameters:
            timeout (float): timeout in seconds for the connection attempt

        Returns:
            Response: the response object corresponding to the request

        Raises:
            NotImplementedError: when you have defined some data to POST
                because POST requests are not supported yet
        """
        if self.data is not None:
            raise NotImplementedError("POST requests not supported yet")

        method = b"GET"
        parts = urlparse(self.url)

        if not self.has_header("Host"):
            if parts.port and parts.port != 80:
                self.add_header("Host", "{0.hostname}:{0.port}".format(parts))
            else:
                self.add_header("Host", "{0.hostname}".format(parts))
        if not self.has_header("Connection"):
            self.add_header("Connection", "close")

        request = BytesIO()
        request.write(b"{0} {1} HTTP/1.1\r\n".format(method, quote(parts.path)))
        for header, value in self.headers.items():
            header = header.encode("ascii")
            if header == "User-agent":
                # Some buggy NTRIP servers don't recognize User-agent so we
                # spell it like this
                header = "User-Agent"
            value = value.encode("ascii")
            request.write(b"{0}: {1}\r\n".format(header, value))
        request.write(b"\r\n")

        sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        sock.send(request.getvalue())

        response = Response(sock)
        return response
