"""RTCM V2 and V3 packet types that we support in this library."""

from __future__ import annotations

from bitstring import pack, BitStream
from typing import (
    Any,
    Generic,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    TypedDict,
    Union,
)

from flockwave.gps.constants import GPS_PI, SPEED_OF_LIGHT_KM_S
from flockwave.gps.vectors import ECEFCoordinate

from .correction import CorrectionData
from .ephemeris import EphemerisData
from .utils import get_best_satellites


class RTCMParams:
    """Constants that denote common properties of values stored in RTCM
    packets.
    """

    ANTENNA_POSITION_RESOLUTION = 1e-4
    CARRIER_NOISE_RATIO_UNITS = 0.25
    CARRIER_NOISE_RATIO_HIRES_UNITS = 0.0625
    PSEUDORANGE_RESOLUTION = 2e-2
    PSEUDORANGE_DIFF_RESOLUTION = 5e-4
    INVALID_PSEUDORANGE_MARKER = 0x80000
    GLONASS_INVALID_RANGEINCR_MARKER = 0x2000
    PSEUDORANGE_UNIT_GPS = 299792.458  # speed of light, km/s
    PSEUDORANGE_UNIT_GLONASS = 599584.916
    RANGE_UNIT_MSM = 299792.458  # speed of light, km/s


class RTCMV2Packet:
    """Data structure for RTCM V2 packets."""

    _packet_classes: dict[int, RTCMV2PacketFactory] = {}

    @classmethod
    def create(cls, bitstream: BitStream) -> RTCMV2Packet:
        """Creates an RTCM V2 packet from a bit stream containing the payload
        of the packet, without the preamble and the parity bits.
        """

        original_data = bitstream.tobytes()

        packet_type: int = bitstream.read(6).uint
        station_id: int = bitstream.read(10).uint
        modified_z_count: int = bitstream.read(13).uint
        bitstream.read(11)

        packet_class = cls._packet_classes.get(packet_type)
        if packet_class:
            result = packet_class.create(packet_type, station_id, bitstream)
        else:
            result = cls(packet_type, station_id)

        result.packet_type = packet_type
        result.modified_z_count = modified_z_count
        result.bytes = original_data

        return result

    @classmethod
    def register(cls, *packet_types: int):
        """Returns a decorator that registers a class as the implementation of
        the RTCMv2 packet with the given packet type.
        """

        def decorator(klass: RTCMV2PacketFactory):
            for packet_type in packet_types:
                cls._packet_classes[packet_type] = klass
            return klass

        return decorator

    def __init__(
        self,
        packet_type: Optional[int] = None,
        station_id: Optional[int] = None,
        bytes: Optional[bytes] = None,
    ):
        """Constructor.

        Parameters:
            packet_type: the type of the packet
            station_id: the station ID of the packet
            bytes: bytes object containing the raw representation of the packet
        """
        self.packet_type = packet_type
        self.station_id = station_id
        self.bytes = bytes
        self.modified_z_count = None

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(packet_type={0.packet_type!r}, "
            "station_id={0.station_id!r}, bytes={0.bytes!r})>".format(self)
        )

    def write_body(self, bits: BitStream):
        """Writes the *body* of this packet (without the header, the
        parities etc) into the given bit array.

        Parameters:
            bits: the bit array to write the body of the packet into

        Raises:
            NotImplementedError: if the writing of this packet is not supported
        """
        raise NotImplementedError


class RTCMV2PacketFactory(Protocol):
    def create(
        self, packet_type: int, station_id: int, bitstream: BitStream
    ) -> RTCMV2Packet: ...


@RTCMV2Packet.register(1)
class RTCMV2FullCorrectionsPacket(RTCMV2Packet):
    """RTCM v2 packet that holds correction data for all satellites in view."""

    corrections: Sequence[CorrectionData]

    @classmethod
    def create(cls, packet_type: int, station_id: int, bitstream: BitStream):
        """Creates an RTCM V2 full corrections packet from a bit stream that
        is supposed to be positioned after the header of the RTCM V2
        message.
        """
        assert packet_type == 1

        num_bits = len(bitstream) - bitstream.pos
        num_corrections, remainder = divmod(num_bits, 40)
        if remainder % 8 != 0:
            raise ValueError(
                "full corrections packet must contain a "
                "fill section at the end whose length is "
                "divisible by 8, got {0}".format(remainder)
            )

        corrections = []
        for _i in range(num_corrections):
            scale_factor = bitstream.read(1).uint
            bitstream.read(2)
            svid = bitstream.read(5).uint
            scaled_prc = bitstream.read(16).intbe
            scaled_prrc = bitstream.read(8).int
            iode = bitstream.read(8).uint
            multiplier = 16**scale_factor
            prc = scaled_prc * multiplier
            prrc = scaled_prrc * multiplier
            correction = CorrectionData(svid=svid, prc=prc, prrc=prrc, iode=iode)
            corrections.append(correction)

        while bitstream.pos < bitstream.len:
            fill_byte = bitstream.read(8).uint
            if fill_byte != 0xAA:
                raise ValueError(
                    "invalid padding at the end of the full corrections "
                    "packet, expected 0xaa, got 0x{0:02x}".format(fill_byte)
                )

        return cls(station_id=station_id, corrections=corrections)

    def __init__(
        self,
        station_id: Optional[int] = None,
        corrections: Optional[list[CorrectionData]] = None,
    ):
        """Constructor.

        Parameters:
            station_id: the station ID of the packet
            corrections: the correction data for all the satellites
        """
        super().__init__(packet_type=1, station_id=station_id)
        self.corrections = corrections or []

    @property
    def num_satellites(self):
        """Returns the number of satellites for which we have correction data
        in this packet.
        """
        return len(self.corrections)

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(station_id={0.station_id!r}, "
            "corrections={0.corrections!r})>".format(self)
        )

    def write_body(self, bits: BitStream):
        """Writes the bits of a full corrections message (RTCM message type
        1) into a bit array.
        """
        for correction in self.corrections:
            if correction.scale_factor > 1:
                raise ValueError("scale factor too large")
            if correction.scale_factor < 0:
                raise ValueError("scale factor must not be negative")
            if correction.svid < 0:
                raise ValueError(
                    "correction data SVID must be non-negative, got {0}".format(
                        correction.svid
                    )
                )
            if correction.svid > 32:
                raise ValueError(
                    "correction data SVID must not be "
                    "larger than 32, got {0}".format(correction.svid)
                )
            bits += pack(
                "uint:1, uint:2, uint:5, intbe:16, int:8, uint:8",
                correction.scale_factor,
                0,
                correction.svid & 0x1F,
                correction.scaled_prc,
                correction.scaled_prrc,
                correction.iode,
            )


