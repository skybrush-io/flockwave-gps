"""Unit tests for ``flockwave.gps.distances``."""

from flockwave.gps.distances import haversine
from flockwave.gps.vectors import GPSCoordinate

import unittest


class PlanetCalcDatum(object):
    """Datum that uses the same mean radius as the one on
    http://planetcalc.com/72.
    """

    MEAN_RADIUS_IN_METERS = 6372795


class SimplifiedDatum(object):
    """Datum that uses 6371 km (a commonly used value) for the mean radius
    of the Earth.
    """

    MEAN_RADIUS_IN_METERS = 6371000


class HaversineTest(unittest.TestCase):
    """Unit tests for the Haversine formula."""

    def test_planetcalc(self):
        """Tests the Haversine formula using the example found at
        http://planetcalc.com/72.
        """
        first = GPSCoordinate(lat=55 + 45 / 60, lon=37 + 37 / 60)
        second = GPSCoordinate(lat=59 + 53 / 60, lon=30 + 15 / 60)

        self.assertAlmostEqual(
            633184.232, haversine(first, second, datum=PlanetCalcDatum), places=3
        )

    def test_lyon_paris(self):
        """Tests the Haversine formula for Lyon and Paris."""
        lyon = GPSCoordinate(lat=45.7597, lon=4.8422)
        paris = GPSCoordinate(lat=48.8567, lon=2.3508)
        self.assertAlmostEqual(
            392216.71780659, haversine(lyon, paris, datum=SimplifiedDatum), places=6
        )
