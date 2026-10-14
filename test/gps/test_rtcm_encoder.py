from types import SimpleNamespace
from typing import Any

import pytest

from flockwave.gps.rtcm import (
    RTCMV2Encoder,
    RTCMV2Parser,
    RTCMV3Encoder,
    RTCMV3Parser,
    create_rtcm_encoder,
)
from flockwave.gps.rtcm.correction import CorrectionData
from flockwave.gps.rtcm.packets import (
    RTCMV2FullCorrectionsPacket,
    RTCMV2GPSReferenceStationParametersPacket,
    RTCMV2Packet,
    RTCMV3Packet,
)
from flockwave.gps.rtcm.utils import count_bits, get_best_satellites
from flockwave.gps.vectors import ECEFCoordinate

from .rtcm_helpers import BitWriter, frame_rtcm3
from .test_rtcm_parser import (
    RTCM3_1005_EXAMPLE,
    build_1019_payload,
    build_gps_rtk_payload,
    build_msm_payload,
)


def correction(svid, scale_factor, scaled_prc, scaled_prrc, iode):
    """Stand-in for CorrectionData_ objects, which currently cannot be
    constructed due to a bug in its constructor.
    """
    return SimpleNamespace(
        svid=svid,
        scale_factor=scale_factor,
        scaled_prc=scaled_prc,
        scaled_prrc=scaled_prrc,
        iode=iode,
    )


def reference_station_packet():
    return RTCMV2GPSReferenceStationParametersPacket(
        station_id=7, position=ECEFCoordinate(4080000.12, 1400000.34, -4700000.5)
    )


def full_corrections_packet():
    return RTCMV2FullCorrectionsPacket(
        station_id=123,
        corrections=[
            correction(5, 0, -1234, 12, 77),
            correction(17, 1, 2500, -19, 3),
        ],
    )


def rtcm2_header(
    packet_type: int,
    station_id: int,
    z_count: int,
    seq: int,
    num_words: int,
    health: int = 0,
) -> BitWriter:
    return (
        BitWriter()
        .uint(8, 0x66)
        .uint(6, packet_type)
        .uint(10, station_id)
        .uint(13, z_count)
        .uint(3, seq)
        .uint(5, num_words)
        .uint(3, health)
    )


###########################################################################
# RTCM v2 encoder tests


def test_rtcm2_encoder_reference_station_data_bits():
    encoder = RTCMV2Encoder()
    data = encoder.encode(
        reference_station_packet(), time_of_week=18123, add_parities=False
    )

    expected = rtcm2_header(3, 7, 205, 0, 4)
    expected.int(32, 408000012).int(32, 140000034).int(32, -470000050)
    assert data == expected.to_bytes()


def test_rtcm2_encoder_full_corrections_data_bits():
    encoder = RTCMV2Encoder()
    data = encoder.encode(
        full_corrections_packet(), time_of_week=18123, add_parities=False
    )

    expected = rtcm2_header(1, 123, 205, 0, 4)
    expected.uint(1, 0).uint(2, 0).uint(5, 5).int(16, -1234).int(8, 12).uint(8, 77)
    expected.uint(1, 1).uint(2, 0).uint(5, 17).int(16, 2500).int(8, -19).uint(8, 3)
    expected.uint(8, 0xAA).uint(8, 0xAA)
    assert len(expected) == 6 * 24
    assert data == expected.to_bytes()


def test_rtcm2_encoder_svid_32_is_encoded_as_zero():
    packet = RTCMV2FullCorrectionsPacket(
        station_id=1,
        corrections=[correction(32, 0, 0, 0, 0)],
    )
    data = RTCMV2Encoder().encode(packet, time_of_week=0, add_parities=False)
    assert data[6] == 0x00


@pytest.mark.parametrize(
    "corr,message",
    [
        (correction(33, 0, 0, 0, 0), "SVID must not be larger than 32"),
        (correction(-1, 0, 0, 0, 0), "SVID must be non-negative"),
        (correction(1, 2, 0, 0, 0), "scale factor too large"),
        (correction(1, -1, 0, 0, 0), "scale factor must not be negative"),
    ],
)
def test_rtcm2_encoder_invalid_corrections(corr, message):
    packet = RTCMV2FullCorrectionsPacket(station_id=1, corrections=[corr])
    with pytest.raises(ValueError, match=message):
        RTCMV2Encoder().encode(packet, time_of_week=0)


def test_rtcm2_encoder_wire_format():
    # Golden output; parities are stateful so the three messages must be
    # encoded in this order with the same encoder
    encoder = RTCMV2Encoder()
    encoded = [
        encoder.encode(reference_station_packet(), time_of_week=18123),
        encoder.encode(full_corrections_packet(), time_of_week=18123),
        encoder.encode(reference_station_packet(), time_of_week=18123),
    ]

    assert encoded == [
        bytes.fromhex("664143784e6059414176675767656f4f7f5e7977636c4b4e6b4057586357"),
        bytes.fromhex("6641627752605949414f607e4d5d5670485b6258504e726d524057555559"),
        bytes.fromhex("664143786b5f667a7e525868585a754f7f5e79525c537471714057586372"),
    ]

    # Every byte on the wire carries six data bits with 01 in the upper bits
    assert all(byte & 0xC0 == 0x40 for chunk in encoded for byte in chunk)


