from typing import Callable, Iterable

from .packet import NMEAPacket

__all__ = ("create_nmea_parser",)


class NMEAParser:
    """NMEA-0183 sentence parser."""

    _buffer: list[bytes]
    _total: int

    def __init__(self):
        self._buffer = []
        self._total = 0

    def feed(self, data: bytes) -> list[NMEAPacket]:
        result: list[NMEAPacket] = []

        while data:
            pre, sep, data = data.partition(b"\n")

            self._buffer.append(pre)
            self._total += len(pre)

            if sep:
                line = b"".join(self._buffer)
                try:
                    result.append(NMEAPacket.parse(line.decode("ascii")))
                except UnicodeDecodeError:
                    pass
                except ValueError:
                    pass

                self.reset()

            else:
                if self._total > 82:
                    # Exceeded max message length
                    self.reset()

        return result

    def reset(self) -> None:
        self._buffer.clear()
        self._total = 0


def create_nmea_parser() -> Callable[[bytes], Iterable[NMEAPacket]]:
    """Creates an NMEA-0183 parser function that is suitable to be used in
    conjunction with the channels from the ``flockwave-conn`` module.

    Returns:
        the parser function
    """
    return NMEAParser().feed
