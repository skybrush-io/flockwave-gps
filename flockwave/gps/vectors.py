"""Classes representing coordinates in various coordinate systems."""

from math import atan2, cos, degrees, radians, sin, sqrt

from .constants import WGS84

__all__ = (
    "GPSCoordinate",
    "FlatEarthCoordinate",
    "FlatEarthToGPSCoordinateTransformation",
    "ECEFToGPSCoordinateTransformation",
)


class AltitudeMixin(object):
    """Mixin class for objects that have an altitude component. Provides
    an ``amsl`` (altitude above mean sea level) and an ``agl`` (altitude
    above ground level) property with appropriate getters and setters.
    """

    def __init__(self, amsl=None, agl=None):
        """Constructor."""
        self._agl = None
        self._amsl = None
        self.agl = agl
        self.amsl = amsl

    @property
    def agl(self):
        """The altitude above ground level."""
        return self._agl

    @agl.setter
    def agl(self, value):
        self._agl = float(value) if value is not None else None

    @property
    def amsl(self):
        """The altitude above mean sea level."""
        return self._amsl

    @amsl.setter
    def amsl(self, value):
        self._amsl = float(value) if value is not None else None


class Vector3D(object):
    """Generic 3D vector."""

    @classmethod
    def from_json(cls, data):
        """Creates a generic 3D vector from its JSON representation."""
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            z=float(data.get("z", 0.0)),
        )

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
                (self._x - other._x) ** 2
                + (self._y - other._y) ** 2
                + (self._z - other._z) ** 2
            ) ** 0.5
        else:
            raise TypeError("expected Vector3D, got {0!r}".format(type(other)))

    def round(self, precision):
        """Rounds the coordinates of the vector to the given number of
        decimal digits.

        Parameters:
            precision (int): the number of decimal digits to round to
        """
        self._x = round(self._x, precision)
        self._y = round(self._y, precision)
        self._z = round(self._z, precision)

    def update(self, x=None, y=None, z=None, precision=None):
        """Updates the coordinates of this object.

        Parameters:
            x (Optional[float]): the new X coordinate; ``None`` means to
                leave the current value intact.
            y (Optional[float]): the new Y coordinate; ``None`` means to
                leave the current value intact.
            z (Optional[float]): the Z coordinate; ``None`` means to
                leave the current value intact.
            precision (Optional[int]): the number of decimal digits to
                round the coordinates to; ``None`` means to take the
                values as they are
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if z is not None:
            self.z = z
        if precision is not None:
            self.round(precision)

    def update_from(self, other, precision=None):
        """Updates the coordinates of this object from another instance
        of Vector3D_.

        Parameters:
            other (Vector3D): the other object to copy the values from.
            precision (Optional[int]): the number of decimal digits to
                round the coordinates to; ``None`` means to take the
                values as they are
        """
        # Don't use keyword arguments below; it would break VelocityNED
        self.update(other.x, other.y, other.z, precision=precision)

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
        return self.__class__(self._x // other, self._y // other, self._z // other)

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
        return self.__class__(self.x / other, self.y / other, self.z / other)

    def __mul__(self, other):
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(self.x * other, self.y * other, self.z * other)

    def __repr__(self):
        return "{0.__class__.__name__}(x={0.x!r}, y={0.y!r}, z={0.z!r})".format(self)


class VelocityNED(Vector3D):
    """NED (North-East-Down) velocity vector.

    The property named ``north`` is aliased to ``x``; ``east`` is aliased
    to ``y`` and ``down`` is aliased to ``z``. The JSON representation of
    this class is updated to be conformant with the Flockwave protocol
    specification.
    """

    @classmethod
    def from_json(cls, data):
        """Creates a NED velocity vector from its JSON representation."""
        return cls(
            north=float(data.get("north", 0.0)),
            east=float(data.get("east", 0.0)),
            down=float(data.get("down", 0.0)),
        )

    def __init__(self, north=0.0, east=0.0, down=0.0, **kwds):
        """Constructor.

        Parameters:
            north (float): the north coordinate
            east (float): the east coordinate
            down (float): the down coordinate
        """
        super(VelocityNED, self).__init__(x=north, y=east, z=down)

    def update(self, north=None, east=None, down=None, precision=None):
        """Updates the coordinates of this object.

        Parameters:
            north (Optional[float]): the new north coordinate; ``None``
                means to leave the current value intact.
            east (Optional[float]): the new east coordinate; ``None`` means
                to leave the current value intact.
            down (Optional[float]): the down coordinate; ``None`` means to
                leave the current value intact.
            precision (Optional[int]): the number of decimal digits to
                round the coordinates to; ``None`` means to take the
                values as they are
        """
        super(VelocityNED, self).update(north, east, down, precision=precision)

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
        return (
            "{0.__class__.__name__}(north={0.north!r}, east={0.east!r},"
            " down={0.down!r})".format(self)
        )


class ECEFCoordinate(Vector3D):
    """ECEF (Earth Centered, Earth Fixed) position vector. Coordinates must
    be given in metres.
    """

    pass


class GPSCoordinate(AltitudeMixin):
    """Class representing a GPS coordinate given with latitude, longitude
    and relative or MSL altitude.
    """

    @classmethod
    def from_json(cls, data):
        """Creates a GPS coordinate from its JSON representation."""
        return cls(
            lat=float(data.get("lat", 0.0)),
            lon=float(data.get("lon", 0.0)),
            amsl=float(data["amsl"]) if "amsl" in data else None,
            agl=float(data["agl"]) if "agl" in data else None,
        )

    def __init__(self, lat=0.0, lon=0.0, amsl=None, agl=None):
        """Constructor.

        Parameters:
            lat (float): the latitude
            lon (float): the longitude
            amsl (Optional[float]): the altitude above mean sea level,
                if known
            agl (Optional[float]): the altitude above ground level, if
                known
        """
        AltitudeMixin.__init__(self, amsl=amsl, agl=agl)
        self._lat, self._lon = 0.0, 0.0
        self.lat = float(lat)
        self.lon = float(lon)

    def copy(self):
        """Returns a copy of the current GPS coordinate object."""
        return self.__class__(lat=self.lat, lon=self.lon, amsl=self.amsl, agl=self.agl)

    @property
    def json(self):
        """Returns the JSON representation of the coordinate."""
        result = {"lat": self._lat, "lon": self._lon}
        if self.amsl is not None:
            result["amsl"] = self._amsl
        if self.agl is not None:
            result["agl"] = self._agl
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

    def round(self, precision):
        """Rounds the latitude and longitude of the position to the given
        number of decimal digits. Altitude is left intact.

        Parameters:
            precision (int): the number of decimal digits to round to
        """
        self._lat = round(self._lat, precision)
        self._lon = round(self._lon, precision)

    def update(self, lat=None, lon=None, amsl=None, agl=None, precision=None):
        """Updates the coordinates of this object.

        Parameters:
            lat (Optional[float]): the new latitude; ``None`` means to
                leave the current value intact.
            lon (Optional[float]): the new longitude; ``None`` means to
                leave the current value intact.
            amsl (Optional[float]): the new altitude above mean sea level;
                ``None`` means to leave the current value intact.
            agl (Optional[float]): the new altitude above ground level;
                ``None`` means to leave the current value intact.
            precision (Optional[int]): the number of decimal digits to
                round the latitude and longitude to; ``None`` means to take
                the values as they are
        """
        if lat is not None:
            self.lat = lat
        if lon is not None:
            self.lon = lon
        if amsl is not None:
            self.amsl = amsl
        if agl is not None:
            self.agl = agl
        if precision is not None:
            self.round(precision)

    def update_from(self, other, precision=None):
        """Updates the coordinates of this object from another instance
        of GPSCoordinate_.

        Parameters:
            other (GPSCoordinate): the other object to copy the values from.
            precision (Optional[int]): the number of decimal digits to
                round the latitude and longitude to; ``None`` means to take
                the values as they are
        """
        self.update(
            lat=other.lat,
            lon=other.lon,
            amsl=other.amsl,
            agl=other.agl,
            precision=precision,
        )


class FlatEarthCoordinate(AltitudeMixin):
    """Class representing a coordinate given in flat Earth coordinates."""

    @classmethod
    def from_json(cls, data):
        """Creates a flat Earth coordinate from its JSON representation."""
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            amsl=float(data["amsl"]) if "amsl" in data else None,
            agl=float(data["agl"]) if "agl" in data else None,
        )

    def __init__(self, x=0.0, y=0.0, amsl=None, agl=None):
        """Constructor.

        Parameters:
            x (float): the X coordinate
            y (float): the Y coordinate
            amsl (Optional[float]): the altitude above mean sea level,
                if known
            agl (Optional[float]): the altitude above ground level, if
                known
        """
        AltitudeMixin.__init__(self, amsl=amsl, agl=agl)
        self._x, self._y = 0.0, 0.0
        self.x = x
        self.y = y

    def copy(self):
        """Returns a copy of the current flat Earth coordinate object."""
        return self.__class__(x=self.x, y=self.y, amsl=self.amsl, agl=self.agl)

    @property
    def json(self):
        """Returns the JSON representation of the coordinate."""
        result = {"x": self._x, "y": self._y}
        if self.amsl is not None:
            result["amsl"] = self._amsl
        if self.agl is not None:
            result["agl"] = self._agl
        return result

    def round(self, precision):
        """Rounds the X and Y coordinates of the vector to the given
        number of decimal digits. Altitude is left intact.

        Parameters:
            precision (int): the number of decimal digits to round to
        """
        self._x = round(self._x, precision)
        self._y = round(self._y, precision)

    def update(self, x=None, y=None, amsl=None, agl=None, precision=None):
        """Updates the coordinates of this object.

        Parameters:
            x (Optional[float]): the new X coordinate; ``None`` means to
                leave the current value intact.
            y (Optional[float]): the new Y coordinate; ``None`` means to
                leave the current value intact.
            amsl (Optional[float]): the new altitude above mean sea level;
                ``None`` means to leave the current value intact.
            agl (Optional[float]): the new altitude above ground level;
                ``None`` means to leave the current value intact.
            precision (Optional[int]): the number of decimal digits to
                round the X and Y to; ``None`` means to take the
                values as they are
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if amsl is not None:
            self.amsl = amsl
        if agl is not None:
            self.agl = agl
        if precision is not None:
            self.round(precision)

    def update_from(self, other, precision=None):
        """Updates the coordinates of this object from another instance
        of FlatEarthCoordinate_.

        Parameters:
            other (FlatEarthCoordinate): the other object to copy the
                values from.
            precision (Optional[int]): the number of decimal digits to
                round the X and Y to; ``None`` means to take the
                values as they are
        """
        self.update(
            x=other.x, y=other.y, amsl=other.amsl, agl=other.agl, precision=precision
        )

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
            self.radii = WGS84.EQUATORIAL_RADIUS_IN_METERS, WGS84.POLAR_RADIUS_IN_METERS
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
        self._ep_sq_times_polar_radius = (
            self._eq_radius_sq - self._polar_radius_sq
        ) / self._polar_radius
        self._ecc_sq_times_eq_radius = (
            self._eq_radius - self._polar_radius_sq / self._eq_radius
        )

    def to_ecef(self, coord):
        """Converts the given GPS coordinates to ECEF coordinates.

        Parameters:
            coord (GPSCoordinate): the coordinate to convert

        Returns:
            ECEFCoordinate: the converted coordinate
        """
        if coord.amsl is None:
            raise ValueError(
                "GPS coordinates need an altitude relative " "to the mean sea level"
            )

        lat, lon = radians(coord.lat), radians(coord.lon)
        height = coord.amsl

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
        lat = atan2(
            z + self._ep_sq_times_polar_radius * (sin(th) ** 3),
            p - self._ecc_sq_times_eq_radius * (cos(th) ** 3),
        )
        n = self._eq_radius / sqrt(1 - self._ecc_sq * (sin(lat) ** 2))
        amsl = p / cos(lat) - n
        lat, lon = degrees(lat), degrees(lon)
        return GPSCoordinate(lat=lat, lon=lon, amsl=amsl)


