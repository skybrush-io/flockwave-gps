from pytest import raises
from flockwave.gps.enums import GNSSType

from flockwave.gps.rtk import RTKMessageSet, RTKSurveySettings

from flockwave.gps.vectors import ECEFCoordinate


def test_rtk_survey_settings_to_and_from_json():
    settings = RTKSurveySettings()
    obj = settings.json

    settings_new = RTKSurveySettings.from_json(obj)

    assert settings == settings_new


def test_survey_settings_to_json_with_gnss_subset():
    settings = RTKSurveySettings()
    settings.set_gnss_types(["gps", "beidou"])
    obj = settings.json

    settings_new = RTKSurveySettings.from_json(obj)

    assert settings == settings_new

    settings.set_gnss_types(["glonass"])
    assert settings.json["gnssTypes"] == ["glonass"]

    settings.set_gnss_types(None)
    assert "gnssTypes" not in settings.json


def test_survey_settings_to_json_with_fixed_position():
    settings = RTKSurveySettings()
    settings.position = ECEFCoordinate(4120354, 1418752, 4641855)
    obj = settings.json

    settings_new = RTKSurveySettings.from_json(obj)

    assert settings == settings_new

    settings.position = None
    assert "position" not in settings.json


def test_rtk_survey_settings_reset():
    defaults = RTKSurveySettings()

    settings = RTKSurveySettings()
    settings.set_gnss_types(["gps", "beidou"])
    settings.accuracy = 32
    settings.duration = 128

    assert settings != defaults

    settings.reset_to_defaults()
    assert settings == defaults


def test_rtk_survey_settings_update_from_json():
    settings = RTKSurveySettings()
    settings.update_from_json(
        {
            "duration": 240,
            "accuracy": 0.5,
            "gnssTypes": ["gps", "glonass"],
            "position": [4120354, 1418752, 4641855],
        }
    )

    assert settings.duration == 240
    assert settings.accuracy == 0.5
    assert settings.gnss_types == set([GNSSType.GPS, GNSSType.GLONASS])
    assert settings.message_set == RTKMessageSet.MSM7
    assert settings.position == ECEFCoordinate(4120354, 1418752, 4641855)

    settings.update_from_json({"duration": 180, "messageSet": "msm4", "position": None})

    assert settings.duration == 180
    assert settings.accuracy == 0.5
    assert settings.gnss_types == set([GNSSType.GPS, GNSSType.GLONASS])
    assert settings.message_set is RTKMessageSet.MSM4
    assert settings.position is None

    settings.update_from_json({"duration": 180, "messageSet": "msm4"}, reset=True)

    assert settings.duration == 180
    assert settings.accuracy == 1
    assert settings.gnss_types is None
    assert settings.message_set is RTKMessageSet.MSM4


def test_rtk_survey_settings_update_from_json_errors():
    settings = RTKSurveySettings()

    with raises(ValueError):
        settings.update_from_json(123)

    with raises(ValueError):
        settings.update_from_json({"accuracy": "hey!"})

    with raises(ValueError):
        settings.update_from_json({"duration": [123]})

    with raises(ValueError):
        settings.update_from_json({"messageSet": "noSuchMessageSet"})

    with raises(ValueError):
        settings.update_from_json({"gnssTypes": {"gps": 1, "beidou": 2}})

    with raises(ValueError):
        settings.update_from_json({"gnssTypes": 77})

    with raises(ValueError):
        settings.update_from_json({"gnssTypes": ["turul"]})

    with raises(ValueError):
        settings.update_from_json({"position": {"x": 1, "y": 2}})

    with raises(ValueError):
        settings.update_from_json({"position": 123})


def test_rtk_survey_uses_gnss():
    settings = RTKSurveySettings()

    for type in GNSSType:
        assert settings.uses_gnss(type)

    settings.set_gnss_types(["gps", "beidou"])

    for type in GNSSType:
        if type.value in ("gps", "beidou"):
            assert settings.uses_gnss(type)
        else:
            assert not settings.uses_gnss(type)