# TODO: maybe implement RTCM v2 partial corrections packet as well?
# (packet type = 9)


@RTCMV2Packet.register(3)
class RTCMV2GPSReferenceStationParametersPacket(RTCMV2Packet):
    """RTCM v2 packet that holds the position of a GPS reference station in
    ECEF coordinates.
    """

    position: Optional[ECEFCoordinate]

    @classmethod
    def create(cls, packet_type: int, station_id: int, bitstream: BitStream):
        """Creates an RTCM V2 GPS reference station parameters packet
        from a bit stream that is supposed to be positioned after the
        header of the RTCM V2 message.
        """
        assert packet_type == 3

        pos = (
            ECEFCoordinate(
                x=bitstream.read(32).intbe,
                y=bitstream.read(32).intbe,
                z=bitstream.read(32).intbe,
            )
            / 100  # [cm] -> [m]
        )

        return cls(station_id=station_id, position=pos)

    def __init__(
        self,
        station_id: Optional[int] = None,
        position: Optional[ECEFCoordinate] = None,
    ):
        """Constructor.

        Parameters:
            station_id: the station ID of the packet
            position: the position of the reference station
        """
        super().__init__(packet_type=3, station_id=station_id)
        self.position = position

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(station_id={0.station_id!r}, "
            "position={0.position!r})>".format(self)
        )

    def write_body(self, bits: BitStream):
        """Writes the body of this packet to the end of the given bitstream.

        Parameters:
            bits: the bit stream to append to
        """
        assert self.position is not None
        pos = self.position * 100  # [m] -> [cm]
        # uints must be encoded as big-endian
        bits += pack("intbe:32, intbe:32, intbe:32", pos.x, pos.y, pos.z)


class RTCMV3Packet:
    """Data structure for RTCM V3 packets."""

    _packet_classes: dict[int, RTCMV3PacketFactory] = {}

    packet_type: Optional[int]
    bytes: Optional[bytes]

    @classmethod
    def create(cls, bitstream: BitStream) -> RTCMV3Packet:
        """Creates an RTCM V3 packet from a bit stream containing the payload
        of the packet, without the preamble and the length bytes.
        """
        original_data = bitstream.tobytes()

        packet_type: int = bitstream.read(12).uint
        packet_class = cls._packet_classes.get(packet_type)
        if packet_class:
            result = packet_class.create(packet_type, bitstream)
        else:
            result = cls(packet_type)

        result.packet_type = packet_type
        result.bytes = original_data
        return result

    @classmethod
    def register(cls, *packet_types: int):
        """Returns a decorator that registers a class as the implementation of
        the RTCMv3 packet with the given packet type.
        """

        def decorator(klass: RTCMV3PacketFactory):
            for packet_type in packet_types:
                cls._packet_classes[packet_type] = klass
            return klass

        return decorator

    def __init__(
        self, packet_type: Optional[int] = None, bytes: Optional[bytes] = None
    ):
        """Constructor.

        Parameters:
            packet_type: the type of the packet
            bytes: bytes object containing the raw representation of the packet
        """
        self.packet_type = packet_type
        self.bytes = bytes

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(packet_type={0.packet_type!r}, "
            "bytes={0.bytes!r})>".format(self)
        )


class RTCMV3PacketFactory(Protocol):
    def create(self, packet_type: int, bitstream: BitStream) -> RTCMV3Packet: ...


class RTCMV3SatelliteInfo(Protocol):
    svid: int
    id: str


