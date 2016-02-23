"""Main package for the Flockwave GPS module."""

from __future__ import absolute_import

from .errors import Error
from .version import __version__, __version_info__

__all__ = ("__version__", "__version_info__", "Error")
