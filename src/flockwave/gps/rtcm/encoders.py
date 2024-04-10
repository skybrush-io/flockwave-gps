"""Writer objects that write RTCM V2 or V3 messages."""

from bitstring import BitArray, pack
from itertools import cycle
from typing import Callable, Optional, Union

from flockwave.gps.crc import crc24q

from .packets import RTCMPacket, RTCMV2Packet, RTCMV3Packet
from .utils import count_bits


__all__ = ("RTCMV2Encoder", "RTCMV3Encoder")


class RTCMV2Encoder:
    """Encoder that generates byte-level representations of an
    RTCM V2 message.

    See this URL for more details:
    http://sigidwiki.com/wiki/File:Rtcm-sc104-transmission-characteristics-of-marine-differential-gps-stations.pdf
    """

    PREAMBLE = 0x66
    _PARITY_FORMULA = [
        (0, 0xEC7CD2),  # noqa: bits 0, 1, 2, 4, 5, 9, 10, 11, 12, 13, 16, 17, 19, 22
        (1, 0x763E69),  # noqa: bits 1, 2, 3, 5, 6, 10, 11, 12, 13, 14, 17, 18, 20, 23
        (0, 0xBB1F34),  # noqa: bits 0, 2, 3, 4, 6, 7, 11, 12, 13, 14, 15, 18, 19, 21
        (1, 0x5D8F9A),  # noqa: bits 1, 3, 4, 5, 7, 8, 12, 13, 14, 15, 16, 19, 20, 22
        (1, 0xAEC7CD),  # noqa: bits 0, 2, 4, 5, 6, 8, 9, 13, 14, 15, 16, 17, 20, 21, 23
        (0, 0x2DEA27),  # noqa: bits 2, 4, 5, 7, 8, 9, 10, 12, 14, 18, 21, 22, 23
    ]

    def __init__(self):
        """Constructor."""
        self.seq_generator = cycle(list(range(8)))
        self.previous_parities = False, False

    def encode(
        self,
        message: RTCMV2Packet,
        time_of_week: Optional[int] = None,
        add_parities: bool = True,
    ) -> bytes:
        """Encodes the given message into a bytes object.

        Parameters:
            message: the message to write
            time_of_week: the current GPS time of week. ``None`` means that it
                is not known, in which case we can encode the message only if
                its *own* ``modified_z_count`` attribute is not ``None``.
            add_parities: whether to add the parity bits and perform
                the wire encoding of the message or not. When this parameter
                is ``False``, the encoding stops at the phase when only the
                data bits are assembled and the parity bits are not inserted
                into the bit stream yet.

        Returns:
            the encoded message
        """
        assert isinstance(message, RTCMV2Packet)

        bits = BitArray()

        try:
            message.write_body(bits)
        except (NotImplementedError, AttributeError):
            if hasattr(message, "bytes"):
                bits = BitArray(bytes=message.bytes)
            else:
                raise NotImplementedError(
                    "Unsupported RTCM v2 packet type: {0!r}".format(message.packet_type)
                ) from None

        self._prepend_message_header(bits, message, time_of_week)
        if add_parities:
            bits = self._encode_message(bits)

        return bits.tobytes()

    def _calculate_modified_z_count(self, time_of_week: int):
        """Returns the current "modified Z count" value that is to be inserted
        into the header of every RTCM V2 message.

        The modified Z count value counts from 0 to 6000 and increases every
        0.6 seconds.

        Parameters:
            time_of_week (int): the GPS time of week value from which the
                modified Z count is to be calculated.
        """
        time_within_hour = time_of_week - 3600 * (int(time_of_week) // 3600)
        return int(round(time_within_hour / 0.6))

    def _encode_message(self, bits):
        """Given a bit array containing the data bits, returns another bit
        array that contains the bits to be transmitted using the parity
        algorithm in section 3.3 of the PDF referenced in the class
        docstring.

        Parameters:
            bits (BitArray): the bits of the RTCM V2 message to be encoded

        Returns:
            BitArray: the encoded bits
        """
        if len(bits) % 24 != 0:
            raise ValueError("bit array length must be divisible by 24 at this point")

        # Okay, this is crazy. First we append six parity bits to every data
        # word. Each data word consists of 24 bits. The parity algorithm is
        # stateful; it depends on the parity bits of the previous data word.
        # Furthermore, the actual data bits are inverted if the last parity
        # bit of the previous data word was 1 (but the parity is calculated
        # *before* the inversion). This leaves us with data words consisting
        # of 30 bits with parity. Next, the data words are divided into
        # chunks of 6 bits, each chunk is reversed, then prepended with 01
        # (in binary), and encoded into bytes.
        result = BitArray()
        for start in range(0, len(bits), 24):
            word = self._encode_word(bits[start : (start + 24)])
            for chunk_start in range(0, len(word), 6):
                result.append((False, True))
                result.append(reversed(word[chunk_start : (chunk_start + 6)]))
        return result

    def _encode_word(self, bits):
        """Encodes a single data word of an RTCM V2 message.

        Parameters:
            bits (BitArray): the bits of the data word to be encoded. It
            *might* be mutated by this function.

        Returns:
            BitArray: the encoded bits
        """
        assert len(bits) == 24
        parities = []
        word = bits.uintbe
        for previous_parity_index, mask in self._PARITY_FORMULA:
            num_set_bits = (
                count_bits(word & mask) + self.previous_parities[previous_parity_index]
            )
            parities.append(num_set_bits & 1)
        if self.previous_parities[1]:
            bits.invert()
        bits.append(parities)
        self.previous_parities = list(bits[-2:])
        return bits

    def _prepend_message_header(self, bits, message, time_of_week):
        """Prepends an RTCM V2 message header to the given bit array.

        Parameters:
            bits (BitArray): the bit array that will hold the message.
            message (RTCMV2Message): the message being encoded
            time_of_week (int or None): the current GPS time of week.
                ``None`` means that it is not known, in which case we can
                encode the message only if its *own* ``modified_z_count``
                attribute is not ``None``.
        """
        if len(bits) % 8 != 0:
            raise ValueError("bit array length must be divisible by 8 at " "this point")

        if time_of_week is None:
            mod_z_count = message.modified_z_count
        else:
            mod_z_count = self._calculate_modified_z_count(time_of_week)

        if mod_z_count is None:
            raise ValueError(
                "cannot encode this message without knowing " "the GPS time of week"
            )

        num_data_words = len(bits) // 24
        sequence_no = next(self.seq_generator)

        need_padding = num_data_words * 24 < len(bits)
        if need_padding:
            num_data_words += 1

        health = 0  # assume UDRE scale factor = 1.0

        header = pack(
            "uint:8, uint:6, uint:10, uint:13, uint:3, uint:5, " "uint:3",
            self.PREAMBLE,
            message.packet_type,
            message.station_id,
            mod_z_count,
            sequence_no,
            num_data_words,
            health,
        )
        bits[0:0] = header
        while len(bits) % 24 != 0:
            bits.append("0b10101010")


class RTCMV3Encoder:
    """Encoder that generates byte-level representations of an
    RTCM V3 message.
    """

    PREAMBLE = 0xD3

    def encode(self, message: RTCMV3Packet, add_parities: bool = True) -> bytes:
        """Encodes the given message into a bytes object.

        Parameters:
            message (RTCMV3Packet): the message to write
            add_parities (bool): whether to add the parity bits and perform
                the wire encoding of the message or not. When this parameter is
                ``False``, the encoding stops at the phase when only the data
                bits are assembled and the header and then parity bits are not
                inserted into the bit stream yet.

        Returns:
            bytes: the encoded message
        """
        assert isinstance(message, RTCMV3Packet)

        bits = BitArray()

        try:
            message.write_body(bits)  # type: ignore
        except (NotImplementedError, AttributeError):
            if hasattr(message, "bytes"):
                bits = BitArray(bytes=message.bytes)
            else:
                raise NotImplementedError(
                    f"Unsupported RTCM v3 packet type: {message.packet_type!r}"
                ) from None

        data = bits.tobytes()

        if add_parities:
            length = len(data)
            header = bytes([self.PREAMBLE, length >> 8, length & 0xFF])
            parity = crc24q(header + data)
            data = b"".join(
                [
                    header,
                    data,
                    bytes([parity >> 16, (parity >> 8) & 0xFF, parity & 0xFF]),
                ]
            )

        return data


def create_rtcm_encoder(format: Union[int, str]) -> Callable[[RTCMPacket], bytes]:
    """Creates an RTCM encoder function that is suitable to be used in
    conjunction with the channels from the ``flockwave-conn`` module.

    Parameters:
        format: the RTCM format that the parser will use; must be one of
            ``rtcm2`` or ``rtcm3``. 2 and 3 as integers can be used as aliases
            for ``rtcm2`` and ``rtcm3``.

    Returns:
        the parser function
    """
    if format == "rtcm2" or format == 2:
        return RTCMV2Encoder().encode  # type: ignore
    elif format == "rtcm3" or format == 3:
        return RTCMV3Encoder().encode  # type: ignore
    else:
        raise ValueError(f"unknown RTCM format: {format!r}")
