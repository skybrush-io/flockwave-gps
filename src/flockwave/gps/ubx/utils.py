from typing import Sequence, Union


def calculate_ubx_checksum(data: Union[bytes, Sequence[int]], offset: int = 2) -> bytes:
    """Calculates the checksum of a UBX packet."""
    a, b = 0, 0
    size = len(data)
    for i in range(offset, size):
        a += data[i]
        b += a
    return bytes([a & 0xFF, b & 0xFF])
