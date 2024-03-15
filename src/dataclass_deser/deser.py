from __future__ import annotations

import contextlib
import dataclasses
import inspect
import re
import types
from abc import ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Iterator,
    NoReturn,
    Optional,
    TypeAlias,
    TypeVar,
    Union,
    cast,
)
from typing import get_args as get_type_args
from typing import get_origin as get_type_origin
from typing import get_type_hints

from typing_extensions import Self, assert_never, deprecated, final

__all__ = ("DeserContext", "DeserializeCustom", "DeserError")

SIMPLE_KEY_PATTERN: re.Pattern[str] = re.compile(r"[\w_\-]+")


@dataclasses.dataclass(slots=True)
class _LocationDictKey:
    dict_position: int
    key_value: Any

    def __str__(self) -> str:
        return DeserLocation._fmt_ctx_item(self)


TD = TypeVar("TD")
ContextItem: TypeAlias = str | int | _LocationDictKey


class DeserializeCustom(metaclass=ABCMeta):
    """A type that supports custom deserialization"""

    @classmethod
    @abstractmethod
    def _deser_custom(self, ctx: DeserContext, value: object) -> Self:
        pass

    @classmethod
    @final
    def _deser_default(cls, ctx: DeserContext, value: object) -> Self:
        assert isinstance(ctx, DeserContext)
        if id(value) in ctx._ignore_deserialize_custom:
            raise DeserError(
                f"Already supposed to ignore object (recursion?): {cls}, {value!r}",
                ctx=ctx,
            )
        ctx._ignore_deserialize_custom.add(id(value))
        try:
            result = ctx.deser(cls, value)
        finally:
            ctx._ignore_deserialize_custom.remove(id(value))
        return result


class DeserLocation(tuple[ContextItem, ...]):
    @staticmethod
    def _fmt_ctx_item(item: ContextItem) -> str:
        match item:
            case str(key):
                if SIMPLE_KEY_PATTERN.fullmatch(key):
                    return f".{key}"
                else:
                    return f".[{key!r}]"
            case int(idx):
                return f"[{idx}]"
            case _LocationDictKey(dict_position=dict_pos, key_value=key_value):
                match key_value:
                    case str(key):
                        return DeserLocation._fmt_ctx_item(key)
                    case int(_) | float(_):
                        return f".[{key_value!r}]"
                    case _:
                        # Dicts preserve ordering, so use that
                        return f".[#{dict_pos}]"
            case invalid:
                assert_never(invalid)

    def __str__(self) -> str:
        if not self:
            return "."
        res = []
        for item in self:
            res.append(DeserLocation._fmt_ctx_item(item))
        return "".join(res)


