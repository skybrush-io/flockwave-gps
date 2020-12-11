from typing import Callable

from .packet import UBXPacket

__all__ = ("create_ubx_encoder",)


def create_ubx_encoder() -> Callable[[UBXPacket], bytes]:
    """Creates a UBX encoder function that is suitable to be used in
    conjunction with the channels from the ``flockwave-conn`` module.

    Returns:
        the encoder function
    """
    return UBXPacket.encode
