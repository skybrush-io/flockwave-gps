"""Helpers for constructing RTCM test vectors without relying on `bitstring`.

The RTCM parsers and encoders are built on top of `bitstring`, so the test
vectors are assembled with a minimal, independent bit writer to ensure that
a change in the behaviour of `bitstring` cannot silently change both the
code under test and the expected values.
"""

from flockwave.gps.crc import crc24q

__all__ = ("BitWriter", "frame_rtcm3")


class BitWriter:
    """Minimal MSB-first bit writer."""

    def __init__(self):
        self._value = 0
        self._length = 0

    def __len__(self) -> int:
        return self._length

    def uint(self, num_bits: int, value: int) -> "BitWriter":
        assert 0 <= value < (1 << num_bits), f"{value} does not fit in {num_bits} bits"
        self._value = (self._value << num_bits) | value
        self._length += num_bits
        return self

    def int(self, num_bits: int, value: int) -> "BitWriter":
        limit = 1 << (num_bits - 1)
        assert -limit <= value < limit, f"{value} does not fit in {num_bits} bits"
        return self.uint(num_bits, value & ((1 << num_bits) - 1))

    def bool(self, value: bool) -> "BitWriter":
        return self.uint(1, 1 if value else 0)

    def bits(self, value: str) -> "BitWriter":
        """Appends bits given as a string of zeros and ones."""
        return self.uint(len(value), int(value, 2)) if value else self

    def string(self, value: str) -> "BitWriter":
        """Appends a length-prefixed string, as used in RTCM v3 descriptors."""
        self.uint(8, len(value))
        for ch in value.encode("ascii"):
            self.uint(8, ch)
        return self

    def to_bytes(self) -> bytes:
        """Returns the bits written so far, zero-padded to a byte boundary."""
        padding = -self._length % 8
        num_bytes = (self._length + padding) // 8
        return (self._value << padding).to_bytes(num_bytes, "big")


def frame_rtcm3(payload: bytes) -> bytes:
    """Wraps the given payload in an RTCM v3 frame (preamble, length, CRC)."""
    header = bytes([0xD3, len(payload) >> 8, len(payload) & 0xFF])
    crc = crc24q(header + payload)
    return header + payload + crc.to_bytes(3, "big")
