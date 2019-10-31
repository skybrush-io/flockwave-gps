"""Error classes for the RTCM module."""

from flockwave.gps.errors import Error

__all__ = ("ChecksumError",)


class ChecksumError(Error):
    """Error thrown by the RTCM V3 parser when a packet was dropped due to
    a checksum mismatch.
    """

    def __init__(self, packet, parity):
        """Constructor.

        Parameters:
            packet (bytes): the payload of the packet that was dropped
            parity (bytes): the parity bytes of the packet that was dropped
        """
        super(Error, self).__init__(
            "Dropped packet of length {0} due to "
            "checksum mismatch".format(len(packet))
        )
        self.packet = packet
        self.parity = parity
