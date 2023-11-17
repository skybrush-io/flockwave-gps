import pynmea2

from functools import lru_cache
from typing import Any, Sequence

from pynmea2 import NMEASentence as NMEAPacket

__all__ = ("NMEAPacket", "create_talker_sentence", "create_nmea_packet")


@lru_cache()
def _sentence_factory_from_type(type: str):
    if not type or "_" in type:
        raise RuntimeError(f"Invalid NMEA sentence: {type!r}")

    func = getattr(pynmea2, type.upper(), None)
    if func is None:
        raise RuntimeError(f"Invalid NMEA sentence: {type!r}")

    return func


def create_talker_sentence(talker: str, type: str, args: Sequence[Any]) -> NMEAPacket:
    """Creates an NMEA talker sentence with the given talker ID, packet type
    and arguments.
    """
    factory = _sentence_factory_from_type(type)
    return factory(talker, type, args)


create_nmea_packet = create_talker_sentence
