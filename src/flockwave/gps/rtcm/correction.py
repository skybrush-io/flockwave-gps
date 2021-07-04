"""Satellite position correction data related classes."""

from typing import NamedTuple, Optional


class CorrectionData(
    NamedTuple(
        "CorrectionData",
        [("svid", int), ("prc", float), ("prrc", float), ("iode", float)],
    )
):
    """Satellite position correction data in an RTCM v2 packet."""

    _scale_factor: Optional[float]
    _scaled_prc: Optional[float]
    _scaled_prrc: Optional[float]

    def __init__(self, *args, **kwds):
        """Constructor."""
        super().__init__(*args, **kwds)
        self._scale_factor = None
        self._scaled_prc = None
        self._scaled_prrc = None

    @property
    def scale_factor(self) -> float:
        """Returns the scale factor to use when storing the real ``prc``
        and ``prrc`` values in the bit-level representation of the
        correction data in an RTCM v2 packet.
        """
        if self._scale_factor is None:
            self._calculate_scale_factor()
            assert self._scale_factor is not None
        return self._scale_factor

    @property
    def scaled_prc(self) -> float:
        """Returns the scaled ``prc`` value to use when calculating the
        bit-level representation of the RTCM v2 packet.
        """
        if self._scaled_prc is None:
            self._calculate_scale_factor()
            assert self._scaled_prc is not None
        return self._scaled_prc

    @property
    def scaled_prrc(self) -> float:
        """Returns the scaled ``prrc`` value to use when calculating the
        bit-level representation of the RTCM v2 packet.
        """
        if self._scaled_prrc is None:
            self._calculate_scale_factor()
            assert self._scaled_prrc is not None
        return self._scaled_prrc

    def _calculate_scale_factor(self) -> None:
        scaled_prc = self.prc
        scaled_prrc = self.prrc
        factor = 0
        while scaled_prc > 32767 or scaled_prc < -32768:
            factor += 1
            scaled_prc = (scaled_prc + 8) // 16
            scaled_prrc = (scaled_prrc + 8) // 16
        scaled_prrc = min(127, max(scaled_prrc, -128))
        self._scale_factor, self._scaled_prc, self._scaled_prrc = (
            factor,
            scaled_prc,
            scaled_prrc,
        )
