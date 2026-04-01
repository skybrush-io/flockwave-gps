"""Asynchronous task that configures a Javad GNSS receiver as an RTK base
station.
"""

from typing import Any, Awaitable, Callable

from flockwave.gps.enums import GNSSType
from flockwave.gps.rtk import RTKBaseConfigurator, RTKMessageSet, RTKSurveySettings

__all__ = ("JavadRTKBaseConfigurator",)


class JavadRTKBaseConfigurator(RTKBaseConfigurator):
    """Class that knows how to configure a Javad GNSS receiver as an RTK
    base with a given settings object.

    Javad receivers do not support setting a desired accuracy so this parameter
    of the RTK survey settings will be ignored.
    """

    settings: RTKSurveySettings

    def __init__(self, settings: RTKSurveySettings):
        """Constructor."""
        self.settings = settings

    async def run(
        self,
        write: Callable[[bytes], Awaitable[None]],
        sleep: Callable[[float], Awaitable[None]],
    ):
        """Asynchronous task that configures a Javad GNSS receiver as an RTK base
        station.

        Parameters:
            write: a writer function that can be used to send commands to the
                receiver
            sleep: a function that can be called to sleep a bit without blocking
                other tasks. Takes the number of seconds to sleep.
        """

        async def send(message: str, delay: float = 0.1) -> None:
            await write(message.encode("ascii") + b"\r\n")
            await sleep(delay)

        async def set(key: str, value: Any = True) -> None:
            if value is True:
                value = "on"
            elif value is False:
                value = "off"
            else:
                value = str(value)
            await send(f"set,{key},{value}")

        # Disable all messages on the current port
        await send("dm,/cur/term")

        if self.settings.position is None:
            # Start averaging when turned on, for the given duration
            await set("/par/ref/avg/span", round(self.settings.duration))
            await set("/par/ref/avg/mode", True)
        else:
            # Set antenna reference position manually
            await set("/par/ref/avg/mode", False)
            await set(
                "/par/ref/pos//xyz",
                "{{W84,{0.x},{0.y},{0.z}}}".format(self.settings.position),
            )

        # Enable the appropriate GNSS systems. Note that we never disable a GNSS
        # system if it was enabled by the user; this is intentional as the user
        # might want to _track_ certain satellites for calculating the position
        # but does not want to send RTK corrections based on them
        if self.settings.uses_gnss(GNSSType.GPS):
            await set("/par/pos/sys/gps", "y")
        if self.settings.uses_gnss(GNSSType.GLONASS):
            await set("/par/pos/sys/glo", "y")
        if self.settings.uses_gnss(GNSSType.GALILEO):
            await set("/par/pos/sys/gal", "y")
        if self.settings.uses_gnss(GNSSType.SBAS):
            await set("/par/pos/sys/sbas", "y")
        if self.settings.uses_gnss(GNSSType.QZSS):
            await set("/par/pos/sys/qzss", "y")
        if self.settings.uses_gnss(GNSSType.BEIDOU):
            await set("/par/pos/sys/comp", "y")
        if self.settings.uses_gnss(GNSSType.IRNSS):
            await set("/par/pos/sys/irnss", "y")

        # Do not use fixed altitude
        await set("/par/pos/fix/alt", False)

        # Enable RTCM3 messages
        msg_intervals: dict[int, int] = {1006: 5}
        if self.settings.message_set is RTKMessageSet.MSM7:
            offset = 7
        else:
            offset = 4
        if self.settings.uses_gnss(GNSSType.GPS):
            msg_intervals[1070 + offset] = 1
        if self.settings.uses_gnss(GNSSType.GLONASS):
            msg_intervals[1080 + offset] = 1
            msg_intervals[1230] = 5
        if self.settings.uses_gnss(GNSSType.GALILEO):
            msg_intervals[1090 + offset] = 1
        if self.settings.uses_gnss(GNSSType.SBAS):
            msg_intervals[1100 + offset] = 1
        if self.settings.uses_gnss(GNSSType.QZSS):
            msg_intervals[1110 + offset] = 1
        if self.settings.uses_gnss(GNSSType.BEIDOU):
            msg_intervals[1120 + offset] = 1
        msg_spec = ",".join(
            str(msg_id) if interval == 1 else f"{msg_id}:{interval}"
            for msg_id, interval in msg_intervals.items()
        )
        await send(f"em,,/msg/rtcm3/{{{msg_spec}}}:1")

        # Also enable NMEA GST messages so we get position RMS estimates
        await send("em,,/msg/nmea/GST:1")

        # Reset receiver -- this should be needed to actually start the survey,
        # but the connection would probably break when doing so
        # await set("/par/reset")

        # Reset RTK engine -- apparently it is for the rover mode only
        # await set("/par/pos/pd/reset")

        # set,/par/ref/limit,3  -- if the current position is at least 3 m away
        # from the one assumed as the RTK origin, stop transmitting corrections.
        # This does not seem to be good because if the Javad receiver is not
        # supplied with an external RTK stream, its own position estimate will
        # float around and thus it will stop providing the antenna position
        # message.

        # Use init,/par/ to reset everything to factory defaults


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
            argv[1] if len(argv) > 1 else "/dev/cu.TRIUMPH201421-SerialPort"
        )
        parser = create_gps_parser()

        async with open_nursery() as nursery:
            settings = RTKSurveySettings()
            settings.set_gnss_types(["gps", "glonass", "galileo", "sbas"])
            config = JavadRTKBaseConfigurator(settings)
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
