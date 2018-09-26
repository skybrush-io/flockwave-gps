"""Unit tests for ``flockwave.gps.vectors``."""

from flockwave.gps.constants import WGS84
from flockwave.gps.vectors import (
    ECEFCoordinate, ECEFToGPSCoordinateTransformation,
    FlatEarthCoordinate, FlatEarthToGPSCoordinateTransformation,
    GPSCoordinate, Vector3D, VelocityNED
)

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
    """Unit tests for the ECEFToGPSCoordinateTransformation_ class."""

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
        """Tests whether the ``to_ecef()`` method works."""
        trans = ECEFToGPSCoordinateTransformation()

        # Calculations verified with:
        # http://www.oc.nps.edu/oc2902w/coord/llhxyz.htm
        gps_coord = GPSCoordinate(lat=49, lon=17, amsl=1000)
        ecef_coord = trans.to_ecef(gps_coord)
        self.assertAlmostEqual(4009873, ecef_coord.x, places=0)
        self.assertAlmostEqual(1225941, ecef_coord.y, places=0)
        self.assertAlmostEqual(4791313, ecef_coord.z, places=0)

    def test_to_gps(self):
        """Tests whether the ``to_gps()`` method works."""
        trans = ECEFToGPSCoordinateTransformation()

        # Calculations verified with:
        # http://www.oc.nps.edu/oc2902w/coord/llhxyz.htm
        ecef_coord = ECEFCoordinate(x=4009873, y=1225941, z=4791313)
        gps_coord = trans.to_gps(ecef_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(1000, gps_coord.amsl, places=0)
        self.assertTrue(gps_coord.agl is None)


class FlatEarthToGPSCoordinateTransformationTest(unittest.TestCase):
    """Unit tests for the FlatEarthToGPSCoordinateTransformation_ class."""

    def test_defaults(self):
        """Tests whether the default settings of the transformation are
        correct.
        """
        origin = GPSCoordinate(lat=49, lon=17)
        trans = FlatEarthToGPSCoordinateTransformation(origin=origin)

        self.assertEqual("nwu", trans.type)
        self.assertEqual(0, trans.orientation)
        self.assertEqual(49, trans.origin.lat)
        self.assertEqual(17, trans.origin.lon)

    def test_conversion_in_nwu(self):
        """Tests whether the transformation from flat Earth to GPS coordinates
        and vice versa work with an NWU coordinate system.
        """
        origin = GPSCoordinate(lat=49, lon=17)

        # X axis points North, Y axis points West
        trans = FlatEarthToGPSCoordinateTransformation(
            origin=origin, type="nwu", orientation=0
        )

        flat_earth_coord = FlatEarthCoordinate(x=0, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=5000, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49.04496, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=0, y=-5000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17.06833, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=-3000, y=4000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(48.97302, gps_coord.lat, places=5)
        self.assertAlmostEqual(16.94533, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        # Try a different axis orientation: X axis points Northeast, Y axis
        # points Northwest
        trans = FlatEarthToGPSCoordinateTransformation(
            origin=origin, type="nwu", orientation=45
        )

        flat_earth_coord = FlatEarthCoordinate(x=0, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=5000, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49.03179, gps_coord.lat, places=5)
        self.assertAlmostEqual(17.04832, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=0, y=-5000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(48.96821, gps_coord.lat, places=5)
        self.assertAlmostEqual(17.04832, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=-3000, y=3000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(16.94202, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

    def test_conversion_in_neu(self):
        """Tests whether the transformation from flat Earth to GPS coordinates
        and vice versa work with an NEU coordinate system.
        """
        origin = GPSCoordinate(lat=49, lon=17)

        # X axis points North, Y axis points West
        trans = FlatEarthToGPSCoordinateTransformation(
            origin=origin, type="neu", orientation=0
        )

        flat_earth_coord = FlatEarthCoordinate(x=0, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=5000, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49.04496, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=0, y=5000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17.06833, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=-3000, y=-4000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(48.97302, gps_coord.lat, places=5)
        self.assertAlmostEqual(16.94533, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        # Try a different axis orientation: X axis points Northeast, Y axis
        # points Northwest
        trans = FlatEarthToGPSCoordinateTransformation(
            origin=origin, type="neu", orientation=45
        )

        flat_earth_coord = FlatEarthCoordinate(x=0, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(17, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=5000, y=0)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49.03179, gps_coord.lat, places=5)
        self.assertAlmostEqual(17.04832, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=0, y=5000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(48.96821, gps_coord.lat, places=5)
        self.assertAlmostEqual(17.04832, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)

        flat_earth_coord = FlatEarthCoordinate(x=-3000, y=-3000)
        gps_coord = trans.to_gps(flat_earth_coord)
        recovered_flat_earth_coord = trans.to_flat_earth(gps_coord)
        self.assertAlmostEqual(49, gps_coord.lat, places=5)
        self.assertAlmostEqual(16.94202, gps_coord.lon, places=5)
        self.assertAlmostEqual(flat_earth_coord.x,
                               recovered_flat_earth_coord.x, places=5)
        self.assertAlmostEqual(flat_earth_coord.y,
                               recovered_flat_earth_coord.y, places=5)
