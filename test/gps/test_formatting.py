from datetime import datetime
from typing import Optional
from pytest import mark

from flockwave.gps.formatting import (
    format_gps_coordinate_as_nmea_gga_message,
    format_latitude_for_nmea_gga_message,
    format_longitude_for_nmea_gga_message,
)
from flockwave.gps.vectors import GPSCoordinate


@mark.parametrize(
    ("input", "output"),
    [
        (-1.8, ("0148.0000", "S")),
        (-1.75, ("0145.0000", "S")),
        (-1.9, ("0154.0000", "S")),
        (-2, ("0200.0000", "S")),
        (-2.025, ("0201.5000", "S")),
        (1.8, ("0148.0000", "N")),
        (1.75, ("0145.0000", "N")),
        (1.9, ("0154.0000", "N")),
        (2, ("0200.0000", "N")),
        (2.025, ("0201.5000", "N")),
        (39 + 7.356 / 60, ("3907.3560", "N")),
    ],
)
def test_format_latitude_for_nmea_gga_message(input: float, output: tuple[str, str]):
    assert format_latitude_for_nmea_gga_message(input) == output


@mark.parametrize(
    ("input", "output"),
    [
        (-1.8, ("00148.0000", "W")),
        (-1.75, ("00145.0000", "W")),
        (-1.9, ("00154.0000", "W")),
        (-2, ("00200.0000", "W")),
        (-2.025, ("00201.5000", "W")),
        (1.8, ("00148.0000", "E")),
        (1.75, ("00145.0000", "E")),
        (1.9, ("00154.0000", "E")),
        (2, ("00200.0000", "E")),
        (123.025, ("12301.5000", "E")),
        (-(121 + 2.482 / 60), ("12102.4820", "W")),
    ],
)
def test_format_longitude_for_nmea_gga_message(input: float, output: tuple[str, str]):
    assert format_longitude_for_nmea_gga_message(input) == output


@mark.parametrize(
    ("lat", "lon", "alt", "time", "output"),
    [
        (
            47 + 23.5411 / 60,
            8 + 26.8849 / 60,
            473.5,
            datetime(2024, 8, 27, 15, 12, 29, 400000),
            "$GPGGA,151229.40,4723.5411,N,00826.8849,E,1,10,1,473.50,M,,,0.0,0000*30\r\n",
        )
    ],
)
def test_format_gps_coordinate_as_nmea_gga_message(
    lat: float, lon: float, alt: Optional[float], time: datetime, output: str
):
    coord = GPSCoordinate(lat, lon, amsl=alt)
    sentence = format_gps_coordinate_as_nmea_gga_message(coord, time=time)
    assert sentence == output
