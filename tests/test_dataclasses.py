from dataclasses import dataclass, field
from typing import Any

from dataclass_deser import DeserContext


@dataclass
class Nested:
    art: str
    rules: bool


@dataclass
class Config:
    nested: Nested
    foo: int
    bar: str


def test_baic_dataclasses():
    def construct(target: type | None):
        return (target or Config)(
            nested=(target or Nested)(art="foo", rules=True), foo=3, bar="foo"
        )

    raw_data = construct(dict)
    assert type(raw_data) is dict
    result: Config = DeserContext().deser(Config, raw_data)
    assert result == construct(None)
