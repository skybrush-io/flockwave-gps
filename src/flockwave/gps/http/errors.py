"""Error classes for the low-level HTTP module."""

from flockwave.gps.errors import Error

__all__ = ("ResponseError",)


class ResponseError(Error):
    """Error thrown by HTTP response objects when they encounter an HTTP
    error code signalling an error condition.
    """

    pass


class AccessDeniedError(ResponseError):
    """Error thrown by HTTP response objects that indicate that access to a
    particular resource was denied by the server.
    """

    pass


class AuthenticationNeededError(ResponseError):
    """Error thrown by HTTP response objects that indicate that authentication
    will be needed to access a resource.
    """

    pass


class NotFoundError(ResponseError):
    """Error thrown by HTTP response objects that indicate that a remote
    resource is not found.
    """

    pass
