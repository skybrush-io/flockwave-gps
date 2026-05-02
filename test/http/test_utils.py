import pytest

from flockwave.gps.http.utils import CaseInsensitiveMapping


def test_get_set_and_contains_are_case_insensitive():
    mapping = CaseInsensitiveMapping[bytes]()

    mapping["Content-Type"] = b"text/plain"

    assert mapping["Content-Type"] == b"text/plain"
    assert mapping["content-type"] == b"text/plain"
    assert mapping["CONTENT-TYPE"] == b"text/plain"
    assert "content-type" in mapping
    assert "CONTENT-TYPE" in mapping


def test_setting_same_header_with_different_case_replaces_old_entry():
    mapping = CaseInsensitiveMapping[str]()

    mapping["Content-Type"] = "text/plain"
    mapping["content-type"] = "application/json"

    assert len(mapping) == 1
    assert mapping["CONTENT-TYPE"] == "application/json"
    assert list(mapping.items()) == [("content-type", "application/json")]


def test_deleting_is_case_insensitive():
    mapping = CaseInsensitiveMapping[int]()

    mapping["X-Test"] = 42
    del mapping["x-test"]

    assert len(mapping) == 0
    with pytest.raises(KeyError):
        _ = mapping["X-Test"]


def test_replacing_key_moves_it_to_the_end_of_iteration_order():
    mapping = CaseInsensitiveMapping[int]()

    mapping["A"] = 1
    mapping["B"] = 2
    mapping["a"] = 3

    assert list(mapping.items()) == [("B", 2), ("a", 3)]


def test_missing_key_raises_key_error_on_get_and_delete():
    mapping = CaseInsensitiveMapping[str]()

    with pytest.raises(KeyError):
        _ = mapping["missing"]

    with pytest.raises(KeyError):
        del mapping["missing"]
