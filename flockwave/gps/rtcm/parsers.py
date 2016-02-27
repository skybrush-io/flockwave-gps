"""Parser that parses streamed RTCM V3 messages."""

from __future__ import division, print_function

from abc import ABCMeta, abstractmethod
from bitstring import ConstBitStream
from enum import Enum
from flockwave.gps.crc import crc24q
from six import with_metaclass
from .packets import RTCMV2Packet, RTCMV3Packet


__all__ = ("RTCMV2Parser", "RTCMV3Parser", "RTCMFormatAutodetectingParser")


RTCMV2ParserState = Enum("RTCMV2ParserState", "START LENGTH PAYLOAD")
RTCMV3ParserState = Enum("RTCMV3ParserState", "START LENGTH PAYLOAD PARITY")


class ChecksumError(RuntimeError):
    """Error thrown by the RTCM V3 parser when a packet was dropped due to
    a checksum mismatch.
    """

    def __init__(self, packet, parity):
        super(RuntimeError, self).__init__("Dropped packet of length {0} due "
                                           "to checksum mismatch".format(
                                               len(packet)))
        self.packet = packet
        self.parity = parity


class RTCMParser(with_metaclass(ABCMeta, object)):
    """Superclass for RTCM V2 and V3 parsers."""

    def __init__(self, callback=None, max_packet_length=None):
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
        self.callback = callback
        self.max_packet_length = max_packet_length
        self.reset()

    def feed(self, data):
        """Feeds some raw bytes into the RTCM parser.

        :param data: iterable yielding bytes
        :return: RTCM packets that have been parsed after the
            bytes have been forwarded to the parser
        :rtype: generator of RTCMV2Packet or RTCMV3Packet
        """
        for byte in data:
            try:
                packet = self._feed_byte(ord(byte))
                if packet is not None:
                    yield packet
            except ChecksumError as ex:
                for packet in self._recover_from_checksum_mismatch(ex.packet,
                                                                   ex.parity):
                    yield packet

    @abstractmethod
    def reset(self):
        """Resets the state of the parser. The default implementation is
        empty; should be overridden in subclasses.
        """
        raise NotImplementedError

    @abstractmethod
    def _feed_byte(self, byte):
        """Feeds a new byte to the parser."""
        raise NotImplementedError

    @abstractmethod
    def _recover_from_checksum_mismatch(self, packet, parity):
        """Tries to recover from a checksum-mismatched packet by looking for
        the next preamble byte in the stream and truncating the internal
        packet buffer appropriately.

        :param packet: the body of the last raw packet that resulted in a
            checksum mismatch
        :type packet: bytearray
        :param parity: the parity bytes that resulted in a checksum mismatch
        :type parity: bytearray
        """
        raise NotImplementedError