class RTCMV3GPSSatelliteInfo:
    """Satellite information object for an RTCMV3GPSRTKPacket_ packet."""

    svid: int
    id: str
    l1: dict[str, Any]
    l2: Optional[dict[str, Any]]
    temp_corrs: dict[str, Any]

    @classmethod
    def create(cls, bitstream: BitStream, is_extended: bool, has_l2: bool):
        """Creates a satellite info object from a bit stream that is supposed
        to be part of the body of an RTCMV3GPSRTKPacket_ packet (basic or
        extended).
        """
        result = cls()
        result.svid = bitstream.read(6).uint
        result.id = "G{0:02}".format(result.svid)

        # Store the raw parameters of the L1 signal first
        result.l1 = {}
        result.l1["code"] = bitstream.read(1).uint
        result.l1["pseudorange"] = cls._transform_pseudorange(bitstream.read(24).uint)
        (
            result.l1["pseudorange_diff"],
            result.l1["pseudorange_valid"],
        ) = cls._transform_pseudorange_diff(bitstream.read(20).int)
        result.l1["lock_time"] = bitstream.read(7).int
        if is_extended:
            result.l1["ambiguity"] = bitstream.read(8).uint
            result.l1["cnr"] = (
                bitstream.read(8).uint * RTCMParams.CARRIER_NOISE_RATIO_UNITS
            )

        # Now the L2 signal
        if has_l2:
            result.l2 = {}
            result.l2["code"] = bitstream.read(2).uint
            result.l2["type"] = ["2X", "2P", "2W", "2W"][result.l2["code"]]
            # TODO: gpsd source code parses this field as an uint.
            # (https://git.recluse.de/raw/mirror/gpsd.git/master/driver_rtcm3.c)
            # OTOH, ntrip source code parses this field as an int.
            # (see https://software.rtcm-ntrip.org/browser/ntrip/trunk/...
            # ...BNC/src/RTCM3/RTCM3Decoder.cpp)
            # pyUblox also parses this field as an int. int makes more sense
            # as we add this to the other pseudorange in the end.
            # Check and verify.
            result.l2["pseudorange"] = cls._transform_pseudorange(
                bitstream.read(14).int
            )
            (
                result.l2["pseudorange_diff"],
                result.l2["pseudorange_valid"],
            ) = cls._transform_pseudorange_diff(bitstream.read(20).int)
            result.l2["lock_time"] = bitstream.read(7).int
            if is_extended:
                result.l2["cnr"] = (
                    bitstream.read(8).uint * RTCMParams.CARRIER_NOISE_RATIO_UNITS
                )
        else:
            result.l2 = None

        # Postprocessing
        result.l1["type"] = "1W" if result.l1["code"] else "1C"
        if result.l2 is not None:
            result.l2["type"] = ["2X", "2P", "2W", "2W"][result.l2["code"]]

        # Calculate temp_corrs from pyUblox -- I don't know what it means yet
        result.temp_corrs = {}
        if (
            is_extended
            and result.l1["pseudorange_valid"]
            and (result.l2 is None or result.l2["pseudorange_valid"])
        ):
            result.temp_corrs["p1"] = (
                result.l1["pseudorange"] + result.l1["ambiguity"] * SPEED_OF_LIGHT_KM_S
            )
            if result.l2 is not None:
                result.temp_corrs["p2"] = (
                    result.temp_corrs["p1"] + result.l2["pseudorange"]
                )
        else:
            result.temp_corrs["p1"] = 0.0
            if has_l2:
                result.temp_corrs["p2"] = 0.0

        return result

    @property
    def cnr(self):
        if getattr(self, "l2", None) is not None:
            assert self.l2 is not None
            return self.l1["cnr"], self.l2["cnr"]
        else:
            return self.l1["cnr"]

    @property
    def json(self) -> dict[str, Any]:
        """Returns a compact JSON representation of the object."""
        keys = ["svid", "l1", "l2"]
        return {key: getattr(self, key, None) for key in keys}

    @property
    def l1_cnr(self):
        return self.l1["cnr"]

    @staticmethod
    def _transform_pseudorange(value):
        if value == RTCMParams.INVALID_PSEUDORANGE_MARKER:
            return 0.0
        else:
            return value * RTCMParams.PSEUDORANGE_RESOLUTION

    @staticmethod
    def _transform_pseudorange_diff(value):
        if value == RTCMParams.INVALID_PSEUDORANGE_MARKER:
            return 0.0, False
        else:
            return value * RTCMParams.PSEUDORANGE_DIFF_RESOLUTION, True

    def __repr__(self):
        if getattr(self, "l2", None) is None:
            return "<{0.__class__.__name__}(svid={0.svid!r}, l1={0.l1!r})>".format(self)
        else:
            return (
                "<{0.__class__.__name__}(svid={0.svid!r}, "
                "l1={0.l1!r}, l2={0.l2!r})>".format(self)
            )


