"""Error classes for the low-level HTTP module."""

from flockwave.gps.errors import Error

__all__ = ("ResponseError", )


class ResponseError(Error):
    """Error thrown by HTTP response objects when they encounter an HTTP
    error code signalling an error condition.
    """

    pass
