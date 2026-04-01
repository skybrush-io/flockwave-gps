# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-04-01

### Breaking changes

- Fixed a long-standing typing issue with `RTCMv2Packet` and `RTCMv3Packet` where the
  `create()` class method was overridden in subclasses with a different signature,
  violating the Liskov Substitution Principle. The `create()` methods were now removed
  from the base classes; use the `create_rtcm2_packet()` and `create_rtcm3_packet()`
  functions instead.

## [4.0.0] - 2025-04-20

### Breaking changes

- Dropped support for Python 3.9.

## [3.0.0] - 2023-09-17

### Breaking changes

- `ECEFCoordinate` now transmits and receives the coordinates in millimeters
  when converting into JSON. Internal storage is still in meters.

## [2.3.3] - 2023-04-25

This is the release that serves as a basis for changelog entries above. Refer
to the commit logs for changes affecting this version and earlier versions.
