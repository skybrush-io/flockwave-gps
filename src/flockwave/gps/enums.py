from __future__ import annotations

from enum import Enum

__all__ = ("GNSSType",)


_gnss_type_to_string: dict[GNSSType, str] = {}


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

    def describe(self) -> str:
        result = _gnss_type_to_string.get(self)
        return result or f"unknown GNSS type: {self!r}"


_gnss_type_to_string[GNSSType.GPS] = "GPS"
_gnss_type_to_string[GNSSType.GLONASS] = "GLONASS"
_gnss_type_to_string[GNSSType.GALILEO] = "Galileo"
_gnss_type_to_string[GNSSType.SBAS] = "SBAS"
_gnss_type_to_string[GNSSType.QZSS] = "QZSS"
_gnss_type_to_string[GNSSType.BEIDOU] = "BeiDou"
_gnss_type_to_string[GNSSType.IRNSS] = "IRNSS"
