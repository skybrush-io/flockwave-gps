from flockwave.gps.ubx.message import UBX


def test_encoding():
    message = UBX.MON_VER().encode()
    assert message == b"\xb5b\n\x04\x00\x00\x0e4"

    message = UBX.MON_VER(b"EXT CORE 1").encode()
    assert message == b"\xb5b\n\x04\x0a\x00EXT CORE 1\xa3'"
