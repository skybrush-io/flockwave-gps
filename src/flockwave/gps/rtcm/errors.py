"""Error classes for the RTCM module."""

from flockwave.gps.errors import Error

__all__ = ("ChecksumError",)


class ChecksumError(Error):
    """Error thrown by the RTCM V3 parser when a packet was dropped due to
    a checksum mismatch.
    """

    def __init__(self, packet: bytearray, parity: bytearray):
        """Constructor.

        Parameters:
            packet: the payload of the packet that was dropped
            parity: the parity bytes of the packet that was dropped
        """
        super().__init__(
            f"Dropped packet of length {len(packet)} due to checksum mismatch"
        )
        self.packet = packet
        self.parity = parity
