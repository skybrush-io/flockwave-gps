"""Enum types related to the U-Blox protocol."""

from enum import IntEnum

__all__ = ("UBXClass", "UBXNAVSubclass")


class UBXClass(IntEnum):
    """U-Blox message class identifiers."""

    NAV = 0x01
    RXM = 0x02
    INF = 0x04
    ACK = 0x05
    CFG = 0x06
    UPD = 0x09
    MON = 0x0A
    AID = 0x0B
    TIM = 0x0D
    ESF = 0x10
    MGA = 0x13
    LOG = 0x21
    SEC = 0x27
    HNR = 0x28

    NMEA = 0xF0
    RTCM3 = 0xF5


class UBXNAVSubclass(IntEnum):
    """U-Blox NAV-... message subclass identifiers."""

    PVT = 0x07
    VELNED = 0x12
    SVIN = 0x3B
    TIMEUTC = 0x21
