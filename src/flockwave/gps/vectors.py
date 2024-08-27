"""Classes representing coordinates in various coordinate systems."""

from __future__ import annotations

from math import atan2, cos, degrees, radians, sin, sqrt
from typing import Any, Optional, TypeVar

from .constants import WGS84


__all__ = (
    "GPSCoordinate",
    "FlatEarthCoordinate",
    "FlatEarthToGPSCoordinateTransformation",
    "ECEFToGPSCoordinateTransformation",
    "PositionXYZ",
    "Vector3D",
    "VelocityNED",
    "VelocityXYZ",
)

C = TypeVar("C", bound="Vector3D")
C2 = TypeVar("C2", bound="GPSCoordinate")
C3 = TypeVar("C3", bound="FlatEarthCoordinate")


class AltitudeMixin:
    """Mixin class for objects that have an altitude component. Provides
    an ``amsl`` (altitude above mean sea level), an ``ahl`` (altitude above
    home level) and an ``agl`` (altitude above ground level) property with
    appropriate getters and setters.
    """

    _agl: Optional[float]
    _ahl: Optional[float]
    _amsl: Optional[float]

    def __init__(
        self,
        amsl: Optional[float] = None,
        ahl: Optional[float] = None,
        agl: Optional[float] = None,
    ):
        """Constructor."""
        self._agl = None
        self._ahl = None
        self._amsl = None
        self.agl = agl
        self.ahl = ahl
        self.amsl = amsl

    @property
    def agl(self) -> Optional[float]:
        """The relative altitude above ground level."""
        return self._agl

    @agl.setter
    def agl(self, value: Optional[float]) -> None:
        self._agl = float(value) if value is not None else None

    @property
    def ahl(self) -> Optional[float]:
        """The relative altitude above home level."""
        return self._ahl

    @ahl.setter
    def ahl(self, value: Optional[float]) -> None:
        self._ahl = float(value) if value is not None else None

    @property
    def amsl(self) -> Optional[float]:
        """The absolute altitude above mean sea level."""
        return self._amsl

    @amsl.setter
    def amsl(self, value: Optional[float]) -> None:
        self._amsl = float(value) if value is not None else None


