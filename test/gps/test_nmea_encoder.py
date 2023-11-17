from flockwave.gps.encoder import create_gps_encoder
from flockwave.gps.nmea.packet import create_nmea_packet


def test_nmea_encoder():
    messages = [
        create_nmea_packet(
            "GP",
            "GGA",
            "092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,".split(","),
        ),
        create_nmea_packet(
            "GP",
            "GSA",
            "A,3,10,07,05,02,29,04,08,13,,,,,1.72,1.03,1.38".split(","),
        ),
        create_nmea_packet(
            "GP",
            "GSV",
            "3,1,11,10,63,137,17,07,61,098,15,05,59,290,20,08,54,157,30".split(","),
        ),
    ]

    expected = b"""$GPGGA,092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,*76
$GPGSA,A,3,10,07,05,02,29,04,08,13,,,,,1.72,1.03,1.38*0A
$GPGSV,3,1,11,10,63,137,17,07,61,098,15,05,59,290,20,08,54,157,30*70"""

    encoder = create_gps_encoder("nmea")
    for message, sentence in zip(messages, expected.split(b"\n")):
        assert encoder(message) == sentence + b"\r\n"
