"""Shared testing code"""

from typing import TypeVar

TC = TypeVar("TC")


def assert_type(expected: type[TC], value: object) -> TC:
    assert isinstance(value, expected), f"Expected type {expected}: {value!r}"
    return value
