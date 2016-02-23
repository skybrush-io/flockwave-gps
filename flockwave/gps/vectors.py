"""Classes representing coordinates in various coordinate systems."""

from __future__ import absolute_import, division

from .constants import PI_OVER_180, WGS84
from enum import Enum
from math import atan2, cos, pi, sin, sqrt


__all__ = ("AltitudeReference", "Altitude",
           "GPSCoordinate", "FlatEarthCoordinate",
           "FlatEarthToGPSCoordinateTransformation")


AltitudeReference = Enum("AltitudeReference", "RELATIVE MSL")


class Altitude(object):
    """Class representing an altitude."""

    @classmethod
    def msl(cls, value):
        """Convenience constructor for an altitude above mean sea level.

        Parameters:
            value (float): the altitude above mean sea level

        Returns:
            Altitude: an appropriate altitude object
        """
        return cls(value, reference=AltitudeReference.MSL)

    @classmethod
    def relative(cls, value):
        """Convenience constructor for a relative altitude.

        Parameters:
            value (float): the relative altitude

        Returns:
            Altitude: an appropriate altitude object
        """
        return cls(value, reference=AltitudeReference.RELATIVE)

    def __init__(self, value=0.0, reference=AltitudeReference.MSL):
        """Constructor.

        Parameters:
            value (float): the altitude
            reference (AltitudeReference): the reference point of the
                altitude
        """
        self._value = 0.0
        self.value = value
        self.reference = reference

    def copy(self):
        """Returns a copy of the current altitude object."""
        return self.__class__(value=self._value, reference=self.reference)

    def update_from(self, other):
        """Updates this altitude object from another one.

        Parameters:
            other (Altitude): the altitude object to update this one from
        """
        self._value = other._value
        self.reference = other.reference

    @property
    def value(self):
        """The value component of the altitude, in metres."""
        return self._value

    @value.setter
    def value(self, value):
        self._value = float(value)

    def __repr__(self):
        return "{0.__class__.__name__}(value={0.value}, "\
               "reference={0.reference})".format(self)


class AltitudeMixin(object):
    """Mixin class for objects that have an altitude component. Provides
    an ``alt`` property with appropriate getters and setters.
    """

    def __init__(self):
        """Constructor."""
        self._alt = None

    @property
    def alt(self):
        """The altitude of the coordinate. The getter will return a copy
        of the Altitude_ object embedded in this coordinate; similarly,
        the setter will make a copy of the altitude being set. This means
        that you can safely modify the Altitude_ objects outside this
        class; these modifications will not affect the coordinate itself.
        """
        return self._alt.copy() if self._alt is not None else None

    @alt.setter
    def alt(self, value):
        if value is None:
            self._alt = None
        elif self._alt is None:
            self._alt = value.copy()
        else:
            self._alt.update_from(value)


class ECEFCoordinate(object):
    """ECEF (Earth Centered, Earth Fixed) position vector. Coordinates must
    be given in metres.
    """

    def __init__(self, x=0.0, y=0.0, z=0.0):
        """Constructor.

        Parameters:
            x (float): the X coordinate
            y (float): the Y coordinate
            z (float): the Z coordinate
        """
        self._x, self._y, self._z = 0.0, 0.0, 0.0
        self.x = x
        self.y = y
        self.z = z

    def distance(self, other):
        """Returns the distance between this position and another ECEF
        position vector.
        """
        if isinstance(other, ECEFCoordinate):
            return (
                (self._x - other._x) ** 2 +
                (self._y - other._y) ** 2 +
                (self._z - other._z) ** 2
            ) ** 0.5
        else:
            raise TypeError("expected ECEFPosition, got {0!r}".
                            format(type(other)))

    @property
    def x(self):
        """The X coordinate."""
        return self._x

    @x.setter
    def x(self, value):
        self._x = float(value)

    @property
    def y(self):
        """The Y coordinate."""
        return self._y

    @y.setter
    def y(self, value):
        self._y = float(value)

    @property
    def z(self):
        """The Z coordinate."""
        return self._z

    @z.setter
    def z(self, value):
        self._z = float(value)

    def __floordiv__(self, other):
        return self.__class__(
            x=self._x // other, y=self._y // other, z=self._z // other
        )

    def __ifloordiv__(self, other):
        self._x //= other
        self._y //= other
        self._z //= other

    def __imul__(self, other):
        self._x *= other
        self._y *= other
        self._z *= other

    def __itruediv__(self, other):
        self._x /= other
        self._y /= other
        self._z /= other

    def __truediv__(self, other):
        return self.__class__(
            x=self.x / other, y=self.y / other, z=self.z / other
        )

    def __mul__(self, other):
        return self.__class__(
            x=self.x * other, y=self.y * other, z=self.z * other
        )


