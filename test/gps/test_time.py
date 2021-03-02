from datetime import datetime, timezone
from flockwave.gps.time import (
    current_gps_week,
    datetime_to_gps_time_of_week,
    gps_time_of_week_to_utc,
    leap_seconds_since_1980,
    unix_to_gps_time_of_week,
)


def d(value: str) -> datetime:
    utc = timezone.utc
    if " " in value:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc)
    else:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=utc)


def f(date: datetime) -> str:
    return date.strftime("%Y-%m-%d %H:%M:%S")


def test_current_gps_week():
    # smoke testing only
    assert current_gps_week() >= 2129
    assert isinstance(current_gps_week(), int)


def test_leap_seconds_since_1980():
    assert leap_seconds_since_1980(d("1979-01-01")) == 0
    assert leap_seconds_since_1980(d("1979-12-31")) == 0
    assert leap_seconds_since_1980(d("1996-12-31")) == 11
    assert leap_seconds_since_1980(d("1997-06-30")) == 11
    assert leap_seconds_since_1980(d("1997-07-01")) == 12
    assert leap_seconds_since_1980(d("2017-04-03")) == 18
    assert leap_seconds_since_1980(d("2020-12-26")) == 18


def test_datetime_to_gps_time_of_week():
    # authoritative source: https://www.gw-openscience.org/gps/
    assert datetime_to_gps_time_of_week(d("2020-10-26 14:28:01")) == (2129, 138499)
    assert datetime_to_gps_time_of_week(d("2021-03-02 02:53:14")) == (2147, 183212)


def test_gps_time_of_week_to_utc():
    # authoritative source: https://www.gw-openscience.org/gps/
    dt = gps_time_of_week_to_utc(138499, week=2129)
    assert f(dt) == "2020-10-26 14:28:01"
    assert dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0


def test_unix_to_gps_time_of_week():
    assert unix_to_gps_time_of_week(1603722481) == (2129, 138499)
    assert unix_to_gps_time_of_week(1614653594) == (2147, 183212)