class RTCMV3GLONASSSatelliteInfo:
    """Satellite information object for an RTCMV3GLONASSRTKPacket_ packet."""

    svid: int
    id: str
    l1: dict[str, Any]
    l2: Optional[dict[str, Any]]
    temp_corrs: dict[str, Any]

    @classmethod
    def create(cls, bitstream: BitStream, is_extended: bool, has_l2: bool):
        """Creates a satellite info object from a bit stream that is supposed
        to be part of the body of an RTCMV3GLONASSRTKPacket_ packet (basic or
        extended).
        """
        result = cls()

        result.svid = bitstream.read(6).uint
        result.id = "R{0:02}".format(result.svid)

        # Store the raw parameters of the L1 signal first
        result.l1 = {}
        result.l1["code"] = bitstream.read(1).uint
        result.l1["freq"] = bitstream.read(5).uint
        result.l1["pseudorange"] = cls._transform_pseudorange(bitstream.read(25).uint)
        (
            result.l1["pseudorange_diff"],
            result.l1["pseudorange_valid"],
        ) = cls._transform_pseudorange_diff(bitstream.read(20).int)
        result.l1["lock_time"] = bitstream.read(7).int
        if is_extended or has_l2:
            # According to the gpsd source, GLONASS L1&L2 basic packets
            # have ambiguity and CNR info for L1
            result.l1["ambiguity"] = bitstream.read(7).uint
            result.l1["cnr"] = (
                bitstream.read(8).uint * RTCMParams.CARRIER_NOISE_RATIO_UNITS
            )

        # Now the L2 signal
        if has_l2:
            result.l2 = {}
            result.l2["code"] = bitstream.read(2 if is_extended else 1).uint
            if is_extended:
                result.l2["freq"] = 0
            else:
                result.l2["freq"] = bitstream.read(5).uint
            result.l2["pseudorange"] = cls._transform_rangeincr(bitstream.read(14).uint)
            (
                result.l2["pseudorange_diff"],
                result.l2["pseudorange_valid"],
            ) = cls._transform_pseudorange_diff(bitstream.read(20).int)
            result.l2["lock_time"] = bitstream.read(7).int
            if not is_extended:
                result.l2["ambiguity"] = bitstream.read(7).uint
            result.l2["cnr"] = (
                bitstream.read(8).uint * RTCMParams.CARRIER_NOISE_RATIO_UNITS
            )
        else:
            result.l2 = None

        # Postprocessing
        result.l1["type"] = "1W" if result.l1["code"] else "1C"
        if result.l2 is not None:
            result.l2["type"] = ["2X", "2P", "2W", "2W"][result.l2["code"]]

        return result

    @property
    def cnr(self) -> Union[tuple[float, float], float]:
        if getattr(self, "l2", None) is not None:
            assert self.l2 is not None
            return self.l1["cnr"], self.l2["cnr"]
        else:
            return self.l1["cnr"]

    @property
    def json(self) -> dict[str, Any]:
        """Returns a compact JSON representation of the object."""
        keys = ["svid", "l1", "l2"]
        return {key: getattr(self, key, None) for key in keys}

    @property
    def l1_cnr(self):
        return self.l1["cnr"]

    @staticmethod
    def _transform_pseudorange(value):
        if value == RTCMParams.INVALID_PSEUDORANGE_MARKER:
            return 0.0
        else:
            return value * RTCMParams.PSEUDORANGE_RESOLUTION

    @staticmethod
    def _transform_rangeincr(value):
        if value == RTCMParams.GLONASS_INVALID_RANGEINCR_MARKER:
            return 0.0
        else:
            return value * RTCMParams.PSEUDORANGE_RESOLUTION

    @staticmethod
    def _transform_pseudorange_diff(value):
        if value == RTCMParams.INVALID_PSEUDORANGE_MARKER:
            return 0.0, False
        else:
            return value * RTCMParams.PSEUDORANGE_DIFF_RESOLUTION, True

    def __repr__(self):
        if getattr(self, "l2", None) is None:
            return (
                "<{0.__class__.__name__}(svid={0.svid!r}, "
                "l1={0.l1!r}, temp_corrs={0.temp_corrs!r})>".format(self)
            )
        else:
            return (
                "<{0.__class__.__name__}(svid={0.svid!r}, "
                "l1={0.l1!r}, l2={0.l2!r}, temp_corrs={0.temp_corrs!r})>".format(self)
            )


class RTCMV3MSMSignal(TypedDict):
    id: int
    cnr: Optional[float]


class RTCMV3MSMSatelliteInfo:
    """Satellite information object for an RTCMV3MSMPacket_ packet."""

    svid: int
    id: str
    signals: list[RTCMV3MSMSignal]
    cnr: Optional[float]
    range: float
    extended_info: Optional[int]
    rng_m: int
    rate: Optional[int]

    def __init__(self, svid: int, prefix: str):
        self.svid = svid
        self.id = "{1}{0:02}".format(svid, prefix)
        self.signals = []
        self.cnr = None
        self.range = 0
        self.extended_info = None
        self.rng_m = 0
        self.rate = None

    @staticmethod
    def update_satellite_data(
        objects: list[RTCMV3MSMSatelliteInfo],
        bitstream: BitStream,
        is_high_resolution: bool = False,
    ):
        """Updates multiple satellite info object with the satellite-related
        data from a bit stream that is supposed to be part of the body of an
        RTCMV3MSMPacket_ packet.
        """
        for obj in objects:
            obj.range = bitstream.read("uint:8") * RTCMParams.RANGE_UNIT_MSM

        if is_high_resolution:
            for obj in objects:
                obj.extended_info = bitstream.read("uint:4")
        else:
            for obj in objects:
                obj.extended_info = None

        for obj in objects:
            obj.rng_m = bitstream.read("uint:10")

        if is_high_resolution:
            for obj in objects:
                obj.rate = bitstream.read("int:14")
        else:
            for obj in objects:
                obj.rate = None

    @staticmethod
    def update_signal_data(
        objects: list[RTCMV3MSMSignal],
        bitstream: BitStream,
        last_digit_of_packet_type: int,
    ):
        # TODO(ntamas): store these; see the RTKLIB source code for details
        # about units and special values etc

        if last_digit_of_packet_type in (6, 7):
            for _ in objects:
                bitstream.read("int:20")  # pseudorange
            for _ in objects:
                bitstream.read("int:24")  # phase range
            for _ in objects:
                bitstream.read("uint:10")  # lock time
        else:
            for _ in objects:
                bitstream.read("int:15")  # pseudorange
            for _ in objects:
                bitstream.read("int:22")  # phase range
            for _ in objects:
                bitstream.read("uint:4")  # lock time

        for _ in objects:
            bitstream.read("bool")  # half-cycle ambiguity

        if last_digit_of_packet_type in (6, 7):
            for obj in objects:
                obj["cnr"] = (
                    bitstream.read("uint:10")
                    * RTCMParams.CARRIER_NOISE_RATIO_HIRES_UNITS
                )
        else:
            for obj in objects:
                obj["cnr"] = bitstream.read("uint:6")

        if last_digit_of_packet_type in (5, 7):  # not a typo
            for _ in objects:
                bitstream.read("int:15")  # phase range rate

    def add_empty_signal_data(self, signal_id: int):
        """Adds a placeholder for the data related to the signal with the given
        ID, to be parsed later from a bistream.
        """
        signal_data: RTCMV3MSMSignal = {"id": signal_id, "cnr": None}
        self.signals.append(signal_data)
        return signal_data

    @property
    def json(self) -> dict[str, Any]:
        """Returns a compact JSON representation of the object."""
        keys = ["svid", "range", "extended_info", "rng_m", "rate", "cnr", "signals"]
        return {key: getattr(self, key, None) for key in keys}

    def update_cnr_from_signals(self):
        """Updates the top-level CNR value from the CNR values of the individual
        observations by taking the maximum.

        We take the maximum instead of averaging (or some other magic) is because
        sometimes you have multiple signals for each satellite, but in practice
        the L1 signal is the most interesting to us for low-cost receivers, and
        the CNR of the L1 signal is usually the highest.
        """
        self.cnr = (
            max(signal.get("cnr") or 0.0 for signal in self.signals)
            if self.signals
            else None
        )

    def __repr__(self):
        return (
            "<{0.__class__.__name__}("
            "svid={0.svid!r}, "
            "range={0.range!r}, "
            "rng_m={0.rng_m!r}, "
            "rate={0.rate!r}, "
            "cnr={0.cnr!r}, "
            "signals={0.signals!r}"
            ")>"
        ).format(self)


