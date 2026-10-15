"""Helper functions for RTCM message decoding"""

from operator import attrgetter
from typing import Iterable, TypeVar

from bitstring import Reader

__all__ = ("count_bits", "get_best_satellites", "read_bool", "read_int", "read_uint")

# Construct a helper table for the _count_bits function
_count_bits_table = [0] * 256
for i in range(256):
    _count_bits_table[i] = (i & 1) + _count_bits_table[i >> 1]


T = TypeVar("T")


def count_bits(value: int) -> int:
    """Counts the number of set bits in a non-negative integer that is assumed
    to be smaller than 2**24.

    Parameters:
        value: the input value

    Returns:
        int: the number of set bits in the given value
    """
    assert value >= 0 and value < 0x1000000
    return (
        _count_bits_table[value & 0xFF]
        + _count_bits_table[(value >> 8) & 0xFF]
        + _count_bits_table[(value >> 16) & 0xFF]
    )


def get_best_satellites(satellites: Iterable[T], count: int | None = None) -> list[T]:
    """Given a list of satellite objects, each of which having a `cnr`
    attribute containing the carrier-to-noise ratio, returns the ones that
    have the best carrier-to-noise ratio, in decreasing order.

    Parameters:
        satellites: list of satellites
        count: maximum number of satellites to return

    Returns:
        a sorted list of satellites with the best carrier-to-noise ratios
    """
    top = sorted(satellites, key=attrgetter("cnr"), reverse=True)
    if count is not None:
        top[count:] = []
    return top


def read_bool(reader: Reader) -> bool:
    """Reads a single bit from the given reader as a boolean."""
    return reader.read_bits(1).bool


def read_int(reader: Reader, num_bits: int) -> int:
    """Reads a big-endian signed integer of the given width from the given
    reader.
    """
    return reader.read_bits(num_bits).i


def read_uint(reader: Reader, num_bits: int) -> int:
    """Reads a big-endian unsigned integer of the given width from the given
    reader.
    """
    return reader.read_bits(num_bits).u
