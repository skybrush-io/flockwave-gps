"""NTRIP client related classes."""

import base64
import click
import sys

from collections import namedtuple
from flockwave.gps.http import Request
from urllib.parse import urlparse

from .errors import InvalidResponseError

__all__ = ("NtripClient", "NtripClientConnectionInfo")


class NtripClientConnectionInfo(
    namedtuple(
        "NtripClientConnectionInfo",
        "server port username password " "mountpoint version",
    )
):
    """Named tuple that holds the parameters required to connect to an
    NTRIP caster on the Internet.
    """

    @classmethod
    def create_from_uri(cls, uri):
        """Creates a connection info object from a URI representation of the
        form::

            ntrip://[<username>:<password>]@<server>:[<port>][/<mountpoint>]

        or::

            ntrip1://[<username>:<password>]@<server>:[<port>][/<mountpoint>]
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
            "server": parts.hostname,
            "port": parts.port or 2101,
            "username": parts.username,
            "password": parts.password,
            "mountpoint": parts.path[1:] if len(parts.path) > 1 else None,
            "version": version,
        }
        return cls(**params)


class NtripClient(object):
    """An NTRIP client object that reads DGPS correction data from an NTRIP
    caster.
    """

    @classmethod
    def create(
        cls,
        server="www.euref-ip.net",
        port=2101,
        username=None,
        password=None,
        mountpoint=None,
        version=None,
    ):
        """Convenience constructor.

        Parameters:
            server (str): the hostname of the server. It may also be an
                URI if it starts with ``ntrip://`.
            port (int): the port of the server to connect to
            username (str or None): the username to use for authenticated
                streams
            password (str or None): the password to use for authenticated
                streams
            mountpoint (str or None): the mountpoint to read the DGPS stream
                from
            version (int or None): the NTRIP protocol version that the
                server speaks. ``None`` means the latest available version.

        Returns:
            NtripClient: a configured client object
        """
        if server.startswith("ntrip"):
            conn = NtripClientConnectionInfo.create_from_uri(server)
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
                conn = conn._replace(**updates)
        else:
            if version is None:
                version = 2
            if "/" in server and mountpoint is None:
                server, _, mountpoint = server.partition("/")
            conn = NtripClientConnectionInfo(
                server, port, username, password, mountpoint, version
            )
        return cls(connection_info=conn)

    def __init__(self, connection_info=None):
        """Constructor.

        In most cases, it is easier to use the ``create()`` class method.

        Parameters:
            connection_info (NtripClientConnectionInfo): an object
                describing how to connect to the
        """
        self.connection_info = connection_info

    def stream(self, mountpoint=None, timeout=10):
        """Returns a file-like object that will stream the DGPS data from
        the NTRIP caster.

        Parameters:
            mountpoint (str or None): the mountpoint to connect to. May be
                ``None``, in which case the mountpoint given in the
                connection info object at construction time will be used.
            timeout (float): timeout to use for the connection attempt,
                in seconds
            blocking (bool): whether the returned file-like object should
                be in blocking mode

        Throws:
            InvalidResponseError: when the caster returned an invalid
                response
        """
        url = self._url_for_mountpoint(mountpoint)

        request = Request(url)
        request.add_header("Accept", "*/*")
        request.add_header("User-Agent", "NTRIP NtripClientPOSIX/1.50")
        if self.connection_info.version == 2:
            request.add_header("Ntrip-Version", "Ntrip/2.0")

        if self.connection_info.username is not None:
            credentials = base64.encodestring(
                "{0.username}:{0.password}".format(self.connection_info)
            )
            credentials = credentials.replace("\n", "")
            request.add_header("Authorization", "Basic {0}".format(credentials))

        response = request.send()
        if response.protocol != "ICY":
            self._check_header(response, "Content-type", "gnss/data")
        return response

    def _check_header(self, response, header, value):
        """Checks whether the given HTTP response contains the given header
        with the given value.
        """
        observed_value = response.getheader(header)
        if observed_value != value:
            raise InvalidResponseError(
                "expected Content-type: gnss/data, " "got {0!r}".format(observed_value)
            )

    def _url_for_mountpoint(self, mountpoint=None):
        """Returns the URL of the given mountpoint.

        :param mountpoint: the mountpoint to connect to. May be None, in which
            case the mountpoint given in the connection info object at
            construction time will be used.
        :type mountpoint: str or None
        :return: the URL of the given mountpoint
        :rtype: str
        """
        mountpoint = mountpoint or self.connection_info.mountpoint
        return "http://{0.connection_info.server}:{0.connection_info.port}/{1}".format(
            self, mountpoint
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
    www.euref-ip.net/BUTE0, ntrip://products.igs-ip.net/RTCM3EPH,
    ntrip1://152.66.6.49/RTCM23
    """
    client = NtripClient.create(url, username=username, password=password)
    stream = client.stream()
    while True:
        sys.stdout.write(stream.read())
        sys.stdout.flush()


if __name__ == "__main__":
    ntrip_streamer()
