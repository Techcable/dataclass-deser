import contextlib
import dataclasses
import re
from typing import Iterator, NoReturn, TypeAlias, TypeVar, cast
from typing import get_args as get_type_args
from typing import get_origin as get_type_origin

try:
    from typing_extensions import assert_never, assert_type
except ImportError:
    from typing import assert_never, assert_type

__all__ = ("DeserContext", "ContextItem")

SIMPLE_KEY_PATTERN: re.Pattern[str] = re.compile(r"[\w_\-]+")

TD = TypeVar("TD")
ContextItem: TypeAlias = str | int


class DeserContext:
    # Settings
    strict_keys: bool
    # State
    _context_items: list[ContextItem]

    def __init__(self) -> None:
        self.strict_keys = True
        self._context_items = []

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
    def context(self) -> str:
        """Describe the context as a string"""
        items = self._context_items
        if not items:
            return "."
        res = []
        for item in reversed(items):
            match item:
                case str(key):
                    if SIMPLE_KEY_PATTERN.fullmatch(key):
                        res.append(f".")
                    else:
                        res.append(f".[{key!r}]")
                case int(idx):
                    res.append(f"[{idx}]")
                case invalid:
                    assert_never(invalid)
        assert res
        return "".join(res)

    def deser(self, target_type: type[TD], value: object) -> TD:
        def _unexpected_type(expected: type) -> NoReturn:
            raise DeserError(
                f"Expected type {expected}, but got {type(value)} (at {self.context})"
            )

        erased_type: type | None = get_type_origin(target_type)
        if target_type in (str, bool, int, float):
            if isinstance(value, target_type):
                # Need cast for pyright, and ignore for mypy redundant-cast
                #
                # Cannot replace with plain type: ignore,
                # because then mypy gives redundant-ignore
                return cast(TD, value)  # type: ignore
            else:
                _unexpected_type(target_type)
        elif erased_type is not None and issubclass(erased_type, list):
            type_args = get_type_args(target_type)
            element_type: type
            match type_args:
                case (element_type,):
                    pass
                case other:
                    raise TypeError(f"Bad args for list: {other!r}")
            if not isinstance(value, list):
                _unexpected_type(list)
            result: list[object] = []
            for index, element in enumerate(value):
                with self._add_context(index):
                    result.append(self.deser(element_type, element))
            return cast(TD, result)
        elif dataclasses.is_dataclass(target_type):
            fields = dataclasses.fields(target_type)
            if not isinstance(value, dict):
                _unexpected_type(dict)
            remaining_values = dict(value)  # Defensive copy
            res: dict[str, object] = {}
            for field in fields:
                key = field.name
                if key not in remaining_values:
                    raise DeserError(f"Missing key {key!r} (at {self.context})")
                with self._add_context(key):
                    raw_value = remaining_values.pop(key)
                    deser_value = self.deser(field.type, raw_value)
                    res[key] = deser_value
            if remaining_values and self.strict_keys:
                raise DeserError(
                    f"Unexpected keys {set(remaining_values.keys())} for {target_type} (at {self.context})"
                )
            # Try to construct target_type
            return cast(TD, target_type(**res))
        else:
            raise TypeError(
                f"Unsupported target type {target_type} (at {self.context})"
            )


class DeserError(ValueError):
    pass
