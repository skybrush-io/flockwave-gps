"""Distance calculation routines."""

from math import asin, cos, radians, sin, sqrt

from .constants import WGS84
from .vectors import GPSCoordinate

__all__ = ("haversine",)


def haversine(first: GPSCoordinate, second: GPSCoordinate, datum=WGS84) -> float:
    """Returns the distance of two points given in spherical coordinates
    (latitude and longitude) using the Haversine formula.

    Parameters:
        first: the first point
        second: the second point

    Returns:
        the distance of the two points, in metres
    """
    first_lat = radians(first.lat)
    second_lat = radians(second.lat)
    lat_diff = first_lat - second_lat
    lon_diff = radians(first.lon - second.lon)
    d = (
        sin(lat_diff * 0.5) ** 2
        + cos(first_lat) * cos(second_lat) * sin(lon_diff * 0.5) ** 2
    )
    return 2 * datum.MEAN_RADIUS_IN_METERS * asin(sqrt(d))