T = TypeVar("T", bound="RTCMV3SatelliteInfo")


class SatelliteContainerMixin(Generic[T]):
    """Mixin class for RTK packets that hold information about multiple
    satellites.
    """

    satellites: list[T]

    def best_satellites(self, count: Optional[int] = None) -> list[T]:
        """Returns the given number of satellites from the satellite info
        structure with the best signal-to-noise ratios.
        """
        return get_best_satellites(self.satellites, count)

    @property
    def num_satellites(self) -> int:
        return len(self.satellites)


@RTCMV3Packet.register(1001, 1002, 1003, 1004)
class RTCMV3GPSRTKPacket(RTCMV3Packet, SatelliteContainerMixin[RTCMV3GPSSatelliteInfo]):
    """RTCM v3 GPS RTK packet representation.

    This class is used to represent RTCM v3 packets of type 1001, 1002,
    1003 and 1004.
    """

    station_id: int
    tow: float
    sync: bool
    smoothed: bool
    smoothing_interval: int

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        """Creates an RTCM v3 GPS RTK packet from the given bit stream.

        Parameters:
            packet_type: the type of the packet (1001, 1002, 1003 or 1004)
            bitstream: the body of the packet, starting at the station ID

        Returns:
            the packet data parsed out of the bitstream
        """
        assert packet_type in (1001, 1002, 1003, 1004)

        has_l2 = packet_type in (1003, 1004)
        is_extended = packet_type in (1002, 1004)

        result = cls(packet_type)
        result.station_id = bitstream.read(12).uint
        result.tow = bitstream.read(30).uint * 0.001
        result.sync = bitstream.read(1).bool
        satellite_count: int = bitstream.read(5).uint
        result.smoothed = bitstream.read(1).bool
        result.smoothing_interval = bitstream.read(3).uint
        result.satellites = []

        for _i in range(satellite_count):
            result.satellites.append(
                RTCMV3GPSSatelliteInfo.create(bitstream, is_extended, has_l2)
            )

        return result

    @property
    def json(self) -> dict[str, Any]:
        """Returns a compact JSON representation of the packet."""
        keys = [
            "packet_type",
            "station_id",
            "tow",
            "sync",
            "smoothed",
            "smoothing_interval",
        ]
        result = {key: getattr(self, key, None) for key in keys}
        result["satellites"] = [sat_info.json for sat_info in self.satellites]
        return result

    @property
    def time_of_week(self) -> float:
        """Alias for ``tow``."""
        return self.tow

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(station_id={0.station_id!r}, "
            "tow={0.tow!r}, sync={0.sync!r}, "
            "smoothed={0.smoothed!r}, "
            "smoothing_interval={0.smoothing_interval!r}, "
            "satellites={0.satellites!r}"
            ")>".format(self)
        )


