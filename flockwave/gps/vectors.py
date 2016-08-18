"""Classes representing coordinates in various coordinate systems."""

from __future__ import absolute_import, division

from .constants import PI_OVER_180, WGS84
from enum import Enum
from math import atan2, cos, pi, sin, sqrt


__all__ = ("AltitudeReference", "Altitude",
           "GPSCoordinate", "FlatEarthCoordinate",
           "FlatEarthToGPSCoordinateTransformation",
           "ECEFToGPSCoordinateTransformation")


class AltitudeReference(Enum):
    """Altitude reference point types for the Altitude_ class."""

    HOME = "home"
    MSL = "msl"


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
    def relative_to_home(cls, value):
        """Convenience constructor for a relative-to-home altitude.

        Parameters:
            value (float): the relative-to-home altitude

        Returns:
            Altitude: an appropriate altitude object
        """
        return cls(value, reference=AltitudeReference.HOME)

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

    @property
    def json(self):
        """Returns the JSON representation of the altitude."""
        return {
            "reference": self.reference.value,
            "value": self._value
        }

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


class Vector3D(object):
    """Generic 3D vector."""

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

    def copy(self):
        """Creates a copy of this vector."""
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(self.x, self.y, self.z)

    def distance(self, other):
        """Returns the distance between this position and another 3D
        vector.
        """
        if isinstance(other, Vector3D):
            return (
                (self._x - other._x) ** 2 +
                (self._y - other._y) ** 2 +
                (self._z - other._z) ** 2
            ) ** 0.5
        else:
            raise TypeError("expected Vector3D, got {0!r}".
                            format(type(other)))

    def update(self, x=None, y=None, z=None):
        """Updates the coordinates of this object.

        Parameters:
            x (Optional[float]): the new X coordinate; ``None`` means to
                leave the current value intact.
            y (Optional[float]): the new Y coordinate; ``None`` means to
                leave the current value intact.
            z (Optional[float]): the Z coordinate; ``None`` means to
                leave the current value intact.
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if z is not None:
            self.z = z

    def update_from(self, other):
        """Updates the coordinates of this object from another instance
        of Vector3D_.

        Parameters:
            other (Vector3D): the other object to copy the values from.
        """
        # Don't use keyword arguments below; it would break VelocityNED
        self.update(other.x, other.y, other.z)

    @property
    def json(self):
        """Returns the JSON representation of the coordinate."""
        return {"x": self._x, "y": self._y, "z": self._z}

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
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(
            self._x // other, self._y // other, self._z // other
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
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(
            self.x / other, self.y / other, self.z / other
        )

    def __mul__(self, other):
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(
            self.x * other, self.y * other, self.z * other
        )

    def __repr__(self):
        return "{0.__class__.__name__}(x={0.x!r}, y={0.y!r}, z={0.z!r})"\
            .format(self)


class VelocityNED(Vector3D):
    """NED (North-East-Down) velocity vector.

    The property named ``north`` is aliased to ``x``; ``east`` is aliased
    to ``y`` and ``down`` is aliased to ``z``. The JSON representation of
    this class is updated to be conformant with the Flockwave protocol
    specification.
    """

    def __init__(self, north=0.0, east=0.0, down=0.0, **kwds):
        """Constructor.

        Parameters:
            north (float): the north coordinate
            east (float): the east coordinate
            down (float): the down coordinate
        """
        super(VelocityNED, self).__init__(x=north, y=east, z=down)

    def update(self, north=None, east=None, down=None):
        """Updates the coordinates of this object.

        Parameters:
            north (Optional[float]): the new north coordinate; ``None``
                means to leave the current value intact.
            east (Optional[float]): the new east coordinate; ``None`` means
                to leave the current value intact.
            down (Optional[float]): the down coordinate; ``None`` means to
                leave the current value intact.
        """
        super(VelocityNED, self).update(north, east, down)

    @Vector3D.json.getter
    def json(self):
        """Returns the JSON representation of the coordinate."""
        return {"north": self._x, "east": self._y, "down": self._z}

    @property
    def north(self):
        """The north coordinate."""
        return self.x

    @north.setter
    def north(self, value):
        self.x = value

    @property
    def east(self):
        """The east coordinate."""
        return self.y

    @east.setter
    def east(self, value):
        self.y = value

    @property
    def down(self):
        """The down coordinate."""
        return self.z

    @down.setter
    def down(self, value):
        self.z = value

    def __repr__(self):
        return "{0.__class__.__name__}(north={0.north!r}, east={0.east!r},"\
            " down={0.down!r})".format(self)


class ECEFCoordinate(Vector3D):
    """ECEF (Earth Centered, Earth Fixed) position vector. Coordinates must
    be given in metres.
    """

    pass


class GPSCoordinate(AltitudeMixin):
    """Class representing a GPS coordinate given with latitude, longitude
    and relative or MSL altitude.
    """

    def __init__(self, lat=0.0, lon=0.0, alt=None):
        """Constructor.

        Parameters:
            lat (float): the latitude
            lon (float): the longitude
            alt (Optional[Altitude]): the altitude (relative or MSL);
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
    def json(self):
        """Returns the JSON representation of the coordinate."""
        result = {"lat": self._lat, "lon": self._lon}
        if self.alt is not None:
            result["alt"] = self._alt.json
        return result

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
            lat (Optional[float]): the new latitude; ``None`` means to
                leave the current value intact.
            lon (Optional[float]): the new longitude; ``None`` means to
                leave the current value intact.
            alt (Optional[Altitude]): the new altitude; ``None`` means to
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
            alt (Optional[Altitude]): the altitude (relative or MSL);
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

    @property
    def json(self):
        """Returns the JSON representation of the coordinate."""
        result = {"x": self._x, "y": self._y}
        if self.alt is not None:
            result["alt"] = self._alt.json
        return result

    def update(self, x=None, y=None, alt=None):
        """Updates the coordinates of this object.

        Parameters:
            x (Optional[float]): the new X coordinate; ``None`` means to
                leave the current value intact.
            y (Optional[float]): the new Y coordinate; ``None`` means to
                leave the current value intact.
            alt (Optional[Altitude]): the new altitude; ``None`` means to
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
            coord (GPSCoordinate): the coordinate to convert

        Returns:
            ECEFCoordinate: the converted coordinate
        """
        if coord.alt is None or coord.alt.reference != AltitudeReference.MSL:
            raise ValueError("GPS coordinates need an altitude relative "
                             "to the mean sea level")

        lat, lon = coord.lat * PI_OVER_180, coord.lon * PI_OVER_180
        height = coord.alt.value

        n = self._eq_radius / sqrt(1 - self._ecc_sq * (sin(lat) ** 2))
        cos_lat = cos(lat)
        x = (n + height) * cos_lat * cos(lon)
        y = (n + height) * cos_lat * sin(lon)
        z = (n * (1 - self._ecc_sq) + height) * sin(lat)
        return ECEFCoordinate(x=x, y=y, z=z)

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
        lat = lat / PI_OVER_180
        lon = lon / PI_OVER_180
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
            alt=coord.alt.copy() if coord.alt is not None else None
        )