class GPSCoordinate(AltitudeMixin):
    """Class representing a GPS coordinate given with latitude, longitude
    and relative or MSL altitude.
    """

    def __init__(self, lat=0.0, lon=0.0, alt=None):
        """Constructor.

        Parameters:
            lat (float): the latitude
            lon (float): the longitude
            alt (Altitude or None): the altitude (relative or MSL);
                ``None`` if not known
        """
        AltitudeMixin.__init__(self)
        self._lat, self._lon = 0.0, 0.0
        self.lat = float(lat)
        self.lon = float(lon)
        self.alt = alt

    def copy(self):
        """Returns a copy of the current GPS coordinate object."""
        return self.__class__(
            lat=self.lat, lon=self.lon,
            alt=self.alt.copy() if self.alt is not None else None
        )

    @property
    def lat(self):
        """The latitude of the coordinate."""
        return self._lat

    @lat.setter
    def lat(self, value):
        self._lat = float(value)

    @property
    def lon(self):
        """The longitude of the coordinate."""
        return self._lon

    @lon.setter
    def lon(self, value):
        self._lon = float(value)

    def update(self, lat=None, lon=None, alt=None):
        """Updates the coordinates of this object.

        Parameters:
            lat (float or None): the new latitude; ``None`` means to
                leave the current value intact.
            lon (float or None): the new longitude; ``None`` means to
                leave the current value intact.
            alt (Altitude or None): the new altitude; ``None`` means to
                leave the current value intact.
        """
        if lat is not None:
            self.lat = lat
        if lon is not None:
            self.lon = lon
        if alt is not None:
            self.alt = alt

    def update_from(self, other):
        """Updates the coordinates of this object from another instance
        of GPSCoordinate_.

        Parameters:
            other (GPSCoordinate): the other object to copy the values from.
        """
        self.update(lat=other.lat, lon=other.lon, alt=other._alt)


