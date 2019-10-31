"""Constants used in several places throughout the GPS package."""

__all__ = ("WGS84", "GPS_PI", "SPEED_OF_LIGHT_M_S", "SPEED_OF_LIGHT_KM_S")


class WGS84(object):
    """WGS84 ellipsoid model parameters for Earth."""

    ####################################################################
    # Defining parameters of WGS84 come first

    #: Equatorial radius of Earth in the WGS ellipsoid model
    EQUATORIAL_RADIUS_IN_METERS = 6378137.0

    #: Inverse flattening of Earth in the WGS ellipsoid model
    INVERSE_FLATTENING = 298.257223563

    #: Gravitational constant times Earth's mass
    GRAVITATIONAL_CONSTANT_TIMES_MASS = 3.986005e14

    #: Earth's rotation rate [rad/sec]
    ROTATION_RATE_IN_RADIANS_PER_SEC = 7.2921151467e-5

    ####################################################################
    # Non-defining parameters of WGS84 are below

    #: Flattening of Earth in the WGS ellipsoid model
    FLATTENING = 1.0 / INVERSE_FLATTENING

    #: Eccentricity of Earth in the WGS ellipsoid model
    ECCENTRICITY = (FLATTENING * (2 - FLATTENING)) ** 0.5

    #: Square of the eccentricity of Earth in the WGS ellipsoid model
    ECCENTRICITY_SQUARED = ECCENTRICITY ** 2

    #: Polar radius of Earth in the WGS ellipsoid model
    POLAR_RADIUS_IN_METERS = EQUATORIAL_RADIUS_IN_METERS * (1 - FLATTENING)

    #: Mean radius of Earth in the WGS ellipsoid model, as defined by IUGG
    MEAN_RADIUS_IN_METERS = (
        2 * EQUATORIAL_RADIUS_IN_METERS + POLAR_RADIUS_IN_METERS
    ) / 3


#: Value of pi used in some GPS-specific calculations.
GPS_PI = 3.1415926535898

#: Speed of light in km/s
SPEED_OF_LIGHT_KM_S = 299792.458

#: Speed of light in m/s
SPEED_OF_LIGHT_M_S = 299792458.0
