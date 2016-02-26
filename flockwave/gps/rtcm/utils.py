"""Helper functions for RTCM message decoding"""

from six.moves.builtins import range


__all__ = ("count_bits", )

# Construct a helper table for the _count_bits function
_count_bits_table = [0] * 256
for i in range(256):
    _count_bits_table[i] = (i & 1) + _count_bits_table[i >> 1]


def count_bits(value):
    """Counts the number of set bits in a non-negative integer that is assumed
    to be smaller than 2**24.

    Parameters:
        value (int): the input value

    Returns:
        int: the number of set bits in the given value
    """
    assert value >= 0 and value < 0x1000000
    return _count_bits_table[value & 0xFF] + \
        _count_bits_table[(value >> 8) & 0xFF] + \
        _count_bits_table[(value >> 16) & 0xFF]
