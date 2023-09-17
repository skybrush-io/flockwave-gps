"""Generic U-blox message type."""

from dataclasses import dataclass
from functools import partial
from typing import Callable

from .enums import UBXClass, UBXNAVSubclass
from .utils import calculate_ubx_checksum

__all__ = ("UBX", "UBXPacket")


@dataclass
class UBXPacket:
    """Generic U-blox message type."""

    class_id: int
    subclass_id: int
    payload: bytes

    def encode(self) -> bytes:
        """Encodes a U-blox message into its raw byte representation."""
        num_bytes = len(self.payload)
        assert num_bytes < 65536, "message too long"

        header_and_payload = (
            bytes(
                [
                    0xB5,
                    0x62,
                    int(self.class_id),
                    int(self.subclass_id),
                    num_bytes & 0xFF,
                    num_bytes >> 8,
                ]
            )
            + self.payload
        )
        chksum = calculate_ubx_checksum(header_and_payload)
        return header_and_payload + chksum


_ubx_message_class_and_subclass_map: dict[str, tuple[UBXClass, int]] = {
    "CFG_PRT": (UBXClass.CFG, 0),
    "CFG_MSG": (UBXClass.CFG, 1),
    "CFG_RATE": (UBXClass.CFG, 8),
    "CFG_NAV5": (UBXClass.CFG, 0x24),
    "CFG_TMODE3": (UBXClass.CFG, 0x71),
    "MON_HW": (UBXClass.MON, 9),
    "MON_VER": (UBXClass.MON, 4),
    "NAV_PVT": (UBXClass.NAV, UBXNAVSubclass.PVT),
    "NAV_SVIN": (UBXClass.NAV, UBXNAVSubclass.SVIN),
    "NAV_VELNED": (UBXClass.NAV, UBXNAVSubclass.VELNED),
    "NAV_TIMEUTC": (UBXClass.NAV, UBXNAVSubclass.TIMEUTC),
    "RXM_RAW": (UBXClass.RXM, 0x15),
    "RXM_RAWX": (UBXClass.RXM, 0x10),
    "RXM_SFRB": (UBXClass.RXM, 0x11),
    "RXM_SFRBX": (UBXClass.RXM, 0x13),
}


class _UBXPacketFactory:
    """Message factory for UBXPacket_ objects that allow a nicer syntax as
    follows:

        UBX.CFG_RATE(b"\xe8\x03\x01\x00\x01\x00")
    """

    def __init__(self):
        self._factories = {}

    def __getattr__(self, name: str) -> Callable[[bytes], UBXPacket]:
        func = self._factories.get(name)
        if func is None:
            try:
                class_id, subclass_id = _ubx_message_class_and_subclass_map[name]
            except KeyError:
                raise AttributeError(name) from None

            func = self._factories[name] = partial(
                self._create_message, class_id, subclass_id
            )

        return func

    def _create_message(
        self, class_id: UBXClass, subclass_id: int, data=b""
    ) -> UBXPacket:
        return UBXPacket(class_id, subclass_id, bytes(data))


UBX = _UBXPacketFactory()
