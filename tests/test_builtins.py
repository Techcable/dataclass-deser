"""Tests for deserializing builtin classes"""

from dataclass_deser import DeserContext


def assert_roundtrip(tp: type, val: object):
    assert val == DeserContext().deser(tp, val), f"roundtrip {val} as {tp}"


def test_primitives() -> None:
    assert_roundtrip(int, 3)
    assert_roundtrip(float, 7.2)
    assert_roundtrip(str, "foo")

    # Conversion int -> float
    assert_roundtrip(float, 7)


def test_implicit_float_conversions() -> None:
    assert 3 == DeserContext().deser(int, 3.7)


def test_basic_list():
    assert_roundtrip(list[int], [])
    assert_roundtrip(list[int], [3, 4, 7])


def test_nested_list():
    assert_roundtrip(list[list[int]], [[3, 7], [], [8, 9]])
