"""Very low-level HTTP client library.

This is primarily used in place of higher-level libraries like ``httplib``
or ``urllib2`` when we need to mess with the underlying socket directly.
"""

from .errors import ResponseError
from .request import Request
from .response import Response

__all__ = ("Request", "Response", "ResponseError")