class DeserContext:
    # Settings
    strict_keys: bool
    # State
    _context_items: list[ContextItem]
    _ignore_deserialize_custom: set[int]

    def __init__(self) -> None:
        self.strict_keys = True
        self._context_items = []
        self._ignore_deserialize_custom = set()

    @contextlib.contextmanager
    def _add_context(self, item: ContextItem) -> Iterator[None]:
        expected_state = (len(self._context_items), item)
        self._context_items.append(item)
        yield
        # NOTE: We _want_ to ignore exceptions here
        removed_item = self._context_items.pop()
        actual_state = (len(self._context_items), removed_item)
        assert (
            actual_state == expected_state
        ), f"Expected {expected_state}, got {actual_state}"

    @property
    @deprecated("Replaced with `location` function")
    def context(self) -> str:
        return str(self.current_location)

    @property
    def current_location(self) -> DeserLocation:
        """Describe the context as a string"""
        return DeserLocation(self._context_items)

    def deser(self, target_type: type[TD], value: object) -> TD:
        def _unexpected_type(expected: str, *, target: str | None=None) -> NoReturn:
            target_info = "" if target is None else f" for {target}"
            raise DeserError(
                f"Expected a {expected}{target_info}, but got {type(value)}", ctx=self
            )

        erased_type = get_type_origin(target_type)
        if target_type in (str, bool, int, float, types.NoneType):
            if isinstance(value, target_type):
                # Need cast for pyright, and ignore for mypy redundant-cast
                #
                # Cannot replace with plain type: ignore,
                # because then mypy gives redundant-ignore
                return cast(TD, value)  # type: ignore
            else:
                _unexpected_type(str(target_type))
        elif erased_type is Union:
            type_args = get_type_args(target_type)
            match type_args:
                case (types.NoneType, element_type) | (element_type, types.NoneType):
                    # its an Optional type
                    if value is None:
                        return cast(TD, value)
                    else:
                        return cast(TD, self.deser(element_type, value))
                case unsupported_combo:
                    raise NotImplementedError(
                        f"Union types (except Optional) are NYI: {unsupported_combo}"
                    )
        elif (
            issubclass(
                deser_custom_type := (erased_type or target_type),
                DeserializeCustom,
            )
            and id(value) not in self._ignore_deserialize_custom
        ):
            return cast(
                TD,
                cast(type[DeserializeCustom], deser_custom_type)._deser_custom(
                    self, value
                ),
            )
        elif erased_type is not None and issubclass(erased_type, list):
            type_args = get_type_args(target_type)
            try:
                (element_type,) = type_args
            except ValueError:
                raise TypeError(f"Bad type args for list: {type_args!r}") from None
            if not isinstance(value, list):
                _unexpected_type('list')
            result_list: list[object] = []
            for index, element in enumerate(value):
                with self._add_context(index):
                    result_list.append(self.deser(element_type, element))
            return cast(TD, result_list)
        elif erased_type is not None and issubclass(erased_type, dict):
            type_args = get_type_args(target_type)
            try:
                (key_type, value_type) = type_args
            except ValueError:
                raise TypeError(f"Bad type args for dict: {type_args!r}") from None
            if not isinstance(value, dict):
                _unexpected_type('dict')
            result_dict: dict[object, object] = {}
            for item_position, (raw_key, raw_value) in enumerate(value.items()):
                with self._add_context(_LocationDictKey(item_position, raw_key)):
                    deser_key = self.deser(key_type, raw_key)
                    deser_value = self.deser(value_type, raw_value)
                    result_dict[deser_key] = deser_value
            return cast(TD, result_dict)
        elif dataclasses.is_dataclass(target_type):
            fields = dataclasses.fields(target_type)
            field_types = get_type_hints(target_type)
            if not isinstance(value, dict):
                _unexpected_type('dict', target=target_type)
            remaining_values = dict(value)  # Defensive copy
            res: dict[str, object] = {}
            for field in fields:
                key = field.name
                if key not in remaining_values:
                    if (
                        field.default is not dataclasses.MISSING
                        or field.default_factory not in (None, dataclasses.MISSING)
                        or not field.init
                    ):
                        continue  # skip field not needed
                    else:
                        raise DeserError(f"Missing key {key!r}", ctx=self)
                with self._add_context(key):
                    raw_value = remaining_values.pop(key)
                    field_type = field_types[key]
                    deser_value = self.deser(field_type, raw_value)
                    res[key] = deser_value
            if remaining_values and self.strict_keys:
                raise DeserError(
                    f"Unexpected keys {set(remaining_values.keys())} for {target_type}",
                    ctx=self,
                )
            # Try to construct target_type
            return cast(TD, target_type(**res))
        else:
            raise TypeError(
                f"Unsupported target type {target_type} (at {self.context})"
            )


class DeserError(ValueError):
    context: Optional[DeserContext]
    location: Optional[DeserLocation]

    def __init__(self, msg: str, /, *, ctx: Optional[DeserContext]):
        super().__init__(msg)
        self.context = ctx
        if ctx is not None:
            self.location = ctx.current_location
        else:
            self.location = None

    def __str__(self) -> str:
        super_msg = super().__str__()
        if self.location is not None:
            return f"{super_msg} (at {self.location})"
        else:
            return super_msg
