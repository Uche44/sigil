import pytest

from sigil.canonical import CanonicalJSONError, canonical_json, canonical_json_bytes


def test_keys_are_sorted_and_whitespace_removed():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert canonical_json({"z": [1, 2], "a": {"y": True, "b": None}}) == (
        '{"a":{"b":null,"y":true},"z":[1,2]}'
    )


def test_unicode_is_kept_as_utf8():
    assert canonical_json({"name": "Café"}) == '{"name":"Café"}'
    assert canonical_json_bytes({"name": "Café"}) == '{"name":"Café"}'.encode("utf-8")


def test_floats_are_rejected():
    with pytest.raises(CanonicalJSONError):
        canonical_json({"weight": 12.5})


def test_non_string_keys_and_unknown_types_are_rejected():
    with pytest.raises(CanonicalJSONError):
        canonical_json({1: "a"})
    with pytest.raises(CanonicalJSONError):
        canonical_json({"items": (1, 2)})


def test_same_content_same_bytes_regardless_of_insertion_order():
    one = {"a": 1, "b": {"c": [1, 2]}}
    two = {"b": {"c": [1, 2]}, "a": 1}
    assert canonical_json_bytes(one) == canonical_json_bytes(two)
