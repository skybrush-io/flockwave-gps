from typing import Any

import pytest

from flockwave.gps.constants import GPS_PI, SPEED_OF_LIGHT_KM_S
from flockwave.gps.rtcm import (
    RTCMFormatAutodetectingParser,
    RTCMV2Encoder,
    RTCMV2Parser,
    RTCMV3Parser,
    create_rtcm_parser,
)
from flockwave.gps.rtcm.packets import (
    RTCMV2FullCorrectionsPacket,
    RTCMV2GPSReferenceStationParametersPacket,
    RTCMV2Packet,
    RTCMV3AntennaDescriptorPacket,
    RTCMV3ExtendedAntennaDescriptorPacket,
    RTCMV3GLONASSRTKPacket,
    RTCMV3GPSEphemerisPacket,
    RTCMV3GPSRTKPacket,
    RTCMV3MSMPacket,
    RTCMV3Packet,
    RTCMV3StationaryAntennaPacket,
)
from flockwave.gps.vectors import ECEFCoordinate

from .rtcm_helpers import BitWriter, frame_rtcm3

#: RTCM v3 message 1005 taken from the example in the RTCM 10403 standard
#: (station 2003, ECEF X=1114104.5999, Y=-4850729.7108, Z=3975521.4643)
RTCM3_1005_EXAMPLE = bytes.fromhex("d300133ed7d30202980edeef34b4bd62ac0941986f33360b98")

#: Short RTCM v3 message of an unknown type without any 0xD3 byte after the
#: preamble. Used in tests where a corrupted message must not contain anything
#: that looks like a preamble, which would legitimately throw the parser off
#: track for a while.
RTCM3_SHORT_MESSAGE = bytes.fromhex("d30003ffeabc83db27")


def parse(parser, data: bytes) -> list[Any]:
    return list(parser.feed(data))


def feed_bytewise(parser, data: bytes) -> list[Any]:
    result = []
    for byte in data:
        result.extend(parser.feed(bytes([byte])))
    return result


###########################################################################
# RTCM v3 payload builders


def build_1006_payload() -> bytes:
    w = BitWriter()
    w.uint(12, 1006).uint(12, 4095)
    w.uint(6, 0).uint(3, 1).bool(True)
    w.int(38, 40800001234).bool(True).uint(1, 0)
    w.int(38, -14000005678).uint(2, 0)
    w.int(38, 47000009012)
    w.uint(16, 15432)
    return w.to_bytes()


def build_gps_rtk_payload(packet_type: int) -> bytes:
    has_l2 = packet_type in (1003, 1004)
    is_extended = packet_type in (1002, 1004)

    w = BitWriter()
    w.uint(12, packet_type).uint(12, 1234)
    w.uint(30, 345678901).bool(True).uint(5, 2).bool(True).uint(3, 5)

    sats = [
        # svid, code, pr, prdiff, lock, amb, cnr, l2code, l2pr, l2prdiff, l2lock, l2cnr
        (5, 1, 1000000, -1234, 63, 12, 180, 1, -500, 4321, 60, 160),
        (31, 0, 7654321, 222222, 100, 0, 4, 3, 8191, -222222, 127, 255),
    ]
    for svid, code, pr, prd, lock, amb, cnr, l2c, l2pr, l2prd, l2lock, l2cnr in sats:
        w.uint(6, svid).uint(1, code).uint(24, pr).int(20, prd).uint(7, lock)
        if is_extended:
            w.uint(8, amb).uint(8, cnr)
        if has_l2:
            w.uint(2, l2c).int(14, l2pr).int(20, l2prd).uint(7, l2lock)
            if is_extended:
                w.uint(8, l2cnr)

    return w.to_bytes()


