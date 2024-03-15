import json
from dataclasses import dataclass

from typing_extensions import Self, override

from dataclass_deser.deser import DeserContext, DeserError, DeserializeCustom

from .shared import assert_type


@dataclass
class Duck(DeserializeCustom):
    name: str

    @classmethod
    @override
    def _deser_custom(cls, ctx: DeserContext, value: object) -> Self:
        assert cls is Duck, "Cannot deserialize explicit subclass"
        match value:
            case {"name": _, "children": _}:
                return assert_type(Advanced, Advanced._deser_default(ctx, value))
            case str(name) | {"name": name}:
                return Duck(name=ctx.deser(str, name))
            case _:
                raise DeserError(f"Unexpected value: {value!r}", ctx=ctx)


@dataclass
class Advanced(Duck):
    children: list[Duck]


def test_custom_duck():
    raw_data = [
        "Veronica",
        "Samuel",
        {
            "name": "King",
            "children": [
                "prince",
                "princess",
                {"name": "long-form"},
                {"name": "long-form-advanced", "children": ["nested-child"]},
            ],
        },
    ]
    expected = [
        Duck("Veronica"),
        Duck("Samuel"),
        Advanced(
            "King",
            children=[
                Duck("prince"),
                Duck("princess"),
                Duck("long-form"),
                Advanced("long-form-advanced", children=[Duck("nested-child")]),
            ],
        ),
    ]
    result: list[Duck] = DeserContext().deser(list[Duck], raw_data)
    assert result == expected
