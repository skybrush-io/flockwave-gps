"""NTRIP client related classes."""

from __future__ import annotations

import click
import sys

from base64 import b64encode
from dataclasses import dataclass, replace
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse

from flockwave.gps.http import Request

if TYPE_CHECKING:
    from flockwave.gps.http import Response

from .errors import InvalidResponseError

__all__ = ("NtripClient", "NtripClientConnectionInfo")


@dataclass
class NtripClientConnectionInfo:
    """Dataclass that holds the parameters required to connect to an
    NTRIP caster on the Internet.
    """

    host: str
    port: int = 2101
    username: Optional[str] = None
    password: Optional[str] = None
    mountpoint: Optional[str] = None
    version: Optional[int] = None

    @classmethod
    def create_from_uri(cls, uri):
        """Creates a connection info object from a URI representation of the
        form::

            ntrip://[<username>:<password>]@<host>:[<port>][/<mountpoint>]

        or::

            ntrip1://[<username>:<password>]@<host>:[<port>][/<mountpoint>]
        """
        if uri.startswith("ntrip1"):
            parts = urlparse(uri, scheme="ntrip1")
            version = 1
        else:
            parts = urlparse(uri, scheme="ntrip")
            version = 2

        fake_uri = "http://" + parts.netloc + parts.path
        parts = urlparse(fake_uri, scheme="http")

        params = {
            "host": parts.hostname,
            "port": parts.port or 2101,
            "username": parts.username,
            "password": parts.password,
            "mountpoint": parts.path[1:] if len(parts.path) > 1 else None,
            "version": version,
        }
        return cls(**params)


class NtripClient:
    """An NTRIP client object that reads DGPS correction data from an NTRIP
    caster.
    """

    @classmethod
    def create(
        cls,
        host: str = "www.euref-ip.net",
        port: int = 2101,
        username: Optional[str] = None,
        password: Optional[str] = None,
        mountpoint: Optional[str] = None,
        version: Optional[int] = None,
    ):
        """Convenience constructor.

        Parameters:
            host: the hostname of the server. It may also be an
                URI if it starts with ``ntrip://`.
            port: the port of the server to connect to
            username: the username to use for authenticated streams
            password: the password to use for authenticated streams
            mountpoint: the mountpoint to read the RTCM messages from
            version: the NTRIP protocol version that the server speaks.
                ``None`` means the latest available version.

        Returns:
            NtripClient: a configured client object
        """
        if host.startswith("ntrip://") or host.startswith("ntrip1://"):
            conn = NtripClientConnectionInfo.create_from_uri(host)
            updates = {}
            if username is not None:
                updates["username"] = username
            if password is not None:
                updates["password"] = password
            if mountpoint is not None:
                updates["mountpoint"] = mountpoint
            if version is not None:
                updates["version"] = version
            if updates:
                conn = replace(conn, **updates)
        else:
            if version is None:
                version = 2
            if "/" in host and mountpoint is None:
                host, _, mountpoint = host.partition("/")
            conn = NtripClientConnectionInfo(
                host, port, username, password, mountpoint, version
            )
        return cls(connection_info=conn)

    def __init__(self, connection_info: NtripClientConnectionInfo):
        """Constructor.

        In most cases, it is easier to use the ``create()`` class method.

        Parameters:
            connection_info: an object describing how to connect to the server
        """
        self.connection_info = connection_info

    async def get_stream(self, mountpoint: Optional[str] = None, timeout: float = 10):
        """Returns a file-like object that will stream the DGPS data from
        the NTRIP caster.

        Parameters:
            mountpoint: the mountpoint to connect to. May be
                ``None``, in which case the mountpoint given in the
                connection info object at construction time will be used.
            timeout: timeout to use for the connection attempt, in seconds

        Throws:
            InvalidResponseError: when the caster returned an invalid
                response
        """
        url = self._url_for_mountpoint(mountpoint)

        request = Request(url)
        request.add_header("Accept", b"*/*")
        request.add_header("User-Agent", b"NTRIP NtripClientPOSIX/1.50")
        if self.connection_info.version == 2:
            request.add_header("Ntrip-Version", b"Ntrip/2.0")

        if self.connection_info.username is not None:
            credentials = b64encode(
                "{0.username}:{0.password}".format(self.connection_info).encode("utf-8")
            )
            credentials = credentials.replace(b"\n", b"")
            request.add_header("Authorization", b"Basic " + credentials)

        response = await request.send()
        await response.ensure_headers_processed()

        if response.protocol != b"ICY":
            self._check_header(response, "Content-type", b"gnss/data")

        return response

    def _check_header(self, response: Response, header: str, value: bytes):
        """Checks whether the given HTTP response contains the given header
        with the given value.
        """
        observed_value = response.getheader(header)
        if observed_value != value:
            raise InvalidResponseError(
                "expected Content-type: gnss/data, got {0!r}".format(observed_value)
            )

    def _url_for_mountpoint(self, mountpoint: Optional[str] = None) -> bytes:
        """Returns the URL of the given mountpoint.

        Parameters:
            mountpoint: the mountpoint to connect to. May be None, in which
                case the mountpoint given in the connection info object at
                construction time will be used.

        Returns:
            the URL of the given mountpoint
        """
        mountpoint = mountpoint or self.connection_info.mountpoint
        return f"http://{self.connection_info.host}:{self.connection_info.port}/{mountpoint}".encode(
            "ascii"
        )


@click.command()
@click.argument("url")
@click.option(
    "-u",
    "--username",
    metavar="USERNAME",
    default=None,
    help="the username to use when connecting",
)
@click.option(
    "-p",
    "--password",
    metavar="PASSWORD",
    default=None,
    help="the password to use when connecting",
)
def ntrip_streamer(url, username, password):
    """Copies a stream from an NTRIP server directly into the standard
    output.

    The given URL must adhere to the following format:

        [protocol://][username[:password]@]hostname/mountpoint

    where 'protocol' is either 'ntrip' (for NTRIP v2 casters) or 'ntrip1'
    (for NTRIP v1 casters), and it defaults to 'ntrip'. The username and the
    password is optional.

    Example servers to try (if you have the right username and password):
    www.euref-ip.net/BUTE0, ntrip://ntrip.use-snip.com/RTCM3EPH,
    ntrip1://152.66.6.49/RTCM23
    """
    try:
        from trio import run
    except ImportError:
        raise ImportError("You need to install 'trio' to use the NTRIP streamer")

    client = NtripClient.create(url, username=username, password=password)

    async def main():
        stream = await client.get_stream()
        while True:
            data = await stream.read()
            if not data:
                print("Stream ended.", file=sys.stderr)
                break
            sys.stdout.buffer.write(data)
            sys.stdout.flush()

    run(main)


if __name__ == "__main__":
    ntrip_streamer()  # type: ignore