def build_glonass_rtk_payload(packet_type: int) -> bytes:
    has_l2 = packet_type in (1011, 1012)
    is_extended = packet_type in (1010, 1012)

    w = BitWriter()
    w.uint(12, packet_type).uint(12, 77)
    w.uint(27, 12345678).bool(False).uint(5, 2).bool(False).uint(3, 0)

    sats = [
        # svid, code, freq, pr, prdiff, lock, amb, cnr, l2code, l2pr, l2prdiff,
        # l2lock, l2cnr
        (24, 1, 13, 20000000, -5000, 42, 99, 160, 2, 1500, 6000, 17, 140),
        (1, 0, 0, 33554431, 1, 100, 0, 255, 1, -250, -1, 127, 0),
    ]
    for (
        svid,
        code,
        freq,
        pr,
        prd,
        lock,
        amb,
        cnr,
        l2c,
        l2pr,
        l2prd,
        l2lock,
        l2cnr,
    ) in sats:
        w.uint(6, svid).uint(1, code).uint(5, freq).uint(25, pr).int(20, prd)
        w.uint(7, lock)
        if is_extended:
            w.uint(7, amb).uint(8, cnr)
        if has_l2:
            w.uint(2, l2c).int(14, l2pr).int(20, l2prd).uint(7, l2lock)
            if is_extended:
                w.uint(8, l2cnr)

    return w.to_bytes()


EPHEMERIS_FIELDS = [
    # name, width, signed, value
    ("svid", 6, False, 17),
    ("week", 10, False, 345),
    ("acc", 4, False, 2),
    ("l2code", 2, False, 1),
    ("i_dot", 14, True, -1234),
    ("iode", 8, False, 77),
    ("toc", 16, False, 22500),
    ("af2", 8, True, -3),
    ("af1", 16, True, -12345),
    ("af0", 22, True, 1234567),
    ("iodc", 10, False, 589),
    ("crs", 16, True, -1500),
    ("delta_n", 16, True, 13000),
    ("m0", 32, True, -1987654321),
    ("cuc", 16, True, -2500),
    ("eccentricity", 32, False, 3456789012),
    ("cus", 16, True, 3000),
    ("sqrt_a", 32, False, 2702100000),
    ("toe", 16, False, 22500),
    ("cic", 16, True, -50),
    ("omega0", 32, True, 1555555555),
    ("cis", 16, True, 60),
    ("i0", 32, True, 654321098),
    ("crc", 16, True, 7000),
    ("omega", 32, True, -987654321),
    ("omega_dot", 24, True, -8000),
    ("tgd", 8, True, -11),
    ("health", 6, False, 0),
    ("l2p", 1, False, 1),
    ("fit", 1, False, 0),
]


def build_1019_payload() -> bytes:
    w = BitWriter()
    w.uint(12, 1019)
    for _, width, signed, value in EPHEMERIS_FIELDS:
        if signed:
            w.int(width, value)
        else:
            w.uint(width, value)
    return w.to_bytes()


def build_msm_payload(packet_type: int) -> bytes:
    """Builds an MSM payload with satellites 3 and 17 and signals 2 and 15.
    Satellite 3 has both signals, satellite 17 has signal 15 only.
    """
    last_digit = packet_type % 10
    hires_sat = last_digit in (5, 7)
    hires_sig = last_digit in (6, 7)

    w = BitWriter()
    w.uint(12, packet_type).uint(12, 2047)
    w.uint(30, 123456789).bool(True).uint(3, 5)
    w.uint(7, 9).uint(2, 1).uint(2, 2).bool(True).uint(3, 4)

    w.uint(64, (1 << (64 - 3)) | (1 << (64 - 17)))
    w.uint(32, (1 << (32 - 2)) | (1 << (32 - 15)))
    w.bits("11" + "01")

    # Satellite data
    w.uint(8, 70).uint(8, 75)
    if hires_sat:
        w.uint(4, 3).uint(4, 15)
    w.uint(10, 512).uint(10, 1023)
    if hires_sat:
        w.int(14, -8000).int(14, 8000)

    # Signal data (three cells)
    for value in (-1, 2, -3):
        w.int(20, value) if hires_sig else w.int(15, value)
    for value in (100, -200, 300):
        w.int(24, value) if hires_sig else w.int(22, value)
    for value in (1, 2, 3):
        w.uint(10, value) if hires_sig else w.uint(4, value)
    w.bits("010")
    cnrs = (720, 640, 800) if hires_sig else (45, 40, 50)
    for value in cnrs:
        w.uint(10, value) if hires_sig else w.uint(6, value)
    if last_digit in (5, 7):
        for value in (-10, 0, 10):
            w.int(15, value)

    return w.to_bytes()


###########################################################################
# RTCM v3 parser tests


