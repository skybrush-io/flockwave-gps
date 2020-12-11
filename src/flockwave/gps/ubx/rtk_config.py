"""Asynchronous task that configures a U-blox GPS receiver as an RTK base
station (if the GPS is capable enough).
"""

from typing import Awaitable, Callable

from .encoder import create_ubx_encoder
from .packet import UBX, UBXClass

__all__ = ("UBXRTKBaseConfigurator",)


class UBXRTKBaseConfigurator:
    """Class that knows how to configure a U-blox GPS receiver as an RTK
    base with given survey-in duration and accuracy.

    Attributes:
        duration: the minimum survey-in duration, in seconds
        accuracy: the desired survey-in accuracy, in meters
    """

    def __init__(self, duration: float = 60, accuracy: float = 0.02):
        """Constructor."""
        self.duration = float(duration)
        self.accuracy = float(accuracy)

    async def run(
        self,
        write: Callable[[bytes], Awaitable[None]],
        sleep: Callable[[], Awaitable[None]],
    ):
        """Asynchronous task that configures a U-blox GPS receiver as an RTK base
        station (if the GPS is capable enough).

        Parameters:
            write: a writer function that can be used to send commands to the GPS
                receiver
            sleep: a function that can be called to sleep a bit without blocking
                other tasks
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
        await send(UBX.CFG_RATE(b"\xE8\x03\x01\x00\x01\x00"))

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
        await send(UBX.MON_VER())

        # Request survey-in data so we can provide feedback to the user about the
        # survey-in procedure
        await set_message_rate(UBXClass.NAV, 0x3B, 1)

        # Request RTCM3 antenna position (1005) messages every 5 seconds
        await set_message_rate(UBXClass.RTCM3, 5, 5)

        # High-precision MSM messages are supported on uBlox M8P from revision
        # 130 and on uBlox F9P. We should do autodetection here.
        # TODO(ntamas): find out how to get the firmware revision.
        high_precision_supported = True

        # GPS MSM message
        await set_message_rate(UBXClass.RTCM3, 74, 0 if high_precision_supported else 1)
        await set_message_rate(UBXClass.RTCM3, 77, 1 if high_precision_supported else 0)

        # GLONASS MSM message
        await set_message_rate(UBXClass.RTCM3, 84, 0 if high_precision_supported else 1)
        await set_message_rate(UBXClass.RTCM3, 87, 1 if high_precision_supported else 0)
        await set_message_rate(UBXClass.RTCM3, 230, 5)

        # Galileo MSM message
        await set_message_rate(UBXClass.RTCM3, 94, 0 if high_precision_supported else 1)
        await set_message_rate(UBXClass.RTCM3, 97, 1 if high_precision_supported else 0)

        # BeiDou MSM message
        await set_message_rate(
            UBXClass.RTCM3, 124, 0 if high_precision_supported else 1
        )
        await set_message_rate(
            UBXClass.RTCM3, 127, 1 if high_precision_supported else 0
        )

        # No moving baseline messages
        await set_message_rate(UBXClass.RTCM3, 254, 0)

        # Turn off other unneeded UBX messages
        await set_message_rate(UBXClass.NAV, 0x07, 1)
        await set_message_rate(UBXClass.NAV, 0x12, 1)
        await set_message_rate(UBXClass.RXM, 0x13, 0)
        await set_message_rate(UBXClass.RXM, 0x15, 0)
        await set_message_rate(UBXClass.MON, 0x09, 0)

        # Set survey-in duration and accuracy requirements
        await sleep(0.2)

        payload = bytes(
            [
                # Version
                0x00,
                # Reserved
                0x00,
                # Flags; 0x01 = survey-in mode
                0x01,
                0x00,
                # ECEF coordinates (X, Y, Z, high-precision X, Y, Z)
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                # Reserved
                0x00,
                # Fixed-position 3D accuracy [0.1 mm], not applicable
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )
        payload += (
            # Survey-in minimum duration [sec]
            max(int(round(self.duration)), 1).to_bytes(4, "little", signed=False)
        )
        payload += (
            # Survey-in position accuracy limit [0.1 mm]
            max(int(round(self.accuracy * 10000)), 1).to_bytes(
                4, "little", signed=False
            )
        )
        # Reserved
        payload += bytes([0] * 8)
        await send(UBX.CFG_TMODE3(payload))

        # Read the CFG_TMODE3 settings back for confirmation
        await send(UBX.CFG_TMODE3())


def test_rtk_base_configuration() -> None:
    from trio import open_nursery, run, sleep
    from sys import argv

    async def main() -> None:
        from flockwave.connections.serial import SerialPortStream
        from flockwave.gps.parser import create_gps_parser

        port = await SerialPortStream.create(
            argv[1] if len(argv) > 1 else "/dev/cu.usbmodem14201"
        )
        parser = create_gps_parser()

        async with open_nursery() as nursery:
            config = UBXRTKBaseConfigurator(accuracy=10)
            nursery.start_soon(config.run, port.send_all, sleep)

            while True:
                data = await port.receive_some()
                # print("raw:", hexlify(data, sep=" ").decode("ascii"))
                for message in parser(data):
                    print(message)

    run(main)


if __name__ == "__main__":
    test_rtk_base_configuration()