class RTCMV2Parser(RTCMParser):
    """Parser that parses RTCM V2 messages from a stream of bytes."""

    PREAMBLE = 0x66

    PARITY_FORMULA = [
        0xBB1F3480, 0x5D8F9A40, 0xAEC7CD00,
        0x5763E680, 0x6BB1F340, 0x8B7A89C0
    ]

    def __init__(self, *args, **kwds):
        """Constructor."""
        self._word = 0
        super(RTCMV2Parser, self).__init__(*args, **kwds)
        self._lsb_reversed = [self._reverse_six_lsb(i) for i in xrange(64)]

    def reset(self):
        """Resets the state of the parser."""
        self._state = RTCMV2ParserState.START
        self._length = None
        self._num_bits = 0
        self._packet = bytearray()

    def _decode_word(self):
        """Decodes a single data word found in ``self._word`` and appends
        the three decoded bytes to ``self._packet``.

        Returns ``True`` if the decoding was successful, ``False`` if there
        was a checksum error.
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
            for i in xrange(3):
                self._packet.append((word >> (22 - i * 8)) & 0xFF)
            return True
        else:
            return False

    def _feed_byte(self, byte):
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

    def _process_packet(self, packet):
        """Processes a packet that has passed the parity test.

        :param packet: the raw packet
        :type packet: bytearray
        :return: the parsed RTCM V2 packet
        :rtype: RTCMV2Packet
        """
        bitstream = ConstBitStream(packet[1:])
        return RTCMV2Packet.create(bitstream)

    @staticmethod
    def _reverse_six_lsb(byte):
        """Reverses the six least significant bits of the given byte.
        The byte is assumed to be between 0 (inclusive) and 64 (exclusive).

        :param byte: the byte to reverse
        :return: the reversed byte
        """
        result = 0
        for i in xrange(6):
            result = (result << 1) + (byte & 1)
            byte >>= 1
        return result


class RTCMV3Parser(RTCMParser):
    """Parser that parses RTCM V3 messages from a stream of bytes."""

    PREAMBLE = 0xD3

    def reset(self):
        """Resets the state of the parser."""
        self._state = RTCMV3ParserState.START
        self._packet_length = 0
        self._packet = bytearray()
        self._parity = bytearray()

    def _check_parity(self, packet, parity):
        """Checks whether the given packet has the given parity.

        :param packet: the raw packet
        :type packet: bytearray
        :param parity: the parity bytes of the packet
        :type parity: bytearray
        :return: whether the packet has the given parity
        :rtype: bool
        """
        return crc24q(packet) == \
            (parity[0] << 16) + (parity[1] << 8) + (parity[2])

    def _feed_byte(self, byte):
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
                self._packet_length = ((self._packet[1] & 0x03) << 8) + \
                    self._packet[2] + 3
                if self.max_packet_length is not None \
                        and self._packet_length > self.max_packet_length:
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
                if self._check_parity(self._packet, self._parity):
                    self._state = RTCMV3ParserState.START
                    return self._process_packet(self._packet)
                else:
                    raise ChecksumError(self._packet, self._parity)
        return None

    def _process_packet(self, packet):
        """Processes a packet that has passed the parity test.

        :param packet: the raw packet
        :type packet: bytearray
        :return: the parsed RTCM V3 packet
        :rtype: RTCMV3Packet
        """
        bitstream = ConstBitStream(packet[3:])
        return RTCMV3Packet.create(bitstream)

    def _recover_from_checksum_mismatch(self, packet, parity):
        """Tries to recover from a checksum-mismatched packet by looking for
        the next preamble byte in the stream and truncating the internal
        packet buffer appropriately.

        :param packet: the body of the last raw packet that resulted in a
            checksum mismatch
        :type packet: bytearray
        :param parity: the parity bytes that resulted in a checksum mismatch
        :type parity: bytearray
        """
        self.reset()

        buf = bytes(packet + parity)
        next_preamble_byte = buf.find(bytes(bytearray([self.PREAMBLE])), 1)
        if next_preamble_byte >= 1:
            return self.feed(buf[next_preamble_byte:])
        else:
            return []


class RTCMFormatAutodetectingParser(RTCMParser):
    """RTCM packet parser that attempts to automatically detect the format
    of the incoming bytes and choose from RTCM v2 or v3.

    This is done by feeding all the incoming bytes in parallel to both an
    RTCM v2 and an RTCM v3 parser. The first parser that successfully
    generates a packet will be used and the other will be discarded.
    """

    def __init__(self, *args, **kwds):
        """Constructor."""
        self._subparsers = [
            RTCMV2Parser(*args, **kwds),
            RTCMV3Parser(*args, **kwds)
        ]
        super(RTCMFormatAutodetectingParser, self).__init__(*args, **kwds)

    def reset(self):
        """Resets the state of the parser. The default implementation is
        empty; should be overridden in subclasses.
        """
        for parser in self._subparsers:
            parser.reset()

        self._chosen_subparser = None
        if len(self._subparsers) == 1:
            self._chosen_subparser = self._subparsers[0]

        self._pending_checksum_errors = []

    def feed(self, data):
        """Feeds some raw bytes into the RTCM parser.

        :param data: iterable yielding bytes
        :return: RTCM packets that have been parsed after the
            bytes have been forwarded to the parser
        :rtype: generator of RTCMV2Packet or RTCMV3Packet
        """
        for byte in data:
            self._pending_checksum_errors[:] = []
            try:
                packet = self._feed_byte(ord(byte))
                if packet is not None:
                    yield packet
            except ChecksumError as ex:
                # We get here if we have already chosen the subparser
                # and the chosen subparser subsequently throws checksum
                # errors.
                recover = self._chosen_subparser.\
                    _recover_from_checksum_mismatch
                for packet in recover(ex.packet, ex.parity):
                    yield packet

            if self._chosen_subparser is None:
                # We get here if we have not chosen a subparser yet and
                # we must handle pending checksum errors
                packets, parser = self._process_pending_checksum_errors()
                if packets:
                    for packet in packets:
                        yield packet
                    self._chosen_subparser = parser

    def _feed_byte(self, byte):
        """Feeds a new byte to the parser."""
        if self._chosen_subparser is not None:
            return self._chosen_subparser._feed_byte(byte)
        else:
            for parser in self._subparsers:
                try:
                    result = parser._feed_byte(byte)
                except ChecksumError as ex:
                    self._pending_checksum_errors.append((parser, ex))
                if result is not None:
                    self._chosen_subparser = parser
                    return result

    def _process_pending_checksum_errors(self):
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