def test_rtcm3_parser_standard_example():
    parser = RTCMV3Parser()
    packets = parse(parser, RTCM3_1005_EXAMPLE)

    assert len(packets) == 1
    packet = packets[0]
    assert isinstance(packet, RTCMV3StationaryAntennaPacket)
    assert packet.packet_type == 1005
    assert packet.bytes == RTCM3_1005_EXAMPLE[3:-3]
    assert packet.station_id == 2003
    assert packet.system == 4
    assert packet.is_reference_station is False
    assert packet.single_receiver is False
    assert packet.antenna_height is None
    assert packet.position.x == pytest.approx(1114104.5999)
    assert packet.position.y == pytest.approx(-4850729.7108)
    assert packet.position.z == pytest.approx(3975521.4643)


def test_rtcm3_parser_bytewise_and_chunked_feeding():
    stream = b"garbage" + RTCM3_1005_EXAMPLE * 3 + b"\x00\x01"

    assert len(feed_bytewise(RTCMV3Parser(), stream)) == 3
    assert len(parse(RTCMV3Parser(), stream)) == 3

    parser = RTCMV3Parser()
    packets = []
    for i in range(0, len(stream), 7):
        packets.extend(parse(parser, stream[i : i + 7]))
    assert [p.station_id for p in packets] == [2003] * 3


def test_rtcm3_parser_drops_packet_with_checksum_error():
    corrupted = bytearray(RTCM3_SHORT_MESSAGE)
    corrupted[4] ^= 0x01

    packets = parse(RTCMV3Parser(), bytes(corrupted) + RTCM3_1005_EXAMPLE)
    assert len(packets) == 1
    assert packets[0].station_id == 2003


def test_rtcm3_parser_recovers_from_spurious_preamble():
    # The spurious preamble claims a two-byte payload, so the parser swallows
    # the first five bytes of the real packet before the CRC check fails. It
    # must then resynchronize on the preamble of the real packet.
    stream = b"\xd3\x00\x02" + RTCM3_1005_EXAMPLE

    packets = parse(RTCMV3Parser(), stream)
    assert len(packets) == 1
    assert packets[0].station_id == 2003

    packets = feed_bytewise(RTCMV3Parser(), stream)
    assert len(packets) == 1


def test_rtcm3_parser_max_packet_length():
    assert parse(RTCMV3Parser(max_packet_length=10), RTCM3_1005_EXAMPLE) == []
    assert len(parse(RTCMV3Parser(max_packet_length=22), RTCM3_1005_EXAMPLE)) == 1


def test_rtcm3_parser_reset():
    parser = RTCMV3Parser()
    assert parse(parser, RTCM3_1005_EXAMPLE[:10]) == []
    parser.reset()
    assert parse(parser, RTCM3_1005_EXAMPLE[10:]) == []
    assert len(parse(parser, RTCM3_1005_EXAMPLE)) == 1


def test_rtcm3_short_message_constant():
    payload = BitWriter().uint(12, 4094).uint(12, 0xABC).to_bytes()
    assert RTCM3_SHORT_MESSAGE == frame_rtcm3(payload)
    assert 0xD3 not in RTCM3_SHORT_MESSAGE[1:]


def test_rtcm3_unknown_packet_type():
    payload = BitWriter().uint(12, 4094).uint(12, 0xABC).to_bytes()
    packets = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert len(packets) == 1
    assert type(packets[0]) is RTCMV3Packet
    assert packets[0].packet_type == 4094
    assert packets[0].bytes == payload


def test_rtcm3_1006():
    payload = build_1006_payload()
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert isinstance(packet, RTCMV3StationaryAntennaPacket)
    assert packet.packet_type == 1006
    assert packet.station_id == 4095
    assert packet.system == 1
    assert packet.is_reference_station is True
    assert packet.single_receiver is True
    assert packet.position.x == pytest.approx(4080000.1234)
    assert packet.position.y == pytest.approx(-1400000.5678)
    assert packet.position.z == pytest.approx(4700000.9012)
    assert packet.antenna_height == pytest.approx(1.5432)


def test_rtcm3_1007_and_1008():
    payload = (
        BitWriter().uint(12, 1007).uint(12, 42).string("ANT-X").uint(8, 3).to_bytes()
    )
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert isinstance(packet, RTCMV3AntennaDescriptorPacket)
    assert packet.station_id == 42
    assert packet.descriptor == "ANT-X"
    assert packet.setup_id == 3
    assert packet.serial is None

    payload = (
        BitWriter()
        .uint(12, 1008)
        .uint(12, 43)
        .string("")
        .uint(8, 255)
        .string("SN12345")
        .to_bytes()
    )
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert isinstance(packet, RTCMV3AntennaDescriptorPacket)
    assert packet.station_id == 43
    assert packet.descriptor == ""
    assert packet.setup_id == 255
    assert packet.serial == "SN12345"