class FlatEarthCoordinate(AltitudeMixin):
    """Class representing a coordinate given in flat Earth coordinates."""

    def __init__(self, x=0.0, y=0.0, alt=None):
        """Constructor.

        Parameters:
            x (float): the X coordinate
            y (float): the Y coordinate
            alt (Altitude or None): the altitude (relative or MSL);
                ``None`` if not known
        """
        AltitudeMixin.__init__(self)
        self._x, self._y = 0.0, 0.0
        self.x = x
        self.y = y

    def copy(self):
        """Returns a copy of the current flat Earth coordinate object."""
        return self.__class__(
            x=self.x, y=self.y,
            alt=self.alt.copy() if self.alt is not None else None
        )

    def update(self, x=None, y=None, alt=None):
        """Updates the coordinates of this object.

        Parameters:
            x (float or None): the new X coordinate; ``None`` means to
                leave the current value intact.
            y (float or None): the new Y coordinate; ``None`` means to
                leave the current value intact.
            alt (Altitude or None): the new altitude; ``None`` means to
                leave the current value intact.
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if alt is not None:
            self.alt = alt

    def update_from(self, other):
        """Updates the coordinates of this object from another instance
        of FlatEarthCoordinate_.

        Parameters:
            other (FlatEarthCoordinate): the other object to copy the
                values from.
        """
        self.update(x=other.x, y=other.y, alt=other._alt)

    @property
    def x(self):
        """The X coordinate."""
        return self._x

    @x.setter
    def x(self, value):
        self._x = float(value)

    @property
    def y(self):
        """The Y coordinate."""
        return self._y

    @y.setter
    def y(self, value):
        self._y = float(value)


class ECEFToGPSCoordinateTransformation(object):
    """Transformation that converts ECEF coordinates to GPS coordinates
    and vice versa.
    """

    def __init__(self, radii=None):
        """Constructor.

        Parameters:
            radii (float, float): the equatorial and the polar radius, in
                metres. ``None`` means to use the WGS84 ellipsoid.
        """
        self._eq_radius, self._polar_radius = 0.0, 0.0
        if radii is None:
            self.radii = WGS84.EQUATORIAL_RADIUS_IN_METERS, \
                WGS84.POLAR_RADIUS_IN_METERS
        else:
            self.radii = radii

    @property
    def radii(self):
        """The equatorial and polar radius of the ellipsoid, in metres."""
        return self._eq_radius, self._polar_radius

    @radii.setter
    def radii(self, value):
        self._eq_radius = float(value[0])
        self._polar_radius = float(value[1])
        self._recalculate()

    def _recalculate(self):
        """Recalculates some cached values that are re-used across different
        transformations.
        """
        self._eq_radius_sq = self._eq_radius ** 2
        self._polar_radius_sq = self._polar_radius ** 2
        self._ecc_sq = 1 - self._polar_radius_sq / self._eq_radius_sq
        self._ep_sq_times_polar_radius = \
            (self._eq_radius_sq - self._polar_radius_sq) / self._polar_radius
        self._ecc_sq_times_eq_radius = \
            self._eq_radius - self._polar_radius_sq / self._eq_radius

    def to_ecef(self, coord):
        """Converts the given GPS coordinates to ECEF coordinates.

        Parameters:
            coord (ECEFCoordinate): the coordinate to convert

        Returns:
            GPSCoordinate: the converted coordinate
        """
        raise NotImplementedError

    def to_gps(self, coord):
        """Converts the given ECEF coordinates to GPS coordinates.

        Parameters:
            coord (ECEFCoordinate): the coordinate to convert

        Returns:
            GPSCoordinate: the converted coordinate
        """
        x, y, z = coord.x, coord.y, coord.z
        p = sqrt(x ** 2 + y ** 2)
        th = atan2(self._eq_radius * z, self._polar_radius * p)
        lon = atan2(y, x)
        lat = atan2(z + self._ep_sq_times_polar_radius * (sin(th) ** 3),
                    p - self._ecc_sq_times_eq_radius * (cos(th) ** 3))
        n = self._eq_radius / sqrt(1 - self._ecc_sq * (sin(lat) ** 2))
        alt = p / cos(lat) - n
        lat = lat * 180 / pi
        lon = lon * 180 / pi
        return GPSCoordinate(lat=lat, lon=lon, alt=Altitude.msl(alt))


class FlatEarthToGPSCoordinateTransformation(object):
    """Transformation that converts flat Earth coordinates to GPS
    coordinates and vice versa.
    """

    def __init__(self, origin=None):
        """Constructor.

        Parameters:
            origin (GPSCoordinate): origin of the flat Earth coordinate
                system, in GPS coordinates. Altitude component is ignored.
                The coordinate will be copied.
        """
        self._origin_lat = None
        self._origin_lon = None
        self.origin = origin if origin is not None else GPSCoordinate()

    @property
    def origin(self):
        """The origin of the transformation, in GPS coordinates. The
        property uses a copy so you can safely modify the value returned
        by the getter without affecting the transformation.
        """
        return GPSCoordinate(lat=self._origin_lat, lon=self._origin_lon)

    @origin.setter
    def origin(self, value):
        self._origin_lat = float(value.lat)
        self._origin_lon = float(value.lon)
        self._recalculate()

    def _recalculate(self):
        """Recalculates some cached values that are re-used across different
        transformations.
        """
        self._pi_over_180 = pi / 180

        earth_radius = WGS84.EQUATORIAL_RADIUS_IN_METERS
        eccentricity_sq = WGS84.ECCENTRICITY_SQUARED

        origin_lat_in_radians = self._origin_lat * self._pi_over_180
        self._cos_origin_lat_in_radians = cos(origin_lat_in_radians)

        x = (1 - eccentricity_sq * (sin(origin_lat_in_radians) ** 2))
        self._r1 = earth_radius * (1 - eccentricity_sq) / (x ** 1.5)
        self._r2 = earth_radius / sqrt(x)

    def to_flat_earth(self, coord):
        """Converts the given GPS coordinates to flat Earth coordinates.

        Parameters:
            coord (GPSCoordinate): the coordinate to convert

        Returns:
            FlatEarthCoordinate: the converted coordinate
        """
        raise NotImplementedError

    def to_gps(self, coord):
        """Converts the given flat Earth coordinates to GPS coordinates.

        Parameters:
            coord (FlatEarthCoordinate): the coordinate to convert

        Returns:
            GPSCoordinate: the converted coordinate
        """
        lat_in_radians = coord.x / self._r1
        lon_in_radians = coord.y / self._r2 / self._cos_origin_lat_in_radians
        return GPSCoordinate(
            lat=lat_in_radians / PI_OVER_180 + self._origin_lat,
            lon=lon_in_radians / PI_OVER_180 + self._origin_lon,
            altRel=coord.altRel,
            altMSL=coord.altMSL
        )
