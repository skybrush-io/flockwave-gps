"""Unit tests for ``flockwave.gps.vectors``."""

from flockwave.gps.constants import WGS84
from flockwave.gps.vectors import ECEFCoordinate, \
    ECEFToGPSCoordinateTransformation, GPSCoordinate, \
    Vector3D, VelocityNED

import unittest


class JSONFormatTest(unittest.TestCase):
    """Unit tests for JSON conversion."""

    def test_vector3d_to_json_and_back(self):
        """Tests whether Vector3D instances can be converted into JSON and
        back.
        """
        vec = Vector3D(x=1, y=4, z=9)
        vec = Vector3D.from_json(vec.json)
        self.assertEqual(1, vec.x)
        self.assertEqual(4, vec.y)
        self.assertEqual(9, vec.z)

    def test_velocity_ned_to_json_and_back(self):
        """Tests whether VelocityNED instances can be converted into JSON and
        back.
        """
        vec = VelocityNED(north=1, east=4, down=9)
        vec = VelocityNED.from_json(vec.json)
        self.assertEqual(1, vec.north)
        self.assertEqual(4, vec.east)
        self.assertEqual(9, vec.down)

    def test_gps_coordinate_to_json_and_back(self):
        """Tests whether GPSCoordinate instances can be converted into JSON and
        back.
        """
        vec = GPSCoordinate(lat=1, lon=4, amsl=9)
        vec = GPSCoordinate.from_json(vec.json)
        self.assertEqual(1, vec.lat)
        self.assertEqual(4, vec.lon)
        self.assertEqual(9, vec.amsl)
        self.assertEqual(None, vec.agl)

        vec = GPSCoordinate(lat=1, lon=4, agl=9)
        vec = GPSCoordinate.from_json(vec.json)
        self.assertEqual(1, vec.lat)
        self.assertEqual(4, vec.lon)
        self.assertEqual(None, vec.amsl)
        self.assertEqual(9, vec.agl)


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
        gps_coord = GPSCoordinate(lat=49, lon=17, amsl=1000)
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
        self.assertAlmostEqual(1000, gps_coord.amsl, places=0)
        self.assertTrue(gps_coord.agl is None)
