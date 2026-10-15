# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking changes

- Migrated to `bitstring` 5.x. Since `bitstring` 5 requires Python 3.11 or later,
  Python 3.10 is not supported any more.

- `create_rtcm2_packet()`, `create_rtcm3_packet()` and the `create()` class methods
  of RTCM packet classes now expect a `bitstring.Reader` instead of a
  `bitstring.ConstBitStream`, which was removed in `bitstring` 5.

### Changed

- Errors raised by `bitstring` while parsing truncated RTCM packets are now
  `bitstring.ReadError` instances that derive from `ValueError` instead of
  `IndexError`.

- `RTCMParams.GLONASS_INVALID_RANGEINCR_MARKER` was replaced by
  `RTCMParams.INVALID_RANGEINCR_MARKER` as it is now used for GPS packets as well.
  `RTCMParams.INVALID_PSEUDORANGE_MARKER` was removed.

### Fixed

- `CorrectionData` objects can now be constructed. Previously the constructor always
  raised a `TypeError`, which also made the parser fail on RTCMv2 type 1 messages
  that contained correction data.

- RTCMv2 and RTCMv3 encoders now raise `NotImplementedError` for unsupported packets
  that have no raw bytes attached, as documented, instead of a `TypeError`.

- `repr()` of satellite info objects in RTCMv3 GLONASS RTK packets does not raise
  an `AttributeError` any more.

- RTCMv3 message 1011 (GLONASS L1 and L2 RTK observables) is now parsed according
  to the RTCM standard. Satellite info objects in these messages do not contain
  ambiguity and carrier-to-noise ratio fields any more as these are not
  transmitted in 1011 messages.

- Lock time indicators in RTCMv3 GPS and GLONASS RTK packets (1001-1004 and
  1009-1012) are now parsed as unsigned integers.

- Invalid phaserange-pseudorange values in RTCMv3 GPS and GLONASS RTK packets are
  now detected correctly; such values are reported as zero with
  `pseudorange_valid` set to `False`.

- The L2-L1 pseudorange difference in RTCMv3 GLONASS RTK packets is now parsed as a
  signed integer, and invalid values of this field are now detected correctly in
  both GPS and GLONASS RTK packets.

- The L1 pseudorange in RTCMv3 GPS and GLONASS RTK packets is not treated as
  invalid any more when it happens to be equal to 0x80000; the RTCM standard does
  not define an invalid value for this field.

## [5.0.2] - 2026-10-14

### Fixed

- Fixed version range of the `bitstring` dependency. `bitstring` 5.0.0 introduced
  API-breaking changes that we are not prepared for yet.

## [5.0.1] - 2026-05-03

### Fixed

- Capitalization of the `Ntrip-Version` header is now kept because it was reported
  that some clients are sensitive to capitalization.

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
