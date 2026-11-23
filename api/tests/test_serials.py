import re

import pytest

from sigil.serials import (
    SERIAL_BYTES,
    SERIAL_CHARS,
    SerialError,
    decode_serial,
    encode_serial,
    generate_serial,
    is_valid_serial,
)


def test_generated_serials_have_the_right_shape():
    serial = generate_serial()
    assert len(serial) == SERIAL_BYTES
    text = encode_serial(serial)
    assert len(text) == SERIAL_CHARS
    assert re.fullmatch(r"[A-Z2-7]{16}", text)


def test_round_trip():
    for _ in range(100):
        raw = generate_serial()
        assert decode_serial(encode_serial(raw)) == raw


def test_serials_are_unique_in_practice():
    values = {generate_serial() for _ in range(2000)}
    assert len(values) == 2000


def test_invalid_serials_are_rejected():
    for bad in ["", "ABC", "abcdefghijklmnop", "AAAAAAAAAAAAAAA0", "AAAAAAAAAAAAAAA="]:
        assert not is_valid_serial(bad)
        with pytest.raises(SerialError):
            decode_serial(bad)


def test_encoder_rejects_wrong_length():
    with pytest.raises(SerialError):
        encode_serial(b"\x00" * 9)