def test_rtcm3_1033():
    payload = (
        BitWriter()
        .uint(12, 1033)
        .uint(12, 1)
        .string("TRM59800.00     NONE")
        .uint(8, 0)
        .string("1234")
        .string("SEPT POLARX5")
        .string("5.4.0")
        .to_bytes()
    )
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert isinstance(packet, RTCMV3ExtendedAntennaDescriptorPacket)
    assert packet.station_id == 1
    assert packet.descriptor == "TRM59800.00     NONE"
    assert packet.setup_id == 0
    assert packet.serial == "1234"
    assert packet.receiver == "SEPT POLARX5"
    assert packet.firmware == "5.4.0"


@pytest.mark.parametrize("packet_type", [1001, 1002, 1003, 1004])
def test_rtcm3_gps_rtk(packet_type: int):
    has_l2 = packet_type in (1003, 1004)
    is_extended = packet_type in (1002, 1004)

    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(build_gps_rtk_payload(packet_type)))

    assert isinstance(packet, RTCMV3GPSRTKPacket)
    assert packet.packet_type == packet_type
    assert packet.station_id == 1234
    assert packet.tow == pytest.approx(345678.901)
    assert packet.time_of_week == packet.tow
    assert packet.sync is True
    assert packet.smoothed is True
    assert packet.smoothing_interval == 5
    assert packet.num_satellites == 2

    first, second = packet.satellites
    assert (first.svid, first.id) == (5, "G05")
    assert (second.svid, second.id) == (31, "G31")

    assert first.l1["code"] == 1
    assert first.l1["type"] == "1W"
    assert first.l1["pseudorange"] == pytest.approx(20000.0)
    assert first.l1["pseudorange_diff"] == pytest.approx(-0.617)
    assert first.l1["pseudorange_valid"] is True
    assert first.l1["lock_time"] == 63
    assert second.l1["type"] == "1C"
    assert second.l1["pseudorange"] == pytest.approx(153086.42)
    assert second.l1["pseudorange_diff"] == pytest.approx(111.111)
    assert second.l1["lock_time"] == 100

    if is_extended:
        assert first.l1["ambiguity"] == 12
        assert first.l1["cnr"] == pytest.approx(45.0)
        assert second.l1["ambiguity"] == 0
        assert second.l1["cnr"] == pytest.approx(1.0)
    else:
        assert "ambiguity" not in first.l1
        assert "cnr" not in first.l1

    if has_l2:
        assert first.l2 is not None and second.l2 is not None
        assert first.l2["code"] == 1
        assert first.l2["type"] == "2P"
        assert first.l2["pseudorange"] == pytest.approx(-10.0)
        assert first.l2["pseudorange_diff"] == pytest.approx(2.1605)
        assert first.l2["lock_time"] == 60
        assert second.l2["code"] == 3
        assert second.l2["type"] == "2W"
        assert second.l2["pseudorange"] == pytest.approx(163.82)
        assert second.l2["pseudorange_diff"] == pytest.approx(-111.111)
        assert second.l2["lock_time"] == 127
        if is_extended:
            assert first.l2["cnr"] == pytest.approx(40.0)
            assert second.l2["cnr"] == pytest.approx(63.75)
            assert first.cnr == (pytest.approx(45.0), pytest.approx(40.0))
    else:
        assert first.l2 is None
        if is_extended:
            assert first.cnr == pytest.approx(45.0)

    if is_extended:
        p1 = 20000.0 + 12 * SPEED_OF_LIGHT_KM_S
        assert first.temp_corrs["p1"] == pytest.approx(p1)
        if has_l2:
            assert first.temp_corrs["p2"] == pytest.approx(p1 - 10.0)
        assert [s.svid for s in packet.best_satellites()] == [5, 31]
        assert [s.svid for s in packet.best_satellites(1)] == [5]
    else:
        assert first.temp_corrs["p1"] == 0.0

    json = packet.json
    assert json["packet_type"] == packet_type
    assert json["station_id"] == 1234
    assert [sat["svid"] for sat in json["satellites"]] == [5, 31]


