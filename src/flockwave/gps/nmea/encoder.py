from typing import Callable

from .packet import NMEAPacket

__all__ = ("create_nmea_encoder",)


class NMEAEncoder:
    """NMEA-0183 sentence encoder."""

    def encode(self, packet: NMEAPacket) -> bytes:
        return str(packet).encode("ascii") + b"\r\n"


def create_nmea_encoder() -> Callable[[NMEAPacket], bytes]:
    """Creates an NMEA-0183 encoder function that is suitable to be used in
    conjunction with the channels from the ``flockwave-conn`` module.

    Returns:
        the encoder function
    """
    return NMEAEncoder().encode
