from __future__ import annotations

import collections.abc
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, IntFlag
from logging import getLogger
from types import MappingProxyType
from typing import Any, Generic, Mapping, Optional, Sequence, Tuple, Type, TypeVar

import orjson

try:
    from types import GenericAlias  # type: ignore[attr-defined]
except ImportError:
    GenericAlias = None  # type: ignore[misc]

try:
    from typing import get_args, get_origin  # type: ignore[attr-defined]
except ImportError:
    # functions only available for 3.8 and up
    def get_args(tp: Any) -> Tuple[Any, ...]:
        return getattr(tp, '__args__', ())

    def get_origin(tp: Any) -> Optional[Any]:
        return getattr(tp, '__origin__', None)

logger = getLogger(__name__)

T = TypeVar('T')


@dataclass
class Conversion(Generic[T]):
    value: T
    coercions: Sequence[str] = ()


class SettingType(ABC, Generic[T]):
    """
    Base class for setting types
    """

    @abstractmethod
    def heksher_string(self) -> str:
        """
        Returns: The type as string, as specified by the Heksher specs
        """
        pass

    @abstractmethod
    def convert_from_heksher(self, x) -> Conversion[T]:
        """
        Args:
            x: JSON-parsed value, retrieved from http api

        Returns:
            x, converted to an immutable pythonic value

        Notes:
            convert must return an immutable value
        """
        pass

    @abstractmethod
    def convert_to_heksher(self, x: T) -> Any:
        """
        Args:
            x: immutable pythonic value

        Returns:
            x, JSON-parsed value
        """
        pass

    def __eq__(self, other):
        return isinstance(other, SettingType) and self.heksher_string() == other.heksher_string()


class SimpleSettingType(SettingType[T]):
    """
    A setting type for immutable primitives
    """

    def __init__(self, name, acceptable_types: Tuple[type, ...]):
        self.name = name
        self.type = acceptable_types

    def heksher_string(self) -> str:
        return self.name

    def convert_from_heksher(self, x):
        if not isinstance(x, self.type):
            raise TypeError(f'value is not of type {self.type}')
        return Conversion(x)

    def convert_to_heksher(self, x: T) -> Any:
        return x


F = TypeVar('F', bound=IntFlag)


class HeksherFlags(SettingType[F]):
    """
    A setting type for flags, reflecting a flags of strings in heksher service.
    Notes:
        Although the heksher type is a flag of strings, the python type must be an IntFlags, where the strings are the
         member names.
    """

    def __init__(self, flags_type: Type[F]):
        """
        Args:
            flags_type: The IntFlags subclass to use as a type
        """
        self.type_ = flags_type

    def heksher_string(self) -> str:
        return 'Flags[' + ','.join(sorted(str(orjson.dumps(x), 'utf-8') for x in self.type_.__members__)) + ']'

    def convert_from_heksher(self, x) -> Conversion[F]:
        ret = self.type_(0)
        coercions = []
        for i in x:
            if not isinstance(i, str):
                raise TypeError(f'expected string in flags, got {type(i).__name__}')
            try:
                member = self.type_[i]
            except KeyError:
                coercions.append(f'server sent a flag value not found in the python type ({i})')
            else:
                ret |= member
        return Conversion(ret, coercions)

    def convert_to_heksher(self, x: F) -> Any:
        return [flag.name for flag in self.type_ if x & flag]


E = TypeVar('E', bound=Enum)


class HeksherEnum(SettingType[E]):
    """
    A setting type for an enum of primitive values
    """

    def __init__(self, enum_type: Type[E]):
        """
        Args:
            enum_type: The Enum subclass to use as a type
        """
        self.type_ = enum_type
        for member in self.type_:
            if type(member.value) not in (int, str, float, bool):
                raise TypeError(f'enum member {member} has a non-primitive value of type')

    def heksher_string(self) -> str:
        return 'Enum[' + ','.join(sorted(str(orjson.dumps(x.value), 'utf-8') for x in self.type_)) + ']'

    def convert_from_heksher(self, x) -> Conversion[E]:
        try:
            return Conversion(self.type_(x))
        except ValueError as ve:
            raise TypeError('value is not a valid enum member') from ve

    def convert_to_heksher(self, x: E) -> Any:
        return x.value


class HeksherSequence(SettingType[Sequence[T]]):
    """
    A setting type for a sequence type
    """

    def __init__(self, inner: SettingType[T]):
        """
        Args:
            inner: the inner setting type of each member
        """
        self.inner = setting_type(inner)

    def heksher_string(self) -> str:
        return f'Sequence<{self.inner.heksher_string()}>'

    def convert_from_heksher(self, x) -> Conversion[Sequence[T]]:
        values = []
        coercions = []
        for i, v in enumerate(x):
            try:
                conversion = self.inner.convert_from_heksher(v)
            except TypeError as e:
                coercions.append(f'failed to convert element {i}: {e!r}')
            else:
                values.append(conversion.value)
                coercions.extend(f'element {i}: {c}' for c in conversion.coercions)
        return Conversion(tuple(values), coercions)

    def convert_to_heksher(self, x: Sequence[T]) -> Any:
        return [self.inner.convert_to_heksher(v) for v in x]


class HeksherMapping(SettingType[Mapping[str, T]]):
    """
    A setting type for a mapping type with string keys
    """

    def __init__(self, inner: SettingType[T]):
        """
        Args:
            inner: the inner setting type of each value in the
        """
        self.inner = setting_type(inner)

    def heksher_string(self) -> str:
        return f'Mapping<{self.inner.heksher_string()}>'

    def convert_from_heksher(self, x) -> Conversion[Mapping[str, T]]:
        values = {}
        coercions = []
        for k, v in x.items():
            try:
                conversion = self.inner.convert_from_heksher(v)
            except TypeError as e:
                coercions.append(f'failed to convert value for key {k}: {e!r}')
            else:
                values[k] = conversion.value
                coercions.extend(f'{k}: {c}' for c in conversion.coercions)
        return Conversion(MappingProxyType(values), coercions)

    def convert_to_heksher(self, x: Mapping[str, T]) -> Any:
        return {k: self.inner.convert_to_heksher(v) for k, v in x.items()}


_simples: Mapping[type, SettingType] = {
    int: SimpleSettingType('int', (int,)),
    float: SimpleSettingType('float', (int, float)),
    str: SimpleSettingType('str', (str,)),
    bool: SimpleSettingType('bool', (bool,)),
}


def setting_type(arg: Any) -> SettingType:
    """
    Parse a python type to a heksher setting type
    Args:
        arg: the python type, genetic alias, or setting type to parse

    Returns:
        A SettingType respective of arg

    """
    if isinstance(arg, SettingType):
        return arg
    simple = _simples.get(arg)
    if simple:
        return simple
    if isinstance(arg, type):
        if issubclass(arg, IntFlag):
            return HeksherFlags(arg)
        if issubclass(arg, Enum):
            return HeksherEnum(arg)
    # we can't depend on GenericAlias to act the way we expect it to, we instead use get_origin and get_args
    if get_origin(arg) is collections.abc.Sequence:
        arg, = get_args(arg)
        return HeksherSequence(setting_type(arg))
    if get_origin(arg) is collections.abc.Mapping:
        key_type, value_type = get_args(arg)
        if key_type is not str:
            raise TypeError('the key for mapping setting types must always be str')
        return HeksherMapping(setting_type(value_type))
    raise RuntimeError(f'could not convert value {arg} to setting type')
