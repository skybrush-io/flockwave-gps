"""Functions to create encoders that can encode messages according to a variety
of commonly used GPS protocols.
"""

from typing import Any, Callable

from .nmea.encoder import create_nmea_encoder
from .rtcm.encoders import RTCMV2Encoder, RTCMV3Encoder
from .ubx.encoder import create_ubx_encoder

__all__ = ("create_gps_encoder",)


_encoder_factories: dict[str, Callable[[], Any]] = {
    "nmea": create_nmea_encoder,
    "rtcm2": RTCMV2Encoder,
    "rtcm3": RTCMV3Encoder,
    "ubx": create_ubx_encoder,
}


def create_gps_encoder(format: str) -> Callable[[Any], bytes]:
    """Creates an encoder that can encode GPS-specific messages using a
    single message format.

    Parameters:
        format: the format that the encoder should support. Valid values are:
            `rtcm2`, `rtcm3`, `ubx` and `nmea`.
    """
    try:
        factory = _encoder_factories[format.lower()]
    except KeyError:
        raise RuntimeError(f"Unknown GPS format: {format!r}") from None
    return factory()
