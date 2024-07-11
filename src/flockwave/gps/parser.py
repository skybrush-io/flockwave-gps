"""Combined parser that can parse many GPS message formats coming from a GPS
receiver.
"""

from typing import Any, Callable, Iterable, Optional, Protocol, TypeVar

from .nmea.parser import NMEAParser
from .rtcm.parsers import RTCMV2Parser, RTCMV3Parser
from .ubx.parser import UBXParser

__all__ = ("create_gps_parser",)


T = TypeVar("T", covariant=True)


class Parser(Protocol[T]):
    def feed(self, data: bytes) -> Iterable[T]: ...
    def reset(self) -> None: ...


_parser_factories: dict[str, Callable[[], Parser]] = {
    "nmea": NMEAParser,
    "rtcm2": RTCMV2Parser,
    "rtcm3": RTCMV3Parser,
    "ubx": UBXParser,
}


def _create_gps_subparser(format: str) -> Parser[Any]:
    try:
        factory = _parser_factories[format.lower()]
    except KeyError:
        raise RuntimeError(f"Unknown GPS format: {format!r}") from None
    return factory()


_NOTHING = ()


def _null_parser(data: bytes) -> Iterable[Any]:
    return _NOTHING


def create_gps_parser(
    formats: Optional[Iterable[str]] = None,
) -> Callable[[bytes], Iterable[Any]]:
    """Creates a combined parser that can parse multiple GPS message formats
    simultaneously. This is commonly used with serial connections to GPS
    receivers where the receiver may send messages in multiple formats such
    as UBX, NMEA-0183 and RTCM.

    Parameters:
        formats: iterable containing the formats that the parser should support.
            Valid values in this list are: `rtcm2`, `rtcm3`, `ubx` and `nmea`.
            Defaults to all supported formats if set to `None`
    """
    if formats is None:
        formats = _parser_factories.keys()

    parsers = [_create_gps_subparser(format) for format in formats]

    if not parsers:
        return _null_parser

    if len(parsers) == 1:
        return parsers[0].feed

    def combined_parser(data: bytes) -> Any:
        # We have to feed the bytes one by one to the subparsers so we can reset
        # all parsers as soon as one of them indicates that it has parsed a
        # message
        chars = [b"%c" % ch for ch in data]
        result = []
        successful_parsers = []
        for ch in chars:
            for parser in parsers:
                messages = parser.feed(ch)
                result.extend(messages)
                if messages:
                    successful_parsers.append(parser)

            if successful_parsers:
                for parser in parsers:
                    if parser not in successful_parsers:
                        parser.reset()
                successful_parsers.clear()

        return result

    return combined_parser
