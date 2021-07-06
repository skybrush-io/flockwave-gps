from enum import Enum

__all__ = ("GNSSType",)


class GNSSType(Enum):
    """Enum representing the known Global Navigation Satellite Systems of the
    world.
    """

    # The order below reflects the order of these satellite systems in the
    # RTCM3 MSM message list; e.g., 1087 is GPS MSM7, 1097 is GLONASS MSM7,
    # 1107 is Galileo MSM7 and so on

    GPS = "gps"
    GLONASS = "glonass"
    GALILEO = "galileo"
    SBAS = "sbas"
    QZSS = "qzss"
    BEIDOU = "beidou"
    IRNSS = "irnss"
