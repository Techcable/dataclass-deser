# dataclass-deser ![PyPI - Version](https://img.shields.io/pypi/v/dataclass-deser)
A simple deserialization library for python based on dataclasses and type hints.

I've written this code repeatedly across several of my scripts,
so I've decided to publish it to PyPi for reuse.

## Basic Example
```python
@dataclass
class Nested:
    foo: int

@dataclass
class Foo:
    bar: int
    baz: list[int]
    nested: Nested

raw_json = """{
    "bar": 3,
    "baz": [1, 2, 8],
    "nested": {"foo": 42}
}"""
expected = Foo(
    bar=3,
    baz=[1, 2, 8],
    nested=Nested(foo=42)
)

ctx = dataclass_deser.DeserContext()
assert expected == ctx.deser(Foo, json.loads(raw_json))
```

## Status
**WARNING**: This library is **ALPHA qUaLitY**

- [x] Basic primitive deserialization
   - [ ] Support lossless numeric conversions (int -> float)
   - [ ] Support lossy numeric conversion
- [ ] Support for optional types
- [ ] Support for union types (int | str | bytes)
- [ ] Configuration options
   - [x] Allow unused keys
- [ ] Extensibility
   - [ ] Field options via dataclass field.metadata
   - [ ] Newtype wrappers
- [ ] Support more collections
   - [ ] Dictionaries
   - [ ] Tuples
   - [ ] Sets
- [ ] Support enumerations

