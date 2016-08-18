"""Distance calculation routines."""

from __future__ import absolute_import

from math import asin, cos, sin, sqrt
from .constants import PI_OVER_180, WGS84

__all__ = ("haversine", )


def haversine(first, second, datum=WGS84):
    """Returns the distance of two points given in spherical coordinates
    (latitude and longitude) using the Haversine formula.

    Parameters:
        first (GPSCoordinate): the first point
        second (GPSCoordinate): the second point

    Returns:
        float: the distance of the two points, in metres
    """
    first_lat = first.lat * PI_OVER_180
    second_lat = second.lat * PI_OVER_180
    lat_diff = first_lat - second_lat
    lon_diff = (first.lon - second.lon) * PI_OVER_180
    d = sin(lat_diff * 0.5) ** 2 + \
        cos(first_lat) * cos(second_lat) * sin(lon_diff * 0.5) ** 2
    return 2 * datum.MEAN_RADIUS_IN_METERS * asin(sqrt(d))