def test_rtcm3_gps_rtk_invalid_markers():
    w = BitWriter()
    w.uint(12, 1004).uint(12, 1).uint(30, 0).bool(False).uint(5, 2)
    w.bool(False).uint(3, 0)
    # First satellite: L1 phaserange-pseudorange invalid
    w.uint(6, 1).uint(1, 0).uint(24, 1000).int(20, -0x80000).uint(7, 0)
    w.uint(8, 0).uint(8, 0)
    w.uint(2, 0).int(14, 10).int(20, 0).uint(7, 0).uint(8, 0)
    # Second satellite: L2-L1 pseudorange difference and L2
    # phaserange-pseudorange invalid
    w.uint(6, 2).uint(1, 0).uint(24, 1000).int(20, 0).uint(7, 0)
    w.uint(8, 0).uint(8, 0)
    w.uint(2, 0).int(14, -0x2000).int(20, -0x80000).uint(7, 0).uint(8, 0)

    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(w.to_bytes()))
    first, second = packet.satellites

    assert first.l1["pseudorange_diff"] == 0.0
    assert first.l1["pseudorange_valid"] is False
    assert first.l2["pseudorange"] == pytest.approx(0.2)
    assert first.l2["pseudorange_valid"] is True
    assert first.temp_corrs == {"p1": 0.0, "p2": 0.0}

    assert second.l1["pseudorange_valid"] is True
    assert second.l2["pseudorange"] == 0.0
    assert second.l2["pseudorange_diff"] == 0.0
    assert second.l2["pseudorange_valid"] is False
    assert second.temp_corrs == {"p1": 0.0, "p2": 0.0}


def test_rtcm3_glonass_rtk_invalid_markers():
    w = BitWriter()
    w.uint(12, 1012).uint(12, 1).uint(27, 0).bool(False).uint(5, 1)
    w.bool(False).uint(3, 0)
    w.uint(6, 1).uint(1, 0).uint(5, 7).uint(25, 1000).int(20, -0x80000).uint(7, 0)
    w.uint(7, 0).uint(8, 0)
    w.uint(2, 0).int(14, -0x2000).int(20, -0x80000).uint(7, 0).uint(8, 0)

    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(w.to_bytes()))
    (sat,) = packet.satellites

    assert sat.l1["pseudorange"] == pytest.approx(20.0)
    assert sat.l1["pseudorange_diff"] == 0.0
    assert sat.l1["pseudorange_valid"] is False
    assert sat.l2["pseudorange"] == 0.0
    assert sat.l2["pseudorange_diff"] == 0.0
    assert sat.l2["pseudorange_valid"] is False