class FlatEarthToGPSCoordinateTransformation(object):
    """Transformation that converts flat Earth coordinates to GPS
    coordinates and vice versa.
    """

    @staticmethod
    def _normalize_type(type):
        """Returns the normalized name of the given coordinate system type.

        Raises:
            ValueError: if type is not a known coordinate system name
        """
        normalized = None
        if len(type) == 3:
            type = type.lower()
            if type in ("neu", "nwu", "ned", "nwd"):
                normalized = type

        if not normalized:
            raise ValueError("unknown coordinate system type: {0!r}".format(type))

        return normalized

    def __init__(self, origin=None, orientation=0, type="nwu"):
        """Constructor.

        Parameters:
            origin (GPSCoordinate): origin of the flat Earth coordinate
                system, in GPS coordinates. Altitude component is ignored.
                The coordinate will be copied.
            orientation (float): orientation of the X axis of the coordinate
                system, in degrees, relative to North (zero degrees),
                increasing in CW direction.
            type (str): orientation of the coordinate system; can be `"neu"`
                (North-East-Up), `"nwu"` (North-West-Up), `"ned"`
                (North-East-Down) or `"nwd"` (North-West-Down)
        """
        self._origin_lat = None
        self._origin_lon = None
        self._orientation = float(orientation)
        self._type = self._normalize_type(type)

        self.origin = origin if origin is not None else GPSCoordinate()

    @property
    def orientation(self):
        """The orientation of the X axis of the coordinate system, in degrees,
        relative to North (zero degrees), increasing in clockwise direction.
        """
        return self._orientation

    @orientation.setter
    def orientation(self, value):
        if self._orientation != value:
            self._orientation = value
            self._recalculate()

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

    @property
    def type(self):
        """The type of the coordinate system."""
        return self._type

    @type.setter
    def type(self, value):
        if self._type != value:
            self._type = value
            self._recalculate()

    def _recalculate(self):
        """Recalculates some cached values that are re-used across different
        transformations.
        """
        earth_radius = WGS84.EQUATORIAL_RADIUS_IN_METERS
        eccentricity_sq = WGS84.ECCENTRICITY_SQUARED

        origin_lat_in_radians = radians(self._origin_lat)

        x = 1 - eccentricity_sq * (sin(origin_lat_in_radians) ** 2)
        self._r1 = earth_radius * (1 - eccentricity_sq) / (x ** 1.5)
        self._r2_over_cos_origin_lat_in_radians = (
            earth_radius / sqrt(x) * cos(origin_lat_in_radians)
        )

        self._sin_alpha = sin(radians(self._orientation))
        self._cos_alpha = cos(radians(self._orientation))

        self._xmul = 1
        self._ymul = 1 if self._type[1] == "e" else -1
        self._zmul = 1 if self._type[2] == "u" else -1

    def to_flat_earth(self, coord):
        """Converts the given GPS coordinates to flat Earth coordinates.

        Parameters:
            coord (GPSCoordinate): the coordinate to convert

        Returns:
            FlatEarthCoordinate: the converted coordinate
        """
        x, y = (
            radians(coord.lat - self._origin_lat) * self._r1,
            radians(coord.lon - self._origin_lon)
            * self._r2_over_cos_origin_lat_in_radians,
        )
        x, y = (
            x * self._cos_alpha + y * self._sin_alpha,
            -x * self._sin_alpha + y * self._cos_alpha,
        )
        return FlatEarthCoordinate(
            x=x * self._xmul,
            y=y * self._ymul,
            amsl=coord.amsl * self._zmul if coord.amsl is not None else None,
            agl=coord.agl * self._zmul if coord.agl is not None else None,
        )

    def to_gps(self, coord):
        """Converts the given flat Earth coordinates to GPS coordinates.

        Parameters:
            coord (FlatEarthCoordinate): the coordinate to convert

        Returns:
            GPSCoordinate: the converted coordinate
        """
        x, y = (coord.x * self._xmul, coord.y * self._ymul)

        x, y = (
            x * self._cos_alpha - y * self._sin_alpha,
            x * self._sin_alpha + y * self._cos_alpha,
        )

        lat = degrees(x / self._r1)
        lon = degrees(y / self._r2_over_cos_origin_lat_in_radians)

        return GPSCoordinate(
            lat=lat + self._origin_lat,
            lon=lon + self._origin_lon,
            amsl=coord.amsl * self._zmul if coord.amsl is not None else None,
            agl=coord.agl * self._zmul if coord.agl is not None else None,
        )
