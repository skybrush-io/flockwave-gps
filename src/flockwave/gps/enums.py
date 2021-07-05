from enum import Enum

__all__ = ("GNSSType",)


class GNSSType(Enum):
    """Enum representing the known Global Navigation Satellite Systems of the
    world.
    """

    GPS = "gps"
    GLONASS = "glonass"
    GALILEO = "galileo"
    BEIDOU = "beidou"
    QZSS = "qzss"
    NAVIC = "navic"