@RTCMV3Packet.register(1005, 1006)
class RTCMV3StationaryAntennaPacket(RTCMV3Packet):
    """RTCM v3 stationary antenna position packet representation."""

    station_id: int
    system: int
    is_reference_station: bool
    single_receiver: bool
    antenna_height: Optional[float]
    position: ECEFCoordinate

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        """Creates an RTCM v3 stationary antenna packet from the given bit
        stream.

        Parameters:
            packet_type: the type of the packet (1005 or 1006)
            bitstream: the body of the packet, starting at the station ID

        Returns:
            the packet data parsed out of the bitstream
        """
        assert packet_type == 1005 or packet_type == 1006

        result = cls(packet_type)
        result.station_id = bitstream.read(12).uint

        bitstream.read(6)  # reserved
        result.system = bitstream.read(3).uint
        result.is_reference_station = bitstream.read(1).bool
        ref_x = bitstream.read(38).int
        result.single_receiver = bitstream.read(1).bool
        bitstream.read(1)
        ref_y = bitstream.read(38).int
        bitstream.read(2)
        ref_z = bitstream.read(38).int

        if packet_type == 1005:
            # No height information in this packet
            result.antenna_height = None
        elif packet_type == 1006:
            # This packet has height information
            result.antenna_height = (
                bitstream.read(16).uint * RTCMParams.ANTENNA_POSITION_RESOLUTION
            )
        else:
            raise ValueError("Invalid packet type: {0}".format(packet_type))

        result.position = (
            ECEFCoordinate(x=ref_x, y=ref_y, z=ref_z)
            * RTCMParams.ANTENNA_POSITION_RESOLUTION
        )
        return result

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(packet_type={0.packet_type!r}, "
            "position={0.position!r}, "
            "antenna_height={0.antenna_height!r}, "
            "system={0.system!r}, "
            "is_reference_station={0.is_reference_station!r}, "
            "single_receiver={0.single_receiver!r}"
            ")>".format(self)
        )


@RTCMV3Packet.register(1007, 1008)
class RTCMV3AntennaDescriptorPacket(RTCMV3Packet):
    """RTCM v3 antenna descriptor packet representation. This packet
    contains information about the station ID, setup ID and serial number
    of the antenna as well as a short description.
    """

    station_id: int
    descriptor: str
    setup_id: int
    serial: Optional[str]

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        """Creates an RTCM v3 antenna descriptor packet from the given bit
        stream.

        Parameters:
            packet_type: the type of the packet (must be 1007 or 1008)
            bitstream: the body of the packet, starting at the station ID

        Returns:
            the packet data parsed out of the bitstream
        """
        assert packet_type in (1007, 1008)

        result = cls(packet_type)
        result.station_id = bitstream.read(12).uint
        result.descriptor = cls._read_string(bitstream)
        result.setup_id = bitstream.read(8).uint
        if packet_type == 1008:
            result.serial = cls._read_string(bitstream)
        else:
            result.serial = None

        return result

    @staticmethod
    def _read_string(bitstream: BitStream):
        n = bitstream.read(8).uint
        return "".join(chr(bitstream.read(8).uint) for _ in range(n))

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(packet_type={0.packet_type!r}, "
            "station_id={0.station_id!r}, "
            "descriptor={0.descriptor!r}, "
            "setup_id={0.setup_id!r}, "
            "serial={0.serial!r}"
            ")>".format(self)
        )


@RTCMV3Packet.register(1009, 1010, 1011, 1012)
class RTCMV3GLONASSRTKPacket(
    RTCMV3Packet, SatelliteContainerMixin[RTCMV3GLONASSSatelliteInfo]
):
    station_id: int
    tod: float
    sync: bool
    smoothed: bool
    smoothing_interval: int

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        assert packet_type in (1009, 1010, 1011, 1012)

        has_l2 = packet_type in (1011, 1012)
        is_extended = packet_type in (1010, 1012)

        result = cls(packet_type)
        result.station_id = bitstream.read(12).uint
        result.tod = bitstream.read(27).uint * 0.001
        result.sync = bitstream.read(1).bool
        satellite_count = bitstream.read(5).uint
        result.smoothed = bitstream.read(1).bool
        result.smoothing_interval = bitstream.read(3).uint
        result.satellites = []

        for _i in range(satellite_count):
            result.satellites.append(
                RTCMV3GLONASSSatelliteInfo.create(bitstream, is_extended, has_l2)
            )

        return result

    @property
    def json(self) -> dict[str, Any]:
        """Returns a compact JSON representation of the packet."""
        keys = [
            "packet_type",
            "station_id",
            "tod",
            "sync",
            "smoothed",
            "smoothing_interval",
        ]
        result = {key: getattr(self, key, None) for key in keys}
        result["satellites"] = [sat_info.json for sat_info in self.satellites]
        return result

    @property
    def time_of_day(self) -> float:
        """Alias for ``tod``."""
        return self.tod

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(station_id={0.station_id!r}, "
            "tod={0.tod!r}, sync={0.sync!r}, "
            "smoothed={0.smoothed!r}, "
            "smoothing_interval={0.smoothing_interval!r}, "
            "satellites={0.satellites!r}"
            ")>".format(self)
        )


