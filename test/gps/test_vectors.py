"""Unit tests for ``flockwave.gps.vectors``."""

from flockwave.gps.constants import WGS84
from flockwave.gps.vectors import AltitudeReference, Altitude, \
    ECEFCoordinate, ECEFToGPSCoordinateTransformation, GPSCoordinate

import unittest


class ECEFToGPSCoordinateTransformationTest(unittest.TestCase):
    """Unit tests for the ECEFToGPSCoordinateTransformationTest_ class."""

    def test_ellipsoid_parameters(self):
        """Tests whether the ellipsoid parameters are taken from WGS84
        when no radii are given.
        """
        trans = ECEFToGPSCoordinateTransformation()
        self.assertAlmostEqual(
            (WGS84.EQUATORIAL_RADIUS_IN_METERS,
             WGS84.POLAR_RADIUS_IN_METERS),
            trans.radii
        )

    def test_custom_ellipsoid_parameters(self):
        """Tests whether custom ellipsoid parameters work."""
        trans = ECEFToGPSCoordinateTransformation((2, 2))
        self.assertEqual((2.0, 2.0), trans.radii)

    def test_to_ecef(self):
        """Unit tests for the ``to_ecef()`` method."""
        trans = ECEFToGPSCoordinateTransformation()

        # Calculations verified with:
        # http://www.oc.nps.edu/oc2902w/coord/llhxyz.htm
        gps_coord = GPSCoordinate(lat=49, lon=17, alt=Altitude.msl(1000))
        ecef_coord = trans.to_ecef(gps_coord)
        self.assertAlmostEqual(4009873, ecef_coord.x, places=0)
        self.assertAlmostEqual(1225941, ecef_coord.y, places=0)
        self.assertAlmostEqual(4791313, ecef_coord.z, places=0)

    def test_to_gps(self):
        """Unit tests for the ``to_gps()`` method."""
        trans = ECEFToGPSCoordinateTransformation()

        # Calculations verified with:
        # http://www.oc.nps.edu/oc2902w/coord/llhxyz.htm
        ecef_coord = ECEFCoordinate(x=4009873, y=1225941, z=4791313)
        gps_coord = trans.to_gps(ecef_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(1000, gps_coord.alt.value, places=0)
        self.assertAlmostEqual(AltitudeReference.MSL,
                               gps_coord.alt.reference)