@pytest.mark.parametrize("packet_type", [1009, 1010, 1011, 1012])
def test_rtcm3_glonass_rtk(packet_type: int):
    has_l2 = packet_type in (1011, 1012)
    is_extended = packet_type in (1010, 1012)

    payload = build_glonass_rtk_payload(packet_type)
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert isinstance(packet, RTCMV3GLONASSRTKPacket)
    assert packet.packet_type == packet_type
    assert packet.station_id == 77
    assert packet.tod == pytest.approx(12345.678)
    assert packet.time_of_day == packet.tod
    assert packet.sync is False
    assert packet.smoothed is False
    assert packet.smoothing_interval == 0
    assert packet.num_satellites == 2

    sat, other = packet.satellites
    assert (sat.svid, sat.id) == (24, "R24")
    assert sat.l1["code"] == 1
    assert sat.l1["type"] == "1W"
    assert sat.l1["freq"] == 13
    assert sat.l1["pseudorange"] == pytest.approx(400000.0)
    assert sat.l1["pseudorange_diff"] == pytest.approx(-2.5)
    assert sat.l1["pseudorange_valid"] is True
    assert sat.l1["lock_time"] == 42

    if is_extended:
        assert sat.l1["ambiguity"] == 99
        assert sat.l1["cnr"] == pytest.approx(40.0)

    if has_l2:
        assert sat.l2 is not None
        assert sat.l2["code"] == 2
        assert sat.l2["type"] == "2W"
        assert sat.l2["freq"] == 0
        assert sat.l2["pseudorange"] == pytest.approx(30.0)
        assert sat.l2["pseudorange_diff"] == pytest.approx(3.0)
        assert sat.l2["lock_time"] == 17
        if is_extended:
            assert sat.l2["cnr"] == pytest.approx(35.0)
            assert sat.cnr == (pytest.approx(40.0), pytest.approx(35.0))
        else:
            assert "ambiguity" not in sat.l1
            assert "cnr" not in sat.l1
            assert "ambiguity" not in sat.l2
            assert "cnr" not in sat.l2
    else:
        assert sat.l2 is None

    # The second satellite catches misaligned fields in the first one
    assert (other.svid, other.id) == (1, "R01")
    assert other.l1["code"] == 0
    assert other.l1["freq"] == 0
    assert other.l1["pseudorange"] == pytest.approx(671088.62)
    assert other.l1["pseudorange_diff"] == pytest.approx(0.0005)
    assert other.l1["lock_time"] == 100
    if is_extended:
        assert other.l1["ambiguity"] == 0
        assert other.l1["cnr"] == pytest.approx(63.75)
    if has_l2:
        assert other.l2 is not None
        assert other.l2["type"] == "2P"
        assert other.l2["pseudorange"] == pytest.approx(-5.0)
        assert other.l2["pseudorange_diff"] == pytest.approx(-0.0005)
        assert other.l2["lock_time"] == 127
        if is_extended:
            assert other.l2["cnr"] == 0.0

    assert repr(sat).startswith("<RTCMV3GLONASSSatelliteInfo(svid=24, ")
    assert repr(packet).startswith("<RTCMV3GLONASSRTKPacket(station_id=77, ")

    json = packet.json
    assert json["tod"] == packet.tod
    assert [s["svid"] for s in json["satellites"]] == [24, 1]


def test_rtcm3_gps_ephemeris():
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(build_1019_payload()))

    assert isinstance(packet, RTCMV3GPSEphemerisPacket)
    for name, _, _, value in EPHEMERIS_FIELDS:
        assert getattr(packet, name) == value, name

    eph = packet.ephemeris
    assert eph.svid == 17
    assert eph.week == 345
    assert eph.iode == 77
    assert eph.iodc == 589
    assert eph.toe == 22500 * 16
    assert eph.toc == 22500 * 16
    assert eph.af0 == pytest.approx(1234567 / 2**31)
    assert eph.af1 == pytest.approx(-12345 / 2**43)
    assert eph.af2 == pytest.approx(-3 / 2**55)
    assert eph.tgd == pytest.approx(-11 / 2**31)
    assert eph.crs == pytest.approx(-1500 / 2**5)
    assert eph.cuc == pytest.approx(-2500 / 2**29)
    assert eph.eccentricity == pytest.approx(3456789012 / 2**33)
    assert eph.sqrt_a == pytest.approx(2702100000 / 2**19)
    assert eph.m0 == pytest.approx(-1987654321 * GPS_PI / 2**31)
    assert eph.omega_dot == pytest.approx(-8000 * GPS_PI / 2**43)
    assert eph.i_dot == pytest.approx(-1234 * GPS_PI / 2**43)
    assert eph.i0 == pytest.approx(654321098 * GPS_PI / 2**31)