class Vector3D:
    """Generic 3D vector."""

    _x: float
    _y: float
    _z: float

    @classmethod
    def from_json(cls, data):
        """Creates a generic 3D vector from its JSON representation."""
        return cls(x=float(data[0]), y=float(data[1]), z=float(data[2]))

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """Constructor.

        Parameters:
            x: the X coordinate
            y: the Y coordinate
            z: the Z coordinate
        """
        self._x, self._y, self._z = 0.0, 0.0, 0.0
        self.x = x
        self.y = y
        self.z = z

    def copy(self: C) -> C:
        """Creates a copy of this vector."""
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(self.x, self.y, self.z)

    def distance(self, other: Vector3D) -> float:
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

    def round(self, precision: int) -> None:
        """Rounds the coordinates of the vector to the given number of
        decimal digits.

        Parameters:
            precision: the number of decimal digits to round to
        """
        self._x = round(self._x, precision)
        self._y = round(self._y, precision)
        self._z = round(self._z, precision)

    def update(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        precision: Optional[int] = None,
    ) -> None:
        """Updates the coordinates of this object.

        Parameters:
            x: the new X coordinate; ``None`` means to leave the current value
                intact.
            y: the new Y coordinate; ``None`` means to leave the current value
                intact.
            z: the new Z coordinate; ``None`` means to leave the current value
                intact.
            precision: the number of decimal digits to round the coordinates
                to; ``None`` means to take the values as they are
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if z is not None:
            self.z = z
        if precision is not None:
            self.round(precision)

    def update_from(self, other: Vector3D, precision: Optional[int] = None) -> None:
        """Updates the coordinates of this object from another instance
        of Vector3D_.

        Parameters:
            other: the other object to copy the values from.
            precision: the number of decimal digits to round the coordinates to;
                ``None`` means to take the values as they are
        """
        # Don't use keyword arguments below; it would break VelocityNED
        self.update(other.x, other.y, other.z, precision=precision)

    @property
    def json(self) -> list[float]:
        """Returns the JSON representation of the coordinate."""
        return [self._x, self._y, self._z]

    @property
    def x(self) -> float:
        """The X coordinate."""
        return self._x

    @x.setter
    def x(self, value: float):
        self._x = float(value)

    @property
    def y(self) -> float:
        """The Y coordinate."""
        return self._y

    @y.setter
    def y(self, value: float):
        self._y = float(value)

    @property
    def z(self) -> float:
        """The Z coordinate."""
        return self._z

    @z.setter
    def z(self, value: float):
        self._z = float(value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Vector3D):
            return self._x == other._x and self._y == other._y and self._z == other._z
        else:
            return False

    def __floordiv__(self: C, other: float) -> C:
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(self._x // other, self._y // other, self._z // other)

    def __hash__(self):
        return hash((self._x, self._y, self._z))

    def __ifloordiv__(self, other: float) -> None:
        self._x //= other
        self._y //= other
        self._z //= other

    def __imul__(self, other: float) -> None:
        self._x *= other
        self._y *= other
        self._z *= other

    def __itruediv__(self, other: float) -> None:
        self._x /= other
        self._y /= other
        self._z /= other

    def __truediv__(self: C, other: float) -> C:
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(self.x / other, self.y / other, self.z / other)

    def __mul__(self: C, other: float) -> C:
        # Don't use keyword arguments below; it would break VelocityNED
        return self.__class__(self.x * other, self.y * other, self.z * other)

    def __repr__(self) -> str:
        return "{0.__class__.__name__}(x={0.x!r}, y={0.y!r}, z={0.z!r})".format(self)


class PositionXYZ(Vector3D):
    """Standard X-Y-Z position vector.

    The JSON representation of this class is conformant with the Flockwave
    protocol specification; therefore, the JSON representation stores positions
    as integers in mm instead of the raw floating-point values.
    """

    @classmethod
    def from_json(cls, data: list[float]):
        """Creates an XYZ position vector from its JSON representation."""
        return cls(x=data[0] * 1e-3, y=data[1] * 1e-3, z=data[2] * 1e-3)

    @Vector3D.json.getter
    def json(self) -> list[int]:
        """Returns the JSON representation of the coordinate."""
        return [
            int(round(self._x * 1e3)),
            int(round(self._y * 1e3)),
            int(round(self._z * 1e3)),
        ]


class VelocityXYZ(Vector3D):
    """Standard X-Y-Z velocity vector.

    The JSON representation of this class is conformant with the Flockwave
    protocol specification; therefore, the JSON representation stores velocities
    as integers in mm/s instead of the raw floating-point values.
    """

    @classmethod
    def from_json(cls, data: list[float]):
        """Creates an XYZ position vector from its JSON representation."""
        return cls(x=data[0] * 1e-3, y=data[1] * 1e-3, z=data[2] * 1e-3)

    @Vector3D.json.getter
    def json(self) -> list[int]:
        """Returns the JSON representation of the coordinate."""
        return [
            int(round(self._x * 1e3)),
            int(round(self._y * 1e3)),
            int(round(self._z * 1e3)),
        ]


class VelocityNED(Vector3D):
    """NED (North-East-Down) velocity vector.

    The property named ``north`` is aliased to ``x``; ``east`` is aliased
    to ``y`` and ``down`` is aliased to ``z``. The JSON representation of
    this class is conformant with the Flockwave protocol specification;
    therefore, the JSON representation stores velocities as integers in
    mm/s instead of the raw floating-point values.
    """

    @classmethod
    def from_json(cls, data: list[float]):
        """Creates a NED velocity vector from its JSON representation."""
        return cls(north=data[0] * 1e-3, east=data[1] * 1e-3, down=data[2] * 1e-3)

    def __init__(
        self, north: float = 0.0, east: float = 0.0, down: float = 0.0, **kwds
    ):
        """Constructor.

        Parameters:
            north: the north coordinate
            east: the east coordinate
            down: the down coordinate
        """
        super().__init__(x=north, y=east, z=down)

    def update(
        self,
        north: Optional[float] = None,
        east: Optional[float] = None,
        down: Optional[float] = None,
        precision: Optional[int] = None,
    ) -> None:
        """Updates the coordinates of this object.

        Parameters:
            north: the new north coordinate; ``None`` means to leave the current
                value intact.
            east: the new east coordinate; ``None`` means to leave the current
                value intact.
            down: the down coordinate; ``None`` means to leave the current value
                intact.
            precision: the number of decimal digits to round the coordinates
                to; ``None`` means to take the values as they are
        """
        super().update(north, east, down, precision=precision)

    @Vector3D.json.getter
    def json(self) -> list[int]:
        """Returns the JSON representation of the coordinate."""
        return [
            int(round(self._x * 1e3)),
            int(round(self._y * 1e3)),
            int(round(self._z * 1e3)),
        ]

    @property
    def north(self) -> float:
        """The north coordinate."""
        return self.x

    @north.setter
    def north(self, value: float) -> None:
        self.x = value

    @property
    def east(self) -> float:
        """The east coordinate."""
        return self.y

    @east.setter
    def east(self, value: float) -> None:
        self.y = value

    @property
    def down(self) -> float:
        """The down coordinate."""
        return self.z

    @down.setter
    def down(self, value: float) -> None:
        self.z = value

    def __repr__(self) -> str:
        return (
            "{0.__class__.__name__}(north={0.north!r}, east={0.east!r},"
            " down={0.down!r})".format(self)
        )


class ECEFCoordinate(Vector3D):
    """ECEF (Earth Centered, Earth Fixed) position vector. Coordinates must
    be given in metres.

    The JSON representation of this class is conformant with the Flockwave
    protocol specification; therefore, the JSON representation stores
    coordinates as integers in mm instead of the raw floating-point values.

    """

    @classmethod
    def from_json(cls, data):
        """Creates an ECEF coordinate from its JSON representation."""
        return cls(x=data[0] * 1e-3, y=data[1] * 1e-3, z=data[2] * 1e-3)

    @property
    def json(self) -> list[int]:
        """Returns the JSON representation of the coordinate."""
        return [
            int(round(self._x * 1e3)),
            int(round(self._y * 1e3)),
            int(round(self._z * 1e3)),
        ]


class GPSCoordinate(AltitudeMixin):
    """Class representing a GPS coordinate given with latitude, longitude
    and relative or MSL altitude.
    """

    _lat: float
    _lon: float

    @classmethod
    def from_json(cls, data):
        """Creates a GPS coordinate from its JSON representation."""
        length = len(data)
        return cls(
            lat=data[0] * 1e-7,
            lon=data[1] * 1e-7,
            amsl=data[2] * 1e-3 if length > 2 and data[2] is not None else None,
            ahl=data[3] * 1e-3 if length > 3 and data[3] is not None else None,
            agl=data[4] * 1e-3 if length > 4 and data[4] is not None else None,
        )

    def __init__(
        self,
        lat: float = 0.0,
        lon: float = 0.0,
        amsl: Optional[float] = None,
        ahl: Optional[float] = None,
        agl: Optional[float] = None,
    ):
        """Constructor.

        Parameters:
            lat: the latitude
            lon: the longitude
            amsl: the altitude above mean sea level, if known
            ahl: the altitude above home level, if known
            agl: the altitude above ground level, if known
        """
        AltitudeMixin.__init__(self, amsl=amsl, ahl=ahl, agl=agl)
        self._lat, self._lon = 0.0, 0.0
        self.lat = float(lat)
        self.lon = float(lon)

    def copy(self: C2) -> C2:
        """Returns a copy of the current GPS coordinate object."""
        return self.__class__(
            lat=self.lat, lon=self.lon, amsl=self.amsl, ahl=self.ahl, agl=self.agl
        )

    def format(self) -> str:
        """Formats the GPS coordinate as a string."""
        if self.amsl is not None:
            return f"{self.lat:.7f}°, {self.lon:.7f}°, {self.amsl:.1f}m AMSL"
        elif self.agl is not None:
            return f"{self.lat:.7f}°, {self.lon:.7f}°, {self.amsl:.1f}m AGL"
        else:
            return f"{self.lat:.7f}°, {self.lon:.7f}°"

    @property
    def json(self) -> list[int]:
        """Returns the JSON representation of the coordinate."""
        retval = [
            int(round(self._lat * 1e7)),
            int(round(self._lon * 1e7)),
            int(round(self._amsl * 1e3)) if self._amsl is not None else None,
            int(round(self._ahl * 1e3)) if self._ahl is not None else None,
        ]
        # for back-compatibility reasons we allow a list of only 4 elements,
        # and use 5-element list only when AGL altitude is explicitly given
        if self._agl is not None:
            retval.append(int(round(self._agl * 1e3)))

        return retval

    @property
    def lat(self) -> float:
        """The latitude of the coordinate."""
        return self._lat

    @lat.setter
    def lat(self, value: float) -> None:
        self._lat = float(value)

    @property
    def lon(self) -> float:
        """The longitude of the coordinate."""
        return self._lon

    @lon.setter
    def lon(self, value: float) -> None:
        self._lon = float(value)

    def round(self, precision: int) -> None:
        """Rounds the latitude and longitude of the position to the given
        number of decimal digits. Altitude is left intact.

        Parameters:
            precision: the number of decimal digits to round to
        """
        self._lat = round(self._lat, precision)
        self._lon = round(self._lon, precision)

    def update(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        amsl: Optional[float] = None,
        ahl: Optional[float] = None,
        agl: Optional[float] = None,
        precision: Optional[int] = None,
    ) -> None:
        """Updates the coordinates of this object.

        Parameters:
            lat: the new latitude; `None` means to leave the current value intact.
            lon: the new longitude; `None` means to leave the current value intact.
            amsl: the new altitude above mean sea level; `None` means to leave
                the current value intact.
            ahl: the new altitude above home level; `None` means to leave the
                current value intact.
            agl: the new altitude above ground level; `None` means to leave the
                current value intact.
            precision: the number of decimal digits to round the latitude and
                longitude to; ``None`` means to take the values as they are
        """
        if lat is not None:
            self.lat = lat
        if lon is not None:
            self.lon = lon
        if amsl is not None:
            self.amsl = amsl
        if ahl is not None:
            self.ahl = ahl
        if agl is not None:
            self.agl = agl
        if precision is not None:
            self.round(precision)

    def update_from(
        self, other: GPSCoordinate, precision: Optional[int] = None
    ) -> None:
        """Updates the coordinates of this object from another instance
        of GPSCoordinate_.

        Parameters:
            other: the other object to copy the values from.
            precision: the number of decimal digits to round the latitude and
                longitude to; ``None`` means to take the values as they are
        """
        self.update(
            lat=other.lat,
            lon=other.lon,
            amsl=other.amsl,
            ahl=other.ahl,
            agl=other.agl,
            precision=precision,
        )


class FlatEarthCoordinate(AltitudeMixin):
    """Class representing a coordinate given in flat Earth coordinates."""

    _x: float
    _y: float

    @classmethod
    def from_json(cls, data):
        """Creates a flat Earth coordinate from its JSON representation."""
        length = len(data)
        return cls(
            x=data[0] * 1e-3,
            y=data[1] * 1e-3,
            amsl=data[2] * 1e-3 if length > 2 and data[2] is not None else None,
            ahl=data[3] * 1e-3 if length > 3 and data[3] is not None else None,
            agl=data[4] * 1e-3 if length > 4 and data[4] is not None else None,
        )

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        amsl: Optional[float] = None,
        ahl: Optional[float] = None,
        agl: Optional[float] = None,
    ):
        """Constructor.

        Parameters:
            x: the X coordinate
            y: the Y coordinate
            amsl: the altitude above mean sea level, if known
            ahl: the altitude above home level, if known
            agl: the altitude above ground level, if known
        """
        AltitudeMixin.__init__(self, amsl=amsl, ahl=ahl, agl=agl)
        self._x, self._y = 0.0, 0.0
        self.x = x
        self.y = y

    def copy(self: C3) -> C3:
        """Returns a copy of the current flat Earth coordinate object."""
        return self.__class__(
            x=self.x, y=self.y, amsl=self.amsl, ahl=self.ahl, agl=self.agl
        )

    @property
    def json(self) -> list[int]:
        """Returns the JSON representation of the coordinate."""
        retval = [
            int(round(self._x * 1e3)),
            int(round(self._y * 1e3)),
            int(round(self._amsl * 1e3)) if self._amsl is not None else None,
            int(round(self._ahl * 1e3)) if self._ahl is not None else None,
        ]
        # for back-compatibility reasons we allow a list of only 4 elements,
        # and use 5-element list only when AGL altitude is explicitly given
        if self._agl is not None:
            retval.append(int(round(self._agl * 1e3)))

        return retval

    def round(self, precision: int) -> None:
        """Rounds the X and Y coordinates of the vector to the given
        number of decimal digits. Altitude is left intact.

        Parameters:
            precision (int): the number of decimal digits to round to
        """
        self._x = round(self._x, precision)
        self._y = round(self._y, precision)

    def update(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        amsl: Optional[float] = None,
        ahl: Optional[float] = None,
        agl: Optional[float] = None,
        precision: Optional[int] = None,
    ) -> None:
        """Updates the coordinates of this object.

        Parameters:
            x: the new X coordinate; `None` means to leave the current value intact.
            y: the new Y coordinate; `None` means to leave the current value intact.
            amsl: the new altitude above mean sea level; `None` means to leave
                the current value intact.
            ahl: the new altitude above home level; `None` means to leave the
                current value intact.
            agl: the new altitude above ground level; `None` means to leave the
                current value intact.
            precision: the number of decimal digits to round the X and Y
                coordinates to; ``None`` means to take the values as they are
        """
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if amsl is not None:
            self.amsl = amsl
        if ahl is not None:
            self.ahl = ahl
        if agl is not None:
            self.agl = agl
        if precision is not None:
            self.round(precision)

    def update_from(self, other: FlatEarthCoordinate, precision: Optional[int] = None):
        """Updates the coordinates of this object from another instance
        of FlatEarthCoordinate_.

        Parameters:
            other: the other object to copy the values from.
            precision: the number of decimal digits to round the X and Y
                coordinates to; ``None`` means to take the values as they are
        """
        self.update(
            x=other.x,
            y=other.y,
            amsl=other.amsl,
            ahl=other.ahl,
            agl=other.agl,
            precision=precision,
        )

    @property
    def x(self) -> float:
        """The X coordinate."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        self._x = float(value)

    @property
    def y(self) -> float:
        """The Y coordinate."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        self._y = float(value)


class ECEFToGPSCoordinateTransformation:
    """Transformation that converts ECEF coordinates to GPS coordinates
    and vice versa.
    """

    _eq_radius: float
    _polar_radius: float

    def __init__(self, radii: Optional[tuple[float, float]] = None):
        """Constructor.

        Parameters:
            radii: the equatorial and the polar radius, in metres. ``None``
                means to use the WGS84 ellipsoid.
        """
        self._eq_radius, self._polar_radius = 0.0, 0.0
        if radii is None:
            self.radii = WGS84.EQUATORIAL_RADIUS_IN_METERS, WGS84.POLAR_RADIUS_IN_METERS
        else:
            self.radii = radii

    @property
    def radii(self) -> tuple[float, float]:
        """The equatorial and polar radius of the ellipsoid, in metres."""
        return self._eq_radius, self._polar_radius

    @radii.setter
    def radii(self, value: tuple[float, float]) -> None:
        self._eq_radius = float(value[0])
        self._polar_radius = float(value[1])
        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculates some cached values that are re-used across different
        transformations.
        """
        self._eq_radius_sq = self._eq_radius**2
        self._polar_radius_sq = self._polar_radius**2
        self._ecc_sq = 1 - self._polar_radius_sq / self._eq_radius_sq
        self._ep_sq_times_polar_radius = (
            self._eq_radius_sq - self._polar_radius_sq
        ) / self._polar_radius
        self._ecc_sq_times_eq_radius = (
            self._eq_radius - self._polar_radius_sq / self._eq_radius
        )

    def to_ecef(self, coord: GPSCoordinate) -> ECEFCoordinate:
        """Converts the given GPS coordinates to ECEF coordinates.

        Parameters:
            coord: the coordinate to convert

        Returns:
            the converted coordinate
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

    def to_gps(self, coord: ECEFCoordinate) -> GPSCoordinate:
        """Converts the given ECEF coordinates to GPS coordinates.

        Parameters:
            coord: the coordinate to convert

        Returns:
            the converted coordinate
        """
        x, y, z = coord.x, coord.y, coord.z
        p = sqrt(x**2 + y**2)
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


class FlatEarthToGPSCoordinateTransformation:
    """Transformation that converts flat Earth coordinates to GPS
    coordinates and vice versa.
    """

    _origin_lat: float
    _origin_lon: float

    _xmul: float
    _ymul: float
    _zmul: float
    _sin_alpha: float
    _cos_alpha: float

    @staticmethod
    def _normalize_type(type: str) -> str:
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

    @classmethod
    def from_json(cls, json):
        """Constructs a transformation from its JSON representation previously
        obtained with the ``json`` property.
        """
        lon, lat = json["origin"]
        return cls(
            origin=GPSCoordinate(lon=lon, lat=lat),
            orientation=json["orientation"],
            type=json["type"],
        )

    def __init__(
        self,
        origin: Optional[GPSCoordinate] = None,
        orientation: float = 0,
        type: str = "nwu",
    ):
        """Constructor.

        Parameters:
            origin: origin of the flat Earth coordinate system, in GPS
                coordinates. Altitude component is ignored. The coordinate will
                be copied.
            orientation: orientation of the X axis of the coordinate system, in
                degrees, relative to North (zero degrees), increasing in CW
                direction.
            type: orientation of the coordinate system; can be `"neu"`
                (North-East-Up), `"nwu"` (North-West-Up), `"ned"`
                (North-East-Down) or `"nwd"` (North-West-Down)
        """
        self._origin_lat = 0
        self._origin_lon = 0
        self._orientation = float(orientation)
        self._type = self._normalize_type(type)

        self.origin = origin if origin is not None else GPSCoordinate()

    @property
    def json(self) -> dict[str, Any]:
        """Returns the JSON representation of the coordinate transformation."""
        return {
            "origin": [self._origin_lon, self._origin_lat],
            "orientation": str(self._orientation),
            "type": self._type,
        }

    @property
    def orientation(self) -> float:
        """The orientation of the X axis of the coordinate system, in degrees,
        relative to North (zero degrees), increasing in clockwise direction.
        """
        return self._orientation

    @orientation.setter
    def orientation(self, value: float) -> None:
        if self._orientation != value:
            self._orientation = value
            self._recalculate()

    @property
    def origin(self) -> GPSCoordinate:
        """The origin of the transformation, in GPS coordinates. The
        property uses a copy so you can safely modify the value returned
        by the getter without affecting the transformation.
        """
        return GPSCoordinate(lat=self._origin_lat, lon=self._origin_lon)

    @origin.setter
    def origin(self, value: GPSCoordinate) -> None:
        self._origin_lat = float(value.lat)
        self._origin_lon = float(value.lon)
        self._recalculate()

    @property
    def type(self) -> str:
        """The type of the coordinate system."""
        return self._type

    @type.setter
    def type(self, value: str) -> None:
        if self._type != value:
            self._type = value
            self._recalculate()

    def _recalculate(self) -> None:
        """Recalculates some cached values that are re-used across different
        transformations.
        """
        earth_radius = WGS84.EQUATORIAL_RADIUS_IN_METERS
        eccentricity_sq = WGS84.ECCENTRICITY_SQUARED

        origin_lat_in_radians = radians(self._origin_lat)

        x = 1 - eccentricity_sq * (sin(origin_lat_in_radians) ** 2)
        self._r1 = earth_radius * (1 - eccentricity_sq) / (x**1.5)
        self._r2_over_cos_origin_lat_in_radians = (
            earth_radius / sqrt(x) * cos(origin_lat_in_radians)
        )

        self._sin_alpha = sin(radians(self._orientation))
        self._cos_alpha = cos(radians(self._orientation))

        self._xmul = 1
        self._ymul = 1 if self._type[1] == "e" else -1
        self._zmul = 1 if self._type[2] == "u" else -1

    def to_flat_earth(self, coord: GPSCoordinate) -> FlatEarthCoordinate:
        """Converts the given GPS coordinates to flat Earth coordinates.

        Parameters:
            coord: the coordinate to convert

        Returns:
            the converted coordinate
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
            ahl=coord.ahl * self._zmul if coord.ahl is not None else None,
            agl=coord.agl * self._zmul if coord.agl is not None else None,
        )

    def to_gps(self, coord: FlatEarthCoordinate) -> GPSCoordinate:
        """Converts the given flat Earth coordinates to GPS coordinates.

        Parameters:
            coord: the coordinate to convert

        Returns:
            the converted coordinate
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
            ahl=coord.ahl * self._zmul if coord.ahl is not None else None,
            agl=coord.agl * self._zmul if coord.agl is not None else None,
        )
