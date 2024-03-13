# NOTE: Intentionally avoids `from future import __anotations__`
#
# Annotations are replaced with strings on a case-by-case basis

from dataclasses import dataclass, field
from typing import Any, Optional

from dataclass_deser import DeserContext


@dataclass
class Nested:
    art: str
    rules: bool
    stringy_typed_int: "int"


@dataclass
class Config:
    nested: Nested
    foo: int
    bar: str
    default_int: Optional[int] = None
    default_list: list[int] = field(default_factory=list)
    nested_stringy_type: "Optional[Nested]" = None


def test_baic_dataclasses():
    def construct(target: type | None):
        return (target or Config)(
            nested=(target or Nested)(art="foo", rules=True, stringy_typed_int=7),
            foo=3,
            bar="foo",
        )

    raw_data = construct(dict)
    assert type(raw_data) is dict
    result: Config = DeserContext().deser(Config, raw_data)
    assert result == construct(None)
    assert result.nested_stringy_type is None