def test_rtcm2_encoder_roundtrip():
    messages = [
        reference_station_packet(),
        RTCMV2Packet(packet_type=16, station_id=1023, bytes=b"HELLO!"),
        RTCMV2Packet(packet_type=63, station_id=0, bytes=b"pad!"),
        reference_station_packet(),
    ]
    encoder = RTCMV2Encoder()
    data = b"".join(encoder.encode(m, time_of_week=7199) for m in messages)

    packets: list[Any] = list(RTCMV2Parser().feed(data))
    assert [(p.packet_type, p.station_id) for p in packets] == [
        (3, 7),
        (16, 1023),
        (63, 0),
        (3, 7),
    ]
    assert all(p.modified_z_count == 5998 for p in packets)
    assert packets[0].position.x == pytest.approx(4080000.12)
    assert packets[0].position.z == pytest.approx(-4700000.5)
    assert packets[1].bytes.endswith(b"HELLO!")
    assert packets[2].bytes.endswith(b"pad!\xaa\xaa")


def test_rtcm2_encoder_sequence_numbers():
    encoder = RTCMV2Encoder()
    seqs = []
    for _ in range(10):
        data = encoder.encode(
            reference_station_packet(), time_of_week=0, add_parities=False
        )
        seqs.append(data[4] & 0x07)
    assert seqs == [0, 1, 2, 3, 4, 5, 6, 7, 0, 1]


@pytest.mark.parametrize(
    "time_of_week,expected",
    [(0, 0), (0.6, 1), (3600, 0), (18123, 205), (604799.4, 5999)],
)
def test_rtcm2_encoder_modified_z_count(time_of_week, expected):
    data = RTCMV2Encoder().encode(
        reference_station_packet(), time_of_week=time_of_week, add_parities=False
    )
    assert int.from_bytes(data[3:6], "big") >> 11 == expected


def test_rtcm2_encoder_uses_modified_z_count_of_message():
    message = reference_station_packet()
    message.modified_z_count = 4321
    data = RTCMV2Encoder().encode(message, add_parities=False)
    assert int.from_bytes(data[3:6], "big") >> 11 == 4321

    message.modified_z_count = None
    with pytest.raises(ValueError, match="GPS time of week"):
        RTCMV2Encoder().encode(message)


###########################################################################
# RTCM v3 encoder tests


def test_rtcm3_encoder_roundtrip_of_parsed_packets():
    frames = [
        RTCM3_1005_EXAMPLE,
        frame_rtcm3(build_gps_rtk_payload(1004)),
        frame_rtcm3(build_1019_payload()),
        frame_rtcm3(build_msm_payload(1077)),
    ]
    packets: list[Any] = list(RTCMV3Parser().feed(b"".join(frames)))
    assert len(packets) == len(frames)

    encoder = RTCMV3Encoder()
    for packet, frame in zip(packets, frames, strict=True):
        assert encoder.encode(packet) == frame
        assert encoder.encode(packet, add_parities=False) == frame[3:-3]


def test_rtcm3_encoder_raw_packet():
    payload = BitWriter().uint(12, 1234).uint(12, 0xFFF).to_bytes()
    packet = RTCMV3Packet(packet_type=1234, bytes=payload)

    encoded = RTCMV3Encoder().encode(packet)
    assert encoded == frame_rtcm3(payload)

    (parsed,) = list(RTCMV3Parser().feed(encoded))
    assert parsed.packet_type == 1234
    assert parsed.bytes == payload


@pytest.mark.parametrize(
    "format,expected",
    [("rtcm2", RTCMV2Encoder), (2, RTCMV2Encoder), ("rtcm3", RTCMV3Encoder)],
)
def test_create_rtcm_encoder(format, expected):
    encoder = create_rtcm_encoder(format)
    assert isinstance(encoder.__self__, expected)  # type: ignore


def test_create_rtcm_encoder_invalid_format():
    with pytest.raises(ValueError, match="unknown RTCM format"):
        create_rtcm_encoder("auto")


###########################################################################
# Helpers


def test_count_bits():
    assert count_bits(0) == 0
    assert count_bits(0xFFFFFF) == 24
    assert count_bits(0xEC7CD2) == 14
    for value in (1, 0x80, 0x123456, 0xABCDEF):
        assert count_bits(value) == bin(value).count("1")


def test_get_best_satellites():
    sats = [SimpleNamespace(svid=i, cnr=cnr) for i, cnr in enumerate([30, 45, 10])]
    assert [s.svid for s in get_best_satellites(sats)] == [1, 0, 2]
    assert [s.svid for s in get_best_satellites(sats, 2)] == [1, 0]


@pytest.mark.xfail(
    reason="CorrectionData() cannot be constructed; its __init__ passes "
    "arguments to object.__init__()",
    raises=TypeError,
    strict=True,
)
def test_correction_data_scale_factor():
    small = CorrectionData(svid=1, prc=-1234, prrc=12, iode=0)
    assert (small.scale_factor, small.scaled_prc, small.scaled_prrc) == (0, -1234, 12)

    large = CorrectionData(svid=1, prc=40000, prrc=-3000, iode=0)
    assert large.scale_factor == 1
    assert large.scaled_prc == 2500
    assert large.scaled_prrc == -128
