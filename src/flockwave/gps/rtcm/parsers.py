"""Parser that parses streamed RTCM V3 messages."""

from abc import ABCMeta, abstractmethod
from builtins import bytes, range
from bitstring import ConstBitStream
from enum import Enum
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Optional,
    TypeVar,
    Union,
)

from flockwave.gps.crc import crc24q

from .errors import ChecksumError
from .packets import RTCMPacket, RTCMV2Packet, RTCMV3Packet


__all__ = (
    "create_rtcm_parser",
    "RTCMV2Parser",
    "RTCMV3Parser",
    "RTCMFormatAutodetectingParser",
)


class RTCMV2ParserState(Enum):
    START = "START"
    LENGTH = "LENGTH"
    PAYLOAD = "PAYLOAD"


class RTCMV3ParserState(Enum):
    START = "START"
    LENGTH = "LENGTH"
    PAYLOAD = "PAYLOAD"
    PARITY = "PARITY"


T = TypeVar("T")


class RTCMParser(Generic[T], metaclass=ABCMeta):
    """Interface specification for RTCM V2 and V3 parsers."""

    @abstractmethod
    def feed(self, data: bytes) -> Iterable[T]:
        """Feeds some raw bytes into the RTCM parser.

        Parameters:
            data: the bytes to feed into the parser

        Returns:
            whole RTCM packets that have been parsed after the bytes have been
            forwarded to the parser
        """
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Resets the state of the parser. The default implementation is
        empty; should be overridden in subclasses.
        """
        raise NotImplementedError


class RTCMParserBase(RTCMParser[T]):
    """Base class for RTCM V2 and V3 parsers."""

    def __init__(self, max_packet_length: Optional[int] = None):
        """Constructor.

        :param callback: a function to call for each successfully decoded
            RTCM frame
        :type callback: callable
        :param max_packet_length: maximum length of RTCM packets that we
            intend to process. Helps the parser with the synchronization
            issues when the data is coming from an RTCM stream and we are
            potentially reading the stream from the middle of an RTCM
            packet.
        :type max_packet_length: int or None
        """
        self.max_packet_length = max_packet_length
        self.reset()

    def feed(self, data: bytes) -> Iterable[T]:
        result = []
        for byte in data:
            try:
                packet = self._feed_byte(byte)
                if packet is not None:
                    result.append(packet)
            except ChecksumError as ex:
                result.extend(
                    self._recover_from_checksum_mismatch(ex.packet, ex.parity)
                )

        return result

    @abstractmethod
    def _feed_byte(self, byte: int) -> Optional[T]:
        """Feeds a new byte to the parser.

        Returns a parsed packet if the new byte resulted in a full packet, or
        `None` if no new packet was parsed from the stream by adding the
        given byte.
        """
        raise NotImplementedError

    @abstractmethod
    def _recover_from_checksum_mismatch(
        self, packet: bytearray, parity: bytearray
    ) -> Iterable[T]:
        """Tries to recover from a checksum-mismatched packet by looking for
        the next preamble byte in the stream and truncating the internal
        packet buffer appropriately.

        Parameters:
            packet: the body of the last raw packet that resulted in a
                checksum mismatch
            parity: the parity bytes that resulted in a checksum mismatch

        Returns:
            whole RTCM packets that have been parsed during recovering from a
            checksum error
        """
        raise NotImplementedError


class RTCMV2Parser(RTCMParserBase[RTCMV2Packet]):
    """Parser that parses RTCM V2 messages from a stream of bytes."""

    PREAMBLE = 0x66

    PARITY_FORMULA = [
        0xBB1F3480,
        0x5D8F9A40,
        0xAEC7CD00,
        0x5763E680,
        0x6BB1F340,
        0x8B7A89C0,
    ]

    _state: RTCMV2ParserState
    _length: int
    _num_bits: int
    _packet: bytearray

    def __init__(self, *args, **kwds):
        """Constructor."""
        self._word = 0
        super().__init__(*args, **kwds)
        self._lsb_reversed = [self._reverse_six_lsb(i) for i in range(64)]

    def reset(self) -> None:
        """Resets the state of the parser."""
        self._state = RTCMV2ParserState.START
        self._length = 0
        self._num_bits = 0
        self._packet = bytearray()

    def _decode_word(self) -> bool:
        """Decodes a single data word found in ``self._word`` and appends
        the three decoded bytes to ``self._packet``.

        Returns:
            ``True`` if the decoding was successful, ``False`` if there was a
            checksum error.
        """
        word = self._word
        parity = 0
        if word & 0x40000000:
            word ^= 0x3FFFFFC0
        for mask in self.PARITY_FORMULA:
            parity <<= 1
            w = (word & mask) >> 6
            while w:
                parity ^= w & 1
                w >>= 1
        if parity == word & 0x3F:
            for i in range(3):
                self._packet.append((word >> (22 - i * 8)) & 0xFF)
            return True
        else:
            return False

    def _feed_byte(self, byte: int) -> Optional[RTCMV2Packet]:
        if byte & 0xC0 != 0x40:
            # Reset the parser if the upper two bits != 01
            self.reset()
            return

        byte = self._lsb_reversed[byte & 0x3F]

        # self._word is a rolling window containing the last 32 bits from
        # the stream (30 data bits plus 2 parity bits from the previous
        # word, if any)
        self._word = ((self._word << 6) | byte) & 0xFFFFFFFF

        if self._state == RTCMV2ParserState.START:
            # Look for the preamble in the front of the current word
            preamb = (self._word >> 22) & 0xFF
            if self._word & 0x40000000:
                preamb ^= 0xFF
            if preamb == self.PREAMBLE:
                # Try decoding the current word
                if self._decode_word():
                    self._num_bits = 0
                    self._state = RTCMV2ParserState.LENGTH
        else:
            # Wait until we have 30 bits again, then decode the word
            self._num_bits += 6
            if self._num_bits < 30:
                return
            self._num_bits = 0
            if self._decode_word():
                # Got another three bytes
                if self._state == RTCMV2ParserState.LENGTH:
                    # Got the length
                    self._length = (self._packet[5] >> 3) * 3 + 6
                    if self._length <= 6:
                        self.reset()
                    else:
                        self._state = RTCMV2ParserState.PAYLOAD
                elif self._state == RTCMV2ParserState.PAYLOAD:
                    # Got another three bytes from the payload
                    if len(self._packet) >= self._length:
                        # Decode the message
                        result = self._process_packet(self._packet)
                        self.reset()
                        return result
                else:
                    self.reset()
            else:
                # Checksum error, try recovery.
                self.reset()

    def _process_packet(self, packet: bytearray) -> RTCMV2Packet:
        """Processes a packet that has passed the parity test.

        Parameters:
            packet: the raw packet

        Returns:
            the parsed RTCM V2 packet
        """
        bitstream = ConstBitStream(packet[1:])
        return RTCMV2Packet.create(bitstream)

    def _recover_from_checksum_mismatch(
        self, packet: bytearray, parity: bytearray
    ) -> Iterable[RTCMV2Packet]:
        """Tries to recover from a checksum-mismatched packet by looking for
        the next preamble byte in the stream and truncating the internal
        packet buffer appropriately.

        Parameters:
            packet: the body of the last raw packet that resulted in a
                checksum mismatch
            parity: the parity bytes that resulted in a checksum mismatch

        Returns:
            whole RTCM packets that have been parsed during recovering from a
            checksum error
        """
        self.reset()
        return []

    @staticmethod
    def _reverse_six_lsb(byte: int) -> int:
        """Reverses the six least significant bits of the given byte.
        The byte is assumed to be between 0 (inclusive) and 64 (exclusive).

        :param byte: the byte to reverse
        :return: the reversed byte
        """
        result = 0
        for _i in range(6):
            result = (result << 1) + (byte & 1)
            byte >>= 1
        return result


class RTCMV3Parser(RTCMParserBase[RTCMV3Packet]):
    """Parser that parses RTCM V3 messages from a stream of bytes."""

    PREAMBLE = 0xD3

    _state: RTCMV3ParserState
    _packet_length: int
    _packet: bytearray
    _parity: bytearray

    def reset(self) -> None:
        """Resets the state of the parser."""
        self._state = RTCMV3ParserState.START
        self._packet_length = 0
        self._packet = bytearray()
        self._parity = bytearray()

    def _check_parity(self, packet: bytearray, parity: bytearray) -> bool:
        """Checks whether the given packet has the given parity.

        Parameters:
            packet: the raw packet
            parity: the parity bytes of the packet

        Returns:
            whether the packet has the given parity
        """
        return crc24q(packet) == (parity[0] << 16) + (parity[1] << 8) + (parity[2])

    def _feed_byte(self, byte: int) -> Optional[RTCMV3Packet]:
        if self._state == RTCMV3ParserState.START:
            # Just waiting for the preamble
            if byte != self.PREAMBLE:
                return None
            else:
                self._packet = bytearray([self.PREAMBLE])
                self._parity = bytearray()
                self._state = RTCMV3ParserState.LENGTH
        elif self._state == RTCMV3ParserState.LENGTH:
            # Reading packet length
            self._packet.append(byte)
            if len(self._packet) >= 3:
                self._packet_length = (
                    ((self._packet[1] & 0x03) << 8) + self._packet[2] + 3
                )
                if (
                    self.max_packet_length is not None
                    and self._packet_length > self.max_packet_length
                ):
                    # We are probably out of sync, let's just reset the parser
                    self.reset()
                elif self._packet_length > 3:
                    self._state = RTCMV3ParserState.PAYLOAD
                else:
                    self._state = RTCMV3ParserState.PARITY
        elif self._state == RTCMV3ParserState.PAYLOAD:
            # Reading payload byte
            self._packet.append(byte)
            if len(self._packet) >= self._packet_length:
                self._state = RTCMV3ParserState.PARITY
        elif self._state == RTCMV3ParserState.PARITY:
            # Reading parity byte
            self._parity.append(byte)
            if len(self._parity) >= 3:
                self._state = RTCMV3ParserState.START
                if self._check_parity(self._packet, self._parity):
                    return self._process_packet(self._packet)
                else:
                    raise ChecksumError(self._packet, self._parity)
        return None

    def _process_packet(self, packet: bytearray) -> RTCMV3Packet:
        """Processes a packet that has passed the parity test.

        Parameters:
            packet: the raw packet

        Returns:
            the parsed RTCM V3 packet
        """
        bitstream = ConstBitStream(packet[3:])
        return RTCMV3Packet.create(bitstream)

    def _recover_from_checksum_mismatch(self, packet: bytearray, parity: bytearray):
        """Tries to recover from a checksum-mismatched packet by looking for
        the next preamble byte in the stream and truncating the internal
        packet buffer appropriately.

        Parameters:
            packet: the body of the last raw packet that resulted in a
                checksum mismatch
            parity: the parity bytes that resulted in a checksum mismatch

        Returns:
            whole RTCM packets that have been parsed during recovering from a
            checksum error
        """
        self.reset()

        buf = bytes(packet + parity)
        next_preamble_byte = buf.find(bytes([self.PREAMBLE]), 1)
        if next_preamble_byte >= 1:
            return self.feed(buf[next_preamble_byte:])
        else:
            return []


class RTCMFormatAutodetectingParser(RTCMParser[RTCMPacket]):
    """RTCM packet parser that attempts to automatically detect the format
    of the incoming bytes and choose from RTCM v2 or v3.

    This is done by feeding all the incoming bytes in parallel to both an
    RTCM v2 and an RTCM v3 parser. The first parser that successfully
    generates a packet will be used and the other will be discarded.
    """

    _subparsers: list[RTCMParserBase[Any]]
    _chosen_subparser: Optional[RTCMParserBase[Any]]
    _pending_checksum_errors: list[tuple[RTCMParserBase, ChecksumError]]

    def __init__(self, *args, **kwds):
        """Constructor."""
        self._subparsers = [RTCMV2Parser(*args, **kwds), RTCMV3Parser(*args, **kwds)]
        self.reset()

    def reset(self) -> None:
        """Resets the state of the parser. The default implementation is
        empty; should be overridden in subclasses.
        """
        for parser in self._subparsers:
            parser.reset()

        self._chosen_subparser = None
        if len(self._subparsers) == 1:
            self._chosen_subparser = self._subparsers[0]

        self._pending_checksum_errors = []

    def feed(self, data: bytes) -> Iterable[RTCMPacket]:
        """Feeds some raw bytes into the RTCM parser.

        Parameters:
            data: the bytes to feed into the parser

        Returns:
            whole RTCM packets that have been parsed after the bytes have been
            forwarded to the parser
        """
        result = []

        for byte in data:
            del self._pending_checksum_errors[:]

            try:
                packet = self._feed_byte(byte)
                if packet is not None:
                    result.append(packet)
            except ChecksumError as ex:
                # We get here if we have already chosen the subparser
                # and the chosen subparser subsequently throws checksum
                # errors, so the check below is not strictly necessary; it is
                # there to make Pylance happy
                if self._chosen_subparser:
                    recover = self._chosen_subparser._recover_from_checksum_mismatch
                    result.extend(recover(ex.packet, ex.parity))

            if self._chosen_subparser is None:
                # We get here if we have not chosen a subparser yet and
                # we must handle pending checksum errors
                packets, parser = self._process_pending_checksum_errors()
                if packets:
                    result.extend(packets)
                    self._chosen_subparser = parser

        return result

    def _feed_byte(self, byte: int) -> Optional[RTCMPacket]:
        """Feeds a new byte to the parser."""
        if self._chosen_subparser is not None:
            return self._chosen_subparser._feed_byte(byte)
        else:
            for parser in self._subparsers:
                try:
                    result = parser._feed_byte(byte)
                except ChecksumError as ex:
                    self._pending_checksum_errors.append((parser, ex))
                    result = None
                if result is not None:
                    self._chosen_subparser = parser
                    return result

    def _process_pending_checksum_errors(
        self,
    ) -> tuple[Iterable[RTCMPacket], Optional[RTCMParserBase]]:
        """Processes unprocessed checksum errors from subparsers to see
        if any of the recovery attempts yield proper packets. Returns a
        list of the recovered packets, or an empty list if there was
        nothing to recover.
        """
        for parser, ex in self._pending_checksum_errors:
            recovered_packets = parser._recover_from_checksum_mismatch(
                ex.packet, ex.parity
            )
            if recovered_packets:
                return list(recovered_packets), parser
        return [], None


def create_rtcm_parser(
    format: Union[int, str] = "auto",
) -> Callable[[bytes], Iterable[RTCMPacket]]:
    """Creates an RTCM parser function that is suitable to be used in
    conjunction with the channels from the ``flockwave-conn`` module.

    Parameters:
        format: the RTCM format that the parser will use; must be one of
            ``rtcm2``, ``rtcm3`` or ``auto``. 2 and 3 as integers can be used
            as aliases for ``rtcm2`` and ``rtcmv3``.

    Returns:
        the parser function
    """
    if format == "rtcm2" or format == 2:
        return RTCMV2Parser().feed
    elif format == "rtcm3" or format == 3:
        return RTCMV3Parser().feed
    elif format == "auto":
        return RTCMFormatAutodetectingParser().feed
    else:
        raise ValueError(f"unknown RTCM format: {format!r}")


def main():
    from contextlib import ExitStack
    import sys

    parser = create_rtcm_parser("rtcm3")
    with ExitStack() as stack:
        if len(sys.argv) > 1:
            fp = stack.enter_context(open(sys.argv[1], "rb"))
        else:
            fp = sys.stdin.buffer
        while True:
            chunk = fp.read(16)
            if not chunk:
                break

            for packet in parser(chunk):
                if hasattr(packet, "json"):
                    print(packet.json)  # type: ignore
                else:
                    pass
                    # print(repr(packet))


if __name__ == "__main__":
    main()
