from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from .nmea.packet import create_nmea_packet

if TYPE_CHECKING:
    from .vectors import GPSCoordinate


__all__ = (
    "format_gps_coordinate",
    "format_gps_coordinate_as_nmea_gga_message",
    "format_latitude_for_nmea_gga_message",
    "format_longitude_for_nmea_gga_message",
)


def format_gps_coordinate(coord: GPSCoordinate) -> str:
    """Formats a GPS coordinate in a human-readable way."""
    return coord.format()


def format_gps_coordinate_as_nmea_gga_message(
    coord: GPSCoordinate, *, time: Optional[datetime] = None
) -> str:
    """Formats a GPS coordinate into an NMEA GGA message."""
    if time is None:
        time = datetime.now(timezone.utc)

    alt = coord.amsl if coord.amsl is not None else 0.0

    packet = create_nmea_packet(
        "GP",
        "GGA",
        (
            # Time in HHMMSS format
            time.strftime("%H%M%S") + f".{int(time.microsecond // 10000):02}",
            # Latitude and latitude sign
            *format_latitude_for_nmea_gga_message(coord.lat),
            # Longitude and longitude sign
            *format_longitude_for_nmea_gga_message(coord.lon),
            # Fix type, number of satellites, HDOP
            "1",
            "10",
            "1",
            # Altitude
            f"{alt:.2f}",
            "M",
            # Height of geoid, always null
            "",
            # Unit of height of geoid, always null
            "",
            # Age of RTK corrections, station ID
            "0.0",
            "0000",
        ),
    )
    return packet.render(newline=True)


def format_latitude_for_nmea_gga_message(lat: float) -> tuple[str, str]:
    """Formats a latitude in a way that is suitable for NMEA GGA messages.

    Args:
        lat: the latitude

    Returns:
        the formatted coordinate and the sign (North or South)
    """
    sign = "S" if lat < 0 else "N"
    deg, min_frac = divmod(abs(lat), 1)
    return f"{int(deg):02}{min_frac * 60:07.4f}", sign


def format_longitude_for_nmea_gga_message(lon: float) -> tuple[str, str]:
    """Formats a longitude in a way that is suitable for NMEA GGA messages.

    Args:
        lon: the longitude

    Returns:
        the formatted coordinate and the sign (East or West)
    """
    sign = "W" if lon < 0 else "E"
    deg, min_frac = divmod(abs(lon), 1)
    return f"{int(deg):03}{min_frac * 60:07.4f}", sign
