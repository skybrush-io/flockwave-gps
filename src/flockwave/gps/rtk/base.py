from abc import abstractmethod, ABCMeta
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Set, Union

from flockwave.gps.enums import GNSSType

__all__ = ("RTKSurveySettings",)


class RTKMessageSet(Enum):
    """Supported RTK message sets that can be requested from an RTK base
    station.
    """

    MSM4 = "msm4"
    MSM7 = "msm7"


@dataclass
class RTKSurveySettings:
    """Object holding the settings of an RTK survey to be performed by an
    RTK-enabled base station before it can start streaming corrections.
    """

    #: Minimum duration of the survey, in seconds
    duration: float = 60

    #: Desired accuracy of the survey, in meters
    accuracy: float = 1

    #: Message set to request during the survey
    message_set: RTKMessageSet = RTKMessageSet.MSM7

    #: GNSS types to configure the survey for; `None` means to configure all
    #: supported GNSS types
    gnss_types: Optional[Set[GNSSType]] = None

    @classmethod
    def from_json(cls, data):
        result = cls()
        result.update_from_json(data)
        return result

    @property
    def json(self) -> Dict[str, Any]:
        result = {
            "duration": self.duration,
            "accuracy": self.accuracy,
            "messageSet": self.message_set,
        }
        if self.gnss_types is not None:
            result["gnssTypes"] = sorted(
                gnss_type.value for gnss_type in self.gnss_types
            )
        return result

    def reset_to_defaults(self) -> None:
        """Resets the settings object to the defaults that are used when
        constructing the object with no arguments.
        """
        self.duration = 60
        self.accuracy = 1
        self.message_set = RTKMessageSet.MSM7
        self.gnss_types = None

    def set_gnss_types(self, types: Optional[Iterable[Union[str, GNSSType]]]) -> None:
        if types is None:
            self.gnss_types = None
        else:
            if self.gnss_types is None:
                self.gnss_types = set()
            self.gnss_types.clear()
            self.gnss_types.update(GNSSType(value) for value in types)

    def update_from_json(self, data, *, reset: bool = False) -> None:
        """Updates an existing RTK survey settings object from the given
        JSON representation.

        Parameters:
            data: the JSON object
            reset: whether to reset the RTK survey settings to the default
                before applying the update

        Raises:
            ValueError: if the format of the JSON object is invalid
        """
        if not isinstance(data, dict):
            raise ValueError("RTK survey settings object missing or invalid")

        if reset:
            self.reset_to_defaults()

        accuracy = data.get("accuracy")
        if accuracy is not None:
            if not isinstance(accuracy, (float, int)) or accuracy <= 0:
                raise ValueError("invalid accuracy")
            else:
                self.accuracy = float(accuracy)

        duration = data.get("duration")
        if duration is not None:
            if not isinstance(duration, (float, int)) or duration <= 0:
                raise ValueError("invalid duration")
            else:
                self.duration = float(duration)

        message_set = data.get("messageSet")
        if message_set is not None:
            self.message_set = RTKMessageSet(message_set)

        if "gnssTypes" in data:
            gnss_types = data["gnssTypes"]
            if isinstance(gnss_types, dict):
                raise ValueError("invalid GNSS type list")
            elif isinstance(gnss_types, Iterable) or gnss_types is None:
                self.set_gnss_types(gnss_types)
            else:
                raise ValueError("invalid GNSS type list")

    def uses_gnss(self, gnss_type: GNSSType) -> bool:
        """Returns whether the RTK survey should use the given GNSS type if
        the receiver supports it.
        """
        return self.gnss_types is None or gnss_type in self.gnss_types


class RTKBaseConfigurator(metaclass=ABCMeta):
    """Interface specification for classes that know how to configure a specific
    type of GPS receiver as an RTK base with given survey-in duration and
    accuracy.
    """

    _settings: RTKSurveySettings

    def __init__(self, settings: RTKSurveySettings):
        """Constructor."""
        self._settings = settings

    @abstractmethod
    async def run(
        self,
        write: Callable[[bytes], Awaitable[None]],
        sleep: Callable[[float], Awaitable[None]],
    ):
        """Asynchronous task that configures a GPS receiver as an RTK base
        station.

        Parameters:
            write: a writer function that can be used to send commands to the GPS
                receiver
            sleep: a function that can be called to sleep a bit without blocking
                other tasks. Takes the number of seconds to sleep.
        """
        raise NotImplementedError  # pragma: no cover