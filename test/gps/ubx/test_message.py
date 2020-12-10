from flockwave.gps.ubx import UBX, UBXClass, UBXParser


def test_encoder():
    message = UBX.MON_VER().encode()
    assert message == b"\xb5b\n\x04\x00\x00\x0e4"

    message = UBX.MON_VER(b"EXT CORE 1").encode()
    assert message == b"\xb5b\n\x04\x0a\x00EXT CORE 1\xa3'"


def test_parser():
    parser = UBXParser()

    parsed = []
    for ch in b"\xb5b\n\x04\x00\x00\x0e4":
        parsed.extend(parser.feed(bytes([ch])))

    assert len(parsed) == 1
    assert parsed[0].class_id == UBXClass.MON
    assert parsed[0].subclass_id == 4
    assert parsed[0].payload == b""

    mon_ver = b"\xb5b\n\x04\x0a\x00EXT CORE 1\xa3'"
    parsed = []
    for i in range(0, len(mon_ver), 2):
        parsed.extend(parser.feed(mon_ver[i : (i + 2)]))

    assert len(parsed) == 1
    assert parsed[0].class_id == UBXClass.MON
    assert parsed[0].subclass_id == 4
    assert parsed[0].payload == b"EXT CORE 1"
