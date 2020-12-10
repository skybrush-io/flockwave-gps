"""Classes and functions related to handling the native protocol of U-blox
GPS receivers.
"""

from .enums import UBXClass
from .message import UBXMessage

__all__ = ("UBXClass", "UBXMessage")