@pytest.mark.parametrize(
    "packet_type,prefix",
    [
        (1074, "G"),
        (1075, "G"),
        (1076, "G"),
        (1077, "G"),
        (1084, "R"),
        (1095, "E"),
        (1116, "Q"),
        (1127, "C"),
    ],
)
def test_rtcm3_msm(packet_type: int, prefix: str):
    last_digit = packet_type % 10
    hires_sat = last_digit in (5, 7)
    hires_sig = last_digit in (6, 7)

    payload = build_msm_payload(packet_type)
    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(payload))

    assert isinstance(packet, RTCMV3MSMPacket)
    assert packet.packet_type == packet_type
    assert packet.bytes == payload
    assert packet.station_id == 2047
    assert packet.tow == pytest.approx(123456.789)
    assert packet.time_of_week == packet.tow
    assert packet.sync is True
    assert packet.iod == 5
    assert packet.time_s == 9
    assert packet.clk_str == 1
    assert packet.clk_ext == 2
    assert packet.smoothed is True
    assert packet.smoothing_interval == 4
    assert packet.num_satellites == 2

    first, second = packet.satellites
    assert (first.svid, first.id) == (3, f"{prefix}03")
    assert (second.svid, second.id) == (17, f"{prefix}17")

    assert first.range == pytest.approx(70 * 299792.458)
    assert second.range == pytest.approx(75 * 299792.458)
    assert (first.rng_m, second.rng_m) == (512, 1023)
    if hires_sat:
        assert (first.extended_info, second.extended_info) == (3, 15)
        assert (first.rate, second.rate) == (-8000, 8000)
    else:
        assert first.extended_info is None and second.extended_info is None
        assert first.rate is None and second.rate is None

    assert [s["id"] for s in first.signals] == [2, 15]
    assert [s["id"] for s in second.signals] == [15]

    if hires_sig:
        expected_cnrs = [45.0, 40.0], [50.0]
    else:
        expected_cnrs = [45, 40], [50]
    assert [s["cnr"] for s in first.signals] == expected_cnrs[0]
    assert [s["cnr"] for s in second.signals] == expected_cnrs[1]
    assert first.cnr == 45
    assert second.cnr == 50

    assert [s.svid for s in packet.best_satellites()] == [17, 3]

    json = packet.json
    assert json["iod"] == 5
    assert [sat["svid"] for sat in json["satellites"]] == [3, 17]
    assert json["satellites"][0]["signals"] == first.signals


def test_rtcm3_msm_without_satellites():
    w = BitWriter()
    w.uint(12, 1077).uint(12, 0).uint(30, 0).bool(False).uint(3, 0)
    w.uint(7, 0).uint(2, 0).uint(2, 0).bool(False).uint(3, 0)
    w.uint(64, 0).uint(32, 0)

    (packet,) = parse(RTCMV3Parser(), frame_rtcm3(w.to_bytes()))
    assert isinstance(packet, RTCMV3MSMPacket)
    assert packet.satellites == []


###########################################################################
# RTCM v2 parser tests


def encode_rtcm2_stream(*messages, time_of_week: int = 18123) -> bytes:
    encoder = RTCMV2Encoder()
    return b"".join(encoder.encode(m, time_of_week=time_of_week) for m in messages)


def test_rtcm2_parser_reference_station_parameters():
    message = RTCMV2GPSReferenceStationParametersPacket(
        station_id=7, position=ECEFCoordinate(4080000.12, 1400000.34, -4700000.5)
    )
    data = encode_rtcm2_stream(message)

    for packets in (parse(RTCMV2Parser(), data), feed_bytewise(RTCMV2Parser(), data)):
        assert len(packets) == 1
        packet = packets[0]
        assert isinstance(packet, RTCMV2GPSReferenceStationParametersPacket)
        assert packet.packet_type == 3
        assert packet.station_id == 7
        assert packet.modified_z_count == 205
        assert packet.position is not None
        assert packet.position.x == pytest.approx(4080000.12)
        assert packet.position.y == pytest.approx(1400000.34)
        assert packet.position.z == pytest.approx(-4700000.5)


def test_rtcm2_parser_unknown_packet_type():
    message = RTCMV2Packet(packet_type=16, station_id=5, bytes=b"HELLO!")
    (packet,) = parse(RTCMV2Parser(), encode_rtcm2_stream(message))

    assert type(packet) is RTCMV2Packet
    assert packet.packet_type == 16
    assert packet.station_id == 5
    assert packet.modified_z_count == 205
    # bytes contains the packet without the preamble but with the header
    assert packet.bytes is not None
    assert packet.bytes.endswith(b"HELLO!")
    assert len(packet.bytes) == 5 + 6


def test_rtcm2_parser_stream_of_messages():
    messages = [
        RTCMV2GPSReferenceStationParametersPacket(
            station_id=i, position=ECEFCoordinate(i, -i, 2 * i)
        )
        for i in range(1, 11)
    ]
    # Bytes whose upper two bits are not 01 are ignored by the parser
    data = b"\xff\x00\x80\xc3" + encode_rtcm2_stream(*messages)

    packets = parse(RTCMV2Parser(), data)
    assert [p.station_id for p in packets] == list(range(1, 11))
    assert packets[4].position.x == pytest.approx(5)
    assert packets[4].position.y == pytest.approx(-5)
    assert packets[4].position.z == pytest.approx(10)


