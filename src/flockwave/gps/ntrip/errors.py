"""Error classes for the NTRIP module."""

from flockwave.gps.errors import Error

__all__ = ("NtripError", "InvalidResponseError")


class NtripError(Error):
    """Superclass for all NTRIP-related exceptions."""

    pass


class InvalidResponseError(NtripError):
    """Error thrown when the response of an NTRIP server contained
    something unexpected.
    """

    pass
