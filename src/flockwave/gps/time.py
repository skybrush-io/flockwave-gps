"""GPS time related utility functions.

The functions in this module should provide the same results as the GPS-to-UTC
converter at https://www.gw-openscience.org/gps/
"""

from bisect import bisect
from datetime import datetime, timedelta, timezone
from typing import Optional

__all__ = (
    "current_gps_week",
    "datetime_to_gps_time",
    "datetime_to_gps_time_of_week",
    "gps_time_to_utc",
    "gps_time_of_week_to_utc",
    "unix_to_gps_time",
    "unix_to_gps_time_of_week",
)


#: Epoch of GPS time
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)

#: Offset between the UNIX epoch and the GPS time epoch
GPS_EPOCH_TO_UNIX_EPOCH = 315964800

#: Dates when leap seconds have occurred since the GPS epoch (1980-01-01)
#: Consult https://www.timeanddate.com/time/leap-seconds-future.html to keep this
#: up-to-date
_LEAP_DATES = (
    (1981, 6, 30),
    (1982, 6, 30),
    (1983, 6, 30),
    (1985, 6, 30),
    (1987, 12, 31),
    (1989, 12, 31),
    (1990, 12, 31),
    (1992, 6, 30),
    (1993, 6, 30),
    (1994, 6, 30),
    (1995, 12, 31),
    (1997, 6, 30),
    (1998, 12, 31),
    (2005, 12, 31),
    (2008, 12, 31),
    (2012, 6, 30),
    (2015, 6, 30),
    (2016, 12, 31),
)

#: Datetime objects representing the occurrences of leap seconds since the GPS epoch
LEAP_DATES = tuple(datetime(i[0], i[1], i[2], 23, 59, 59) for i in _LEAP_DATES)

#: Datetime objects representing the occurrences of leap seconds since the GPS epoch, as UNIX timestamps
LEAP_UNIX_TIMESTAMPS = tuple(
    dt.replace(tzinfo=timezone.utc).timestamp() for dt in LEAP_DATES
)

#: Number of seconds in a week in GPS time
SECONDS_IN_WEEK = 604800


def current_gps_week() -> int:
    """Returns the current GPS week number."""
    return datetime_to_gps_time_of_week(datetime.now(timezone.utc))[0]


def leap_seconds_since_1980(date: datetime) -> int:
    """Returns the number of leap seconds since 1980-01-01

    Parameters:
        date: the time we are interested in, in UTC

    Returns:
        leap seconds up to the given time
    """
    if date.tzinfo is not None:
        date = date.replace(tzinfo=None)
    return bisect(LEAP_DATES, date)


def leap_seconds_since_1980_unix(date: float) -> int:
    """Returns the number of leap seconds since 1980-01-01

    Parameters:
        date: the time we are interested in, in UTC, as a UNIX timestamp

    Returns:
        leap seconds up to the given time
    """
    return bisect(LEAP_UNIX_TIMESTAMPS, date)


def gps_time_to_utc(timestamp: float) -> datetime:
    """Converts a GPS timestamp expressed as the number of seconds since the GPS
    epoch into a timezone-aware UTC datetime object.

    Parameters:
        seconds: the number of sceonds since the beginning of the week
        week: the GPS week number; `None` means to use the current GPS week
    """
    date_before_leaps = GPS_EPOCH + timedelta(seconds=timestamp)
    result = date_before_leaps - timedelta(
        seconds=leap_seconds_since_1980(date_before_leaps)
    )
    return result.replace(tzinfo=timezone.utc)


def gps_time_of_week_to_utc(
    seconds: float = 0, *, week: Optional[int] = None
) -> datetime:
    """Converts a GPS timestamp expressed as the number of seconds since the
    beginning of the current (GPS) week and the GPS week number into a
    timezone-aware UTC datetime object.

    Parameters:
        seconds: the number of sceonds since the beginning of the week
        week: the GPS week number; `None` means to use the current GPS week
    """
    if week is None:
        week = current_gps_week()
    return gps_time_to_utc(week * SECONDS_IN_WEEK + seconds)


def datetime_to_gps_time(dt: datetime) -> float:
    """Converts a timezone-aware datetime object into a GPS timestamp, expressed
    as seconds since the GPS epoch.
    """
    if dt.tzinfo is None:
        raise ValueError("not applicable to naive datetime objects")

    date_naive = dt.astimezone(timezone.utc).replace(tzinfo=None)
    date_before_leaps = date_naive + timedelta(
        seconds=leap_seconds_since_1980(date_naive)
    )

    return (date_before_leaps - GPS_EPOCH).total_seconds()


def datetime_to_gps_time_of_week(dt: datetime) -> tuple[int, float]:
    """Converts a timezone-aware datetime object into GPS time, expressed
    as the GPS week number and the number of seconds since the beginning of that
    GPS week.
    """
    seconds = datetime_to_gps_time(dt)
    week, seconds = divmod(seconds, SECONDS_IN_WEEK)
    return int(week), seconds


def unix_to_gps_time(seconds: float) -> float:
    """Converts a UNIX timestamp into a GPS timestamp."""
    return seconds - GPS_EPOCH_TO_UNIX_EPOCH + leap_seconds_since_1980_unix(seconds)


def unix_to_gps_time_of_week(seconds: float) -> tuple[int, float]:
    """Converts a UNIX timestamp into GPS time, expressed as the GPS week number
    and the number of seconds since the beginning of that GPS week. Fractional
    seconds are ignored.
    """
    seconds = unix_to_gps_time(seconds)
    week, seconds = divmod(seconds, SECONDS_IN_WEEK)
    return int(week), seconds