def test_rtcm2_parser_drops_corrupted_message():
    messages = [
        RTCMV2GPSReferenceStationParametersPacket(
            station_id=i, position=ECEFCoordinate(1, 2, 3)
        )
        for i in range(1, 4)
    ]
    encoder = RTCMV2Encoder()
    chunks = [bytearray(encoder.encode(m, time_of_week=0)) for m in messages]

    # Flip a data bit in the middle of the second message while keeping the
    # upper two bits of the byte intact
    chunks[1][12] ^= 0x04

    packets = parse(RTCMV2Parser(), b"".join(chunks))
    assert [p.station_id for p in packets] == [1, 3]


def test_rtcm2_parser_resets_on_invalid_byte():
    message = RTCMV2GPSReferenceStationParametersPacket(
        station_id=1, position=ECEFCoordinate(1, 2, 3)
    )
    data = bytearray(encode_rtcm2_stream(message, message))
    data[10] = 0xFF  # upper two bits must be 01 in valid RTCM v2 bytes

    packets = parse(RTCMV2Parser(), bytes(data))
    assert len(packets) == 1


def test_rtcm2_parser_full_corrections():
    payload = (
        BitWriter()
        .uint(1, 0)
        .uint(2, 0)
        .uint(5, 5)
        .int(16, -1234)
        .int(8, 12)
        .uint(8, 77)
        .uint(1, 1)
        .uint(2, 0)
        .uint(5, 17)
        .int(16, 2500)
        .int(8, -19)
        .uint(8, 3)
        .to_bytes()
    )
    message = RTCMV2Packet(packet_type=1, station_id=123, bytes=payload)
    (packet,) = parse(RTCMV2Parser(), encode_rtcm2_stream(message))

    assert isinstance(packet, RTCMV2FullCorrectionsPacket)
    assert packet.num_satellites == 2
    first, second = packet.corrections
    assert (first.svid, first.prc, first.prrc, first.iode) == (5, -1234, 12, 77)
    assert (second.svid, second.prc, second.prrc, second.iode) == (17, 40000, -304, 3)


###########################################################################
# Autodetecting parser and factory function tests


def test_autodetecting_parser_rtcm3():
    parser = RTCMFormatAutodetectingParser()
    packets = parse(parser, b"\x01\x02" + RTCM3_1005_EXAMPLE + RTCM3_1005_EXAMPLE)

    assert len(packets) == 2
    assert all(isinstance(p, RTCMV3StationaryAntennaPacket) for p in packets)
    assert isinstance(parser._chosen_subparser, RTCMV3Parser)


def test_autodetecting_parser_rtcm3_with_spurious_preamble():
    parser = RTCMFormatAutodetectingParser()
    packets = feed_bytewise(parser, b"\xd3\x00\x02" + RTCM3_1005_EXAMPLE)

    assert len(packets) == 1
    assert packets[0].station_id == 2003
    assert isinstance(parser._chosen_subparser, RTCMV3Parser)

    # Checksum errors after the subparser was chosen must be handled too
    corrupted = bytearray(RTCM3_SHORT_MESSAGE)
    corrupted[4] ^= 0x01
    packets = parse(parser, b"\xd3\x00\x02" + bytes(corrupted) + RTCM3_1005_EXAMPLE)
    assert len(packets) == 1


def test_autodetecting_parser_rtcm2():
    messages = [
        RTCMV2GPSReferenceStationParametersPacket(
            station_id=i, position=ECEFCoordinate(1, 2, 3)
        )
        for i in range(1, 4)
    ]
    parser = RTCMFormatAutodetectingParser()
    packets = parse(parser, encode_rtcm2_stream(*messages))

    assert [p.station_id for p in packets] == [1, 2, 3]
    assert isinstance(parser._chosen_subparser, RTCMV2Parser)

    parser.reset()
    assert parser._chosen_subparser is None


@pytest.mark.parametrize(
    "format,expected",
    [
        ("rtcm2", RTCMV2Parser),
        (2, RTCMV2Parser),
        ("rtcm3", RTCMV3Parser),
        (3, RTCMV3Parser),
        ("auto", RTCMFormatAutodetectingParser),
    ],
)
def test_create_rtcm_parser(format, expected):
    parser = create_rtcm_parser(format)
    assert isinstance(parser.__self__, expected)  # type: ignore


def test_create_rtcm_parser_invalid_format():
    with pytest.raises(ValueError, match="unknown RTCM format"):
        create_rtcm_parser("rtcm4")