@RTCMV3Packet.register(1019)
class RTCMV3GPSEphemerisPacket(RTCMV3Packet):
    """RTCM v3 packet holding GPS ephemeris data."""

    svid: int
    week: int
    acc: int
    l2code: int
    i_dot: int
    iode: int
    toc: int
    af2: int
    af1: int
    af0: int
    iodc: int
    crs: int
    delta_n: int
    m0: int
    cuc: int
    eccentricity: int
    cus: int
    sqrt_a: int
    toe: int
    cic: int
    omega0: int
    cis: int
    i0: int
    crc: int
    omega: int
    omega_dot: int
    tgd: int
    health: int
    l2p: int
    fit: int

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        """Creates an RTCM v3 GPS ephemeris packet from the given bit
        stream.

        Parameters:
            packet_type: the type of the packet (must be 1019)
            bitstream: the body of the packet, starting at the
                station ID

        Returns:
            the packet data parsed out of the bitstream
        """
        assert packet_type == 1019

        result = cls(packet_type)

        # I have no idea what these mean, they are copied almost unmodified
        # from pyUblox
        #
        # The field names are renamed match the ones here:
        # http://www.trimble.com/OEM_ReceiverHelp/V4.44/en/ICD_Pkt_Response55h_GPSEph.html

        result.svid = bitstream.read(6).uint
        result.week = bitstream.read(10).uint
        result.acc = bitstream.read(4).uint
        result.l2code = bitstream.read(2).uint
        result.i_dot = bitstream.read(14).int  # 3
        result.iode = bitstream.read(8).uint  # 3
        result.toc = bitstream.read(16).uint  # 3
        result.af2 = bitstream.read(8).int  # 3
        result.af1 = bitstream.read(16).int  # 3
        result.af0 = bitstream.read(22).int  # 3
        result.iodc = bitstream.read(10).uint
        result.crs = bitstream.read(16).int  #
        result.delta_n = bitstream.read(16).int  # 2
        result.m0 = bitstream.read(32).int  # 2
        result.cuc = bitstream.read(16).int  #
        result.eccentricity = bitstream.read(32).uint  # 2
        result.cus = bitstream.read(16).int  #
        result.sqrt_a = bitstream.read(32).uint  # 2
        result.toe = bitstream.read(16).uint  # 3
        result.cic = bitstream.read(16).int  #
        result.omega0 = bitstream.read(32).int  # 2
        result.cis = bitstream.read(16).int  #
        result.i0 = bitstream.read(32).int  # 2
        result.crc = bitstream.read(16).int  #
        result.omega = bitstream.read(32).int  # 2
        result.omega_dot = bitstream.read(24).int  # 2
        result.tgd = bitstream.read(8).int  # 3
        result.health = bitstream.read(6).uint
        result.l2p = bitstream.read(1).uint
        result.fit = bitstream.read(1).uint

        return result

    @property
    def ephemeris(self):
        """Constructs an ``EphemerisData`` object from the raw contents of
        this packet.
        """
        params = {
            "cuc": self.cuc / (2**29),
            "cus": self.cus / (2**29),
            "cic": self.cic / (2**29),
            "cis": self.cis / (2**29),
            "crc": self.crc / (2**5),
            "crs": self.crs / (2**5),
            # Group delay differential between L1 and L2 [s]
            "tgd": self.tgd / (2**31),
            # Polynomial clock correction coefficient [s]
            "af0": self.af0 / (2**31),
            # Polynomial clock correction coefficient [s/s]
            "af1": self.af1 / (2**43),
            # Polynomial clock correction coefficient [s/s^2]
            "af2": self.af2 / (2**55),
            # Time of week [s]
            "toe": self.toe * (2**4),
            # Clock reference time of week [s]
            "toc": self.toc * (2**4),
            # Mean motion difference from computed value [rad]
            "delta_n": self.delta_n * GPS_PI / (2**43),
            # Mean anomaly at reference time [rad]
            "m0": self.m0 * GPS_PI / (2**31),
            # Eccentricity of satellite orbit
            "eccentricity": self.eccentricity / (2**33),
            # Square root of the semi-major axis of the orbit
            "sqrt_a": self.sqrt_a / (2**19),
            "omega0": self.omega0 * GPS_PI / (2**31),
            "i0": self.i0 * GPS_PI / (2**31),
            "omega": self.omega * GPS_PI / (2**31),
            "omega_dot": self.omega_dot * GPS_PI / (2**43),
            "i_dot": self.i_dot * GPS_PI / (2**43),
            "iodc": self.iodc,
            "iode": self.iode,
            "week": self.week,
            "tow": None,
            "flags": None,
            "svid": self.svid,
        }

        return EphemerisData(**params)

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(svid={0.svid!r}), "
            "ephemeris={0.ephemeris!r}>".format(self)
        )


@RTCMV3Packet.register(1033)
class RTCMV3ExtendedAntennaDescriptorPacket(RTCMV3Packet):
    """RTCM v3 antenna descriptor packet representation. This packet
    contains information about the station ID, setup ID, serial number,
    receiver and firmware version of the antenna as well as a short
    description.
    """

    station_id: int
    descriptor: str
    setup_id: int
    serial: str
    receiver: str
    firmware: str

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        """Creates an RTCM v3 extended antenna descriptor packet from the
        given bit stream.

        Parameters:
            packet_type: the type of the packet (must be 1033)
            bitstream: the body of the packet, starting at the
                station ID

        Returns:
            the packet data parsed out of the bitstream
        """
        assert packet_type == 1033

        result = cls(packet_type)
        result.station_id = bitstream.read(12).uint
        result.descriptor = cls._read_string(bitstream)
        result.setup_id = bitstream.read(8).uint
        result.serial = cls._read_string(bitstream)
        result.receiver = cls._read_string(bitstream)
        result.firmware = cls._read_string(bitstream)

        return result

    @staticmethod
    def _read_string(bitstream):
        n = bitstream.read(8).uint
        return "".join(chr(bitstream.read(8).uint) for _ in range(n))

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(packet_type={0.packet_type!r}, "
            "station_id={0.station_id!r}, "
            "descriptor={0.descriptor!r}, "
            "setup_id={0.setup_id!r}, "
            "serial={0.serial!r}, "
            "receiver={0.receiver!r}, "
            "firmware={0.firmware!r}"
            ")>".format(self)
        )


# TODO: 1020 -- GLONASS ephemeris


