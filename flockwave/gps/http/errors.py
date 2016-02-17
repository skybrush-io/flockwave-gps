"""Error classes for the low-level HTTP module."""


class ResponseError(RuntimeError):
    """Error thrown by HTTP response objects when they encounter an HTTP
    error code signalling an error condition.
    """

    pass
