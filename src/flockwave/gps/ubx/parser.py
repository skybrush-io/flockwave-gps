from enum import Enum
from typing import Callable, Iterable, Optional

from .packet import UBXPacket
from .utils import calculate_ubx_checksum

__all__ = ("UBXParser",)


class UBXParserState(Enum):
    SYNC1 = 1
    SYNC2 = 2
    CLASS1 = 3
    CLASS2 = 4
    LENGTH1 = 5
    LENGTH2 = 6
    PAYLOAD = 7
    CHKSUM1 = 8
    CHKSUM2 = 9


class UBXParser:
    """Stateful incremental UBX protocol parser."""

    _buffer: list[int]
    _chksum: list[Optional[int]]
    _state: UBXParserState
    _bytes_needed: int

    def __init__(self):
        self._buffer = []
        self._chksum = [None, None]
        self._state = UBXParserState.SYNC1
        self._bytes_needed = 0

    def reset(self) -> None:
        self._bytes_needed = 0
        self._buffer.clear()
        self._state = UBXParserState.SYNC1

    def feed(self, data: bytes) -> Iterable[UBXPacket]:
        store = self._buffer.append
        result = []

        for ch in data:
            if self._state == UBXParserState.SYNC1:
                if ch == 0xB5:
                    self._state = UBXParserState.SYNC2

            elif self._state == UBXParserState.SYNC2:
                if ch == 0x62:
                    self._buffer.clear()
                    self._bytes_needed = 0
                    self._state = UBXParserState.CLASS1
                else:
                    self._state = UBXParserState.SYNC1

            elif self._state == UBXParserState.CLASS1:
                store(ch)
                self._state = UBXParserState.CLASS2

            elif self._state == UBXParserState.CLASS2:
                store(ch)
                self._state = UBXParserState.LENGTH1

            elif self._state == UBXParserState.LENGTH1:
                store(ch)
                self._bytes_needed = ch
                self._state = UBXParserState.LENGTH2

            elif self._state == UBXParserState.LENGTH2:
                store(ch)
                self._bytes_needed += ch << 8
                if self._bytes_needed >= 8192:
                    # Oversized packet
                    # TODO(ntamas): we should scan the buffer to see if there is
                    # another packet marker in the buffer
                    self.reset()
                elif self._bytes_needed > 0:
                    self._state = UBXParserState.PAYLOAD
                else:
                    self._state = UBXParserState.CHKSUM1

            elif self._state == UBXParserState.PAYLOAD:
                store(ch)
                self._bytes_needed -= 1
                if self._bytes_needed <= 0:
                    self._state = UBXParserState.CHKSUM1

            elif self._state == UBXParserState.CHKSUM1:
                self._chksum[0] = ch
                self._state = UBXParserState.CHKSUM2

            elif self._state == UBXParserState.CHKSUM2:
                self._chksum[1] = ch
                expected_chksum = list(calculate_ubx_checksum(self._buffer, offset=0))
                if expected_chksum == self._chksum:
                    result.append(
                        UBXPacket(
                            class_id=self._buffer[0],
                            subclass_id=self._buffer[1],
                            payload=bytes(self._buffer[4:]),
                        )
                    )

                self.reset()

        return result


def create_ubx_parser() -> Callable[[bytes], Iterable[UBXPacket]]:
    """Creates an UBX parser function that is suitable to be used in
    conjunction with the channels from the ``flockwave-conn`` module.

    Returns:
        the parser function
    """
    return UBXParser().feed