# fmt: off
SUPPORTED_RTCMV3_MSM_PACKET_TYPES: tuple[int, ...] = (
    1074, 1075, 1076, 1077,
    1084, 1085, 1086, 1087,
    1094, 1095, 1096, 1097,
    1114, 1115, 1116, 1117,
    1124, 1125, 1126, 1127,
)
# fmt: on


@RTCMV3Packet.register(*SUPPORTED_RTCMV3_MSM_PACKET_TYPES)
class RTCMV3MSMPacket(RTCMV3Packet, SatelliteContainerMixin[RTCMV3MSMSatelliteInfo]):
    """RTCM v3 MSM (multiple signal message) packet representation.

    This class is used to represent RTCM v3 packets of type 1071 to 1077 (GPS),
    1081 to 1087 (GLONASS), 1091 to 1097 (Galileo), 1111 to 1117 (QZSS) and
    1121 to 1127 (BeiDou).

    Currently we have implemented support for packet types ending in 4, 5, 6
    and 7 only; these two are the most common.
    """

    station_id: int
    tow: float
    sync: bool
    iod: int
    time_s: int
    clk_str: int
    clk_ext: int
    smoothed: bool
    smoothing_interval: int

    @classmethod
    def create(cls, packet_type: int, bitstream: BitStream):
        """Creates an RTCM v3 GPS MSM packet from the given bit stream.

        Parameters:
            packet_type: the type of the packet
            bitstream: the body of the packet, starting at the station ID

        Returns:
            the packet data parsed out of the bitstream
        """
        assert packet_type in SUPPORTED_RTCMV3_MSM_PACKET_TYPES

        last_digit: int = packet_type % 10
        has_hires_sat_data = last_digit == 5 or last_digit == 7

        result = cls(packet_type)

        result.station_id = bitstream.read(12).uint
        result.tow = bitstream.read(30).uint * 0.001
        result.sync = bitstream.read(1).bool
        result.iod = bitstream.read(3).uint

        result.time_s = bitstream.read(7).uint
        result.clk_str = bitstream.read(2).uint
        result.clk_ext = bitstream.read(2).uint
        result.smoothed = bitstream.read(1).bool
        result.smoothing_interval = bitstream.read(3).uint

        satellite_mask = bitstream.read(64)
        satellite_ids = [index + 1 for index, bit in enumerate(satellite_mask) if bit]  # type: ignore
        num_satellites = len(satellite_ids)

        signal_mask = bitstream.read(32)
        signal_ids = [index + 1 for index, bit in enumerate(signal_mask) if bit]  # type: ignore
        num_signals = len(signal_ids)

        cell_mask_length = num_satellites * num_signals
        cell_mask = bitstream.read(cell_mask_length)

        if packet_type < 1080:
            # GPS packet
            satellite_id_prefix = "G"
        elif packet_type < 1090:
            # GLONASS packet
            satellite_id_prefix = "R"
        elif packet_type < 1100:
            # Galileo packet
            satellite_id_prefix = "E"
        elif packet_type < 1120:
            # QZSS packet
            satellite_id_prefix = "Q"
        else:
            # BeiDou packet
            satellite_id_prefix = "C"

        # Read satellite-specific information first
        result.satellites = [
            RTCMV3MSMSatelliteInfo(svid, satellite_id_prefix) for svid in satellite_ids
        ]
        RTCMV3MSMSatelliteInfo.update_satellite_data(
            result.satellites,
            bitstream,
            is_high_resolution=has_hires_sat_data,
        )

        # Create empty placeholders in the satellite info objects for each cell
        # (satellite-signal combo)
        cell_mask_iter = iter(cell_mask)
        cells_to_signals = []
        for i in range(num_satellites):
            for signal_id in signal_ids:
                bit = next(cell_mask_iter)
                if bit:
                    signal_data = result.satellites[i].add_empty_signal_data(
                        signal_id=signal_id
                    )
                    cells_to_signals.append(signal_data)

        # Read signal information for each cell (satellite-signal combo)
        RTCMV3MSMSatelliteInfo.update_signal_data(
            cells_to_signals,
            bitstream,
            last_digit_of_packet_type=last_digit,
        )

        for satellite in result.satellites:
            satellite.update_cnr_from_signals()

        return result

    @property
    def json(self) -> dict[str, Any]:
        """Returns a compact JSON representation of the packet."""
        keys = [
            "packet_type",
            "station_id",
            "tow",
            "sync",
            "iod",
            "time_s",
            "clk_str",
            "clk_ext",
            "smoothed",
            "smoothing_interval",
        ]
        result = {key: getattr(self, key, None) for key in keys}
        result["satellites"] = [sat_info.json for sat_info in self.satellites]
        return result

    @property
    def time_of_week(self):
        """Alias for ``tow``."""
        return self.tow

    def __repr__(self):
        return (
            "<{0.__class__.__name__}(station_id={0.station_id!r}, "
            "tow={0.tow!r}, sync={0.sync!r}, iod={0.iod!r}, "
            "time_s={0.time_s!r}, "
            "clk_str={0.clk_str!r}, clk_ext={0.clk_ext!r}, "
            "smoothed={0.smoothed!r}, "
            "smoothing_interval={0.smoothing_interval!r}, "
            "satellites={0.satellites!r}"
            ")>".format(self)
        )


#: Type alias for RTCMv2 and RTCMv3 packets
RTCMPacket = Union[RTCMV2Packet, RTCMV3Packet]
