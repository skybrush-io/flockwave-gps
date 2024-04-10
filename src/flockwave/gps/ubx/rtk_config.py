"""Asynchronous task that configures a U-blox GPS receiver as an RTK base
station (if the GPS is capable enough).
"""

from struct import pack
from typing import Awaitable, Callable

from flockwave.gps.enums import GNSSType
from flockwave.gps.rtk import RTKBaseConfigurator, RTKMessageSet, RTKSurveySettings

from .encoder import create_ubx_encoder
from .enums import UBXClass, UBXNAVSubclass
from .packet import UBX

__all__ = ("UBXRTKBaseConfigurator",)


class UBXRTKBaseConfigurator(RTKBaseConfigurator):
    """Class that knows how to configure a U-blox GPS receiver as an RTK
    base station, optionally with given survey-in duration and accuracy.
    """

    async def run(
        self,
        write: Callable[[bytes], Awaitable[None]],
        sleep: Callable[[float], Awaitable[None]],
    ):
        """Asynchronous task that configures a U-blox GPS receiver as an RTK base
        station (if the GPS is capable enough).

        Parameters:
            write: a writer function that can be used to send commands to the GPS
                receiver
            sleep: a function that can be called to sleep a bit without blocking
                other tasks. Takes the number of seconds to sleep.
        """
        encoder = create_ubx_encoder()

        async def send(message, delay=0.2):
            await write(encoder(message))
            await sleep(delay)

        async def set_message_rate(class_id, subclass_id, rate):
            # Set message rates for ports 1 and 3; all other ports in the range
            # 0-5 are silenced
            payload = bytes([int(class_id), subclass_id, 0, rate, 0, rate, 0, 0])
            await send(UBX.CFG_MSG(payload), delay=0.01)
            # TODO(ntamas): we should wait for confirmation and re-send if needed;
            # this might be useful on radio links

        # Configure measurement rate to 1 Hz (0x3e8 msec), one solution for one
        # measurement, align measurements to GPS time
        await send(UBX.CFG_RATE(b"\xe8\x03\x01\x00\x01\x00"))

        # Configure navigation engine to stationary
        await send(
            UBX.CFG_NAV5(
                bytes(
                    [
                        # Parameter mask: apply all parameters
                        0xFF,
                        0xFF,
                        # Dynamic platform model: stationary
                        0x02,
                        # Position fixing mode: 3D
                        0x03,
                        # Fixed altitude for 2D mode, ignored
                        0x00,
                        0x00,
                        0x00,
                        0x00,
                        # Fixed altitude variance for 2D mode, ignored
                        0x10,
                        0x27,
                        0x00,
                        0x00,
                        # Minimum elevation of a satellite to be used: 5 degrees
                        0x05,
                        # Reserved
                        0x00,
                        # Position DOP mask: 25 (250 * 0.1)
                        0xFA,
                        0x00,
                        # Time DOP mask: 25 (250 * 01)
                        0xFA,
                        0x00,
                        # Position accuracy mask: 100m
                        0x64,
                        0x00,
                        # Time accuracy mask: 300m
                        0x2C,
                        0x01,
                        # Static hold threshold [cm/s]
                        0x00,
                        # DGNSS timeout [s]
                        0x00,
                        # Number of satellites required to be above the carrier-to-noise
                        # ratio threshold (see next byte) in order to attempt a fix
                        0x00,
                        # Carrier-to-noise ratio threshold for satellites
                        0x00,
                        # Reserved
                        0x10,
                        0x27,
                        # Static hold threshold
                        0x00,
                        0x00,
                        # UTC standard to be used; receiver selects based on GNSS configuration
                        0x00,
                        # Reserved
                        0x00,
                        0x00,
                        0x00,
                        0x00,
                        0x00,
                    ]
                )
            )
        )

        # Silence all NMEA messages except 0x0B, 0x0C and 0x0E
        for i in range(16):
            if i not in (0x0B, 0x0C, 0x0E):
                await set_message_rate(UBXClass.NMEA, i, 0)

        # Request receiver version
        await send(UBX.MON_VER(b""))

        # Request UTC time information so we can warn the user if the clock of
        # the computer is not in sync with GPS time
        await set_message_rate(UBXClass.NAV, UBXNAVSubclass.TIMEUTC, 5)

        # Request survey-in data so we can provide feedback to the user about the
        # survey-in procedure
        await set_message_rate(UBXClass.NAV, UBXNAVSubclass.SVIN, 1)

        # Request RTCM3 antenna position (1005) messages every 5 seconds
        await set_message_rate(UBXClass.RTCM3, 5, 5)

        # High-precision MSM messages are supported on uBlox M8P from revision
        # 130 and on uBlox F9P. We should do autodetection here.
        # TODO(ntamas): find out how to get the firmware revision.
        high_precision_supported = True
        use_high_precision = (
            high_precision_supported and self.settings.message_set is RTKMessageSet.MSM7
        )

        # GPS MSM message
        enabled = self.settings.uses_gnss(GNSSType.GPS)
        await set_message_rate(
            UBXClass.RTCM3, 74, 0 if use_high_precision or not enabled else 1
        )
        await set_message_rate(
            UBXClass.RTCM3, 77, 1 if use_high_precision and enabled else 0
        )

        # GLONASS MSM message
        enabled = self.settings.uses_gnss(GNSSType.GLONASS)
        await set_message_rate(
            UBXClass.RTCM3, 84, 0 if use_high_precision or not enabled else 1
        )
        await set_message_rate(
            UBXClass.RTCM3, 87, 1 if use_high_precision and enabled else 0
        )
        await set_message_rate(UBXClass.RTCM3, 230, 5 if enabled else 0)

        # Galileo MSM message
        enabled = self.settings.uses_gnss(GNSSType.GALILEO)
        await set_message_rate(
            UBXClass.RTCM3, 94, 0 if use_high_precision or not enabled else 1
        )
        await set_message_rate(
            UBXClass.RTCM3, 97, 1 if use_high_precision and enabled else 0
        )

        # BeiDou MSM message
        enabled = self.settings.uses_gnss(GNSSType.BEIDOU)
        await set_message_rate(
            UBXClass.RTCM3, 124, 0 if use_high_precision or not enabled else 1
        )
        await set_message_rate(
            UBXClass.RTCM3, 127, 1 if use_high_precision and enabled else 0
        )

        # No moving baseline messages
        await set_message_rate(UBXClass.RTCM3, 254, 0)

        # Turn off other unneeded UBX messages
        await set_message_rate(UBXClass.NAV, UBXNAVSubclass.PVT, 0)
        await set_message_rate(UBXClass.NAV, UBXNAVSubclass.VELNED, 0)
        await set_message_rate(UBXClass.RXM, 0x13, 0)
        await set_message_rate(UBXClass.RXM, 0x15, 0)
        await set_message_rate(UBXClass.MON, 0x09, 0)

        # Set survey-in duration and accuracy requirements
        await sleep(0.2)

        # CFG-TMODE3 parameter payload assembly
        coords: tuple[int, int, int]
        coords_hp: tuple[int, int, int]
        position = self.settings.position
        if position is not None:
            position_in_one_tenth_of_mm = position * 10000  # [m] --> [0.1 mm]
            coords_in_one_tenth_of_mm = (
                int(round(position_in_one_tenth_of_mm.x)),
                int(round(position_in_one_tenth_of_mm.y)),
                int(round(position_in_one_tenth_of_mm.z)),
            )
            coords, coords_hp = zip(
                *(divmod(coord, 100) for coord in coords_in_one_tenth_of_mm)
            )
            flags = 0x02  # 2 = fixed position
            fixed_accuracy = max(
                int(round(self.settings.accuracy * 10000)), 1
            )  # [m] --> [0.1 mm]
            min_accuracy = 0
        else:
            coords = 0, 0, 0
            coords_hp = 0, 0, 0
            flags = 0x01  # 1 = self-survey
            fixed_accuracy = 0
            min_accuracy = max(
                int(round(self.settings.accuracy * 10000)), 1
            )  # [m] --> [0.1 mm]
        payload = pack(
            "<BBHiiibbbBIIIQ",
            0,  # version
            0,  # reserved 1
            flags,
            coords[0],  # ECEF coordinate X
            coords[1],  # ECEF coordinate Y
            coords[2],  # ECEF coordinate Z
            coords_hp[0],  # ECEF coordinate X (high-precision part)
            coords_hp[1],  # ECEF coordinate Y (high-precision part)
            coords_hp[2],  # ECEF coordinate Z (high-precision part)
            0,  # reserved 2
            fixed_accuracy,  # fixed-pos 3D accuracy
            # Survey-in minimum duration [sec]
            max(int(round(self.settings.duration)), 1),
            # Survey-in position accuracy limit [0.1 mm]
            min_accuracy,
            # Reserved 3 (8 bytes)
            0,
        )
        await send(UBX.CFG_TMODE3(payload))

        # Read the CFG_TMODE3 settings back for confirmation
        await send(UBX.CFG_TMODE3(b""))


def test_rtk_base_configuration() -> None:
    from sys import argv

    try:
        from trio import open_nursery, run, sleep
    except ImportError:
        raise ImportError("You need to install 'trio' to run this test") from None

    async def main() -> None:
        from flockwave.connections.serial import SerialPortStream
        from flockwave.gps.parser import create_gps_parser

        port = await SerialPortStream.create(
            argv[1] if len(argv) > 1 else "/dev/cu.usbmodem14201"
        )
        parser = create_gps_parser()

        async with open_nursery() as nursery:
            settings = RTKSurveySettings(accuracy=10)
            settings.set_gnss_types(["gps", "glonass"])
            config = UBXRTKBaseConfigurator(settings)
            nursery.start_soon(config.run, port.send_all, sleep)

            while True:
                data = await port.receive_some()
                # print("raw:", hexlify(data, sep=" ").decode("ascii"))
                for message in parser(data):  # type: ignore
                    if hasattr(message, "packet_type"):
                        print(f"{message.packet_type}", end=" ")
                    print(message)

    run(main)


if __name__ == "__main__":
    test_rtk_base_configuration()
