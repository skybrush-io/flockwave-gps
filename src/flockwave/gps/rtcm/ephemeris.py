"""Ephemeris data related classes."""

import logging

from builtins import range
from collections import namedtuple
from math import atan, cos, sin, sqrt

from flockwave.gps.constants import GPS_PI, WGS84
from flockwave.gps.vectors import ECEFCoordinate


__all__ = ("EphemerisData",)

_EphemerisData = namedtuple(
    "EphemerisData",
    "week iodc iode tow toc toe tgd af2 af1 af0 crs "
    "delta_n m0 cuc eccentricity cus sqrt_a cic "
    "omega0 cis i0 crc omega omega_dot i_dot flags "
    "svid",
)

log = logging.getLogger(__name__)


class EphemerisData(_EphemerisData):
    """Ephemeris data from an RTCM v3 packet."""

    # The order of fields in this class matches the order of fields in a
    # GPS ephemeris report according to:
    # http://www.trimble.com/OEM_ReceiverHelp/V4.44/en/ICD_Pkt_Response55h_GPSEph.html

    @property
    def a(self):
        return self.sqrt_a**2

    def calculate_satellite_position(
        self, transmit_time: float = 0, time_of_flight: float = 0
    ) -> tuple[ECEFCoordinate, float]:
        """Calculates the position of the satellite in ECEF coordinates from
        the ephemeris data, the transmit time and the time of flight.

        The body of this function is copied from pyUblox, which is in turn
        based upon http://home-2.worldonline.nl/~samsvl/stdalone.pas

        Parameters:
            transmit_time: the transmit time (if known), in seconds
            time_of_flight: the time of flight (if known), in seconds

        Returns:
            the satellite position in ECEF coordinates and the relativistic
            correction term
        """
        mu = WGS84.GRAVITATIONAL_CONSTANT_TIMES_MASS
        omega_e_dot = WGS84.ROTATION_RATE_IN_RADIANS_PER_SEC

        T = transmit_time - self.toe
        half_week = 302400
        if T > half_week:
            T = T - 2 * half_week
        elif T < -half_week:
            T = T + 2 * half_week

        n = sqrt(mu / (self.sqrt_a**6)) + self.delta_n
        ecc = self.eccentricity

        # Kepler equation
        M = self.m0 + n * T
        E = M
        E_old = M
        for _ in range(20):
            E_old = E
            E = M + ecc * sin(E)
            if abs(E - E_old) < 1e-12:
                break
        else:
            log.warn(
                "Kepler equation did not converge for satellite "
                "{0.svid} (last difference = {1})".format(self, E - E_old)
            )

        sin_e, cos_e = sin(E), cos(E)
        snu = sqrt(1 - ecc**2) * sin_e / (1 - ecc * cos_e)
        cnu = (cos_e - ecc) / (1 - ecc * cos_e)

        # The paragraph below is basically equivalent to
        # nu = atan2(snu, cnu), but it uses this special GPS_PI constant,
        # which is not exactly equal to math.pi, and I don't know whether
        # the difference is significant
        pi = GPS_PI
        if cnu == 0:
            nu = pi / 2 * snu / abs(snu)
        elif snu == 0 and cnu > 0:
            nu = 0
        elif snu == 0 and cnu < 0:
            nu = pi
        else:
            nu = atan(snu / cnu)
            if cnu < 0:
                nu += pi * snu / abs(snu)

        phi = nu + self.omega

        sin_2_phi, cos_2_phi = sin(2 * phi), cos(2 * phi)
        du = self.cuc * cos_2_phi + self.cus * sin_2_phi
        dr = self.crc * cos_2_phi + self.crs * sin_2_phi
        di = self.cic * cos_2_phi + self.cis * sin_2_phi

        u = phi + du
        r = self.a * (1 - ecc * cos_e) + dr
        i = self.i0 + self.i_dot * T + di

        x_dash = r * cos(u)
        y_dash = r * sin(u)

        wc = self.omega0 + (self.omega_dot - omega_e_dot) * T - omega_e_dot * self.toe

        cos_wc, sin_wc = cos(wc), sin(wc)
        cos_i = cos(i)

        pos = ECEFCoordinate(
            x=x_dash * cos_wc - y_dash * cos_i * sin_wc,
            y=x_dash * sin_wc + y_dash * cos_i * cos_wc,
            z=y_dash * sin(i),
        )
        rel_term = -4.442807633e-10 * ecc * self.sqrt_a * sin_e

        if time_of_flight != 0:
            omega_e_dot = 7.292115e-5
            alpha = time_of_flight * omega_e_dot
            pos.update(
                x=pos.x * cos(alpha) + pos.y * sin(alpha),
                y=pos.y * cos(alpha) - pos.x * sin(alpha),
            )

        return pos, rel_term

    @property
    def issue_of_data_clock(self):
        return self.iodc

    @property
    def issue_of_data_ephemeris(self):
        return self.iode
