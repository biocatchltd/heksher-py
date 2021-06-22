from __future__ import annotations

import collections.abc
from abc import ABC, abstractmethod
from enum import Enum, IntFlag
from logging import getLogger
from types import MappingProxyType
from typing import Any, Optional, Tuple, Type

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


class SettingType(ABC):
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
    def convert(self, x):
        """
        Args:
            x: JSON-parsed value, retrieved from http api

        Returns:
            x, converted to an immutable pythonic value

        Notes:
            convert must return an immutable value
        """
        pass


class SimpleSettingType(SettingType):
    """
    A setting type for immutable primitives
    """

    def __init__(self, name):
        """
        Args:
            name: The name of the primitive in heksher specs
        """
        self.name = name

    def heksher_string(self) -> str:
        return self.name

    def convert(self, x):
        return x


class FlagsType(SettingType):
    """
    A setting type for flags, reflecting a flags of strings in heksher service.
    Notes:
        Although the heksher type is a flag of strings, the python type must be an IntFlags, where the strings are the
         member names.
    """

    def __init__(self, flags_type: Type[IntFlag]):
        """
        Args:
            flags_type: The IntFlags subclass to use as a type
        """
        self.type_ = flags_type

    def heksher_string(self) -> str:
        return 'Flags[' + ','.join(sorted(str(orjson.dumps(x), 'utf-8') for x in self.type_.__members__)) + ']'

    def convert(self, x):
        ret = self.type_(0)
        for i in x:
            if not isinstance(i, str):
                raise TypeError(f'expected string in flags, got {type(i).__name__}')
            try:
                member = self.type_[i]
            except KeyError:
                logger.error('server sent a flag value not found in the python type',
                             extra={'setting_type': self.heksher_string(), 'received value': i})
            else:
                ret |= member
        return ret


class EnumType(SettingType):
    """
    A setting type for an enum of primitive values
    """

    def __init__(self, enum_type: Type[Enum]):
        """
        Args:
            enum_type: The Enum subclass to use as a type
        """
        self.type_ = enum_type

    def heksher_string(self) -> str:
        return 'Enum[' + ','.join(sorted(str(orjson.dumps(x.value), 'utf-8') for x in self.type_)) + ']'

    def convert(self, x):
        return self.type_(x)


class GenericSequenceType(SettingType):
    """
    A setting type for a sequence type
    """

    def __init__(self, inner: SettingType):
        """
        Args:
            inner: the inner setting type of each member
        """
        self.inner = inner

    def heksher_string(self) -> str:
        return f'Sequence<{self.inner.heksher_string()}>'

    def convert(self, x):
        return tuple(self.inner.convert(i) for i in x)


class GenericMappingType(SettingType):
    """
    A setting type for a mapping type with string keys
    """

    def __init__(self, inner: SettingType):
        """
        Args:
            inner: the inner setting type of each value in the
        """
        self.inner = inner

    def heksher_string(self) -> str:
        return f'Mapping<{self.inner.heksher_string()}>'

    def convert(self, x):
        return MappingProxyType({k: self.inner.convert(v) for (k, v) in x.items()})


_simples = {
    int: SimpleSettingType('int'),
    float: SimpleSettingType('float'),
    str: SimpleSettingType('str'),
    bool: SimpleSettingType('bool'),
}


def setting_type(py_type: Any) -> SettingType:
    """
    Parse a python type to a heksher setting type
    Args:
        py_type: the python type or genetic alias to parse

    Returns:
        A SettingType respective of py_type

    """
    if isinstance(py_type, type):
        simple = _simples.get(py_type)
        if simple:
            return simple
        if issubclass(py_type, IntFlag):
            return FlagsType(py_type)
        if issubclass(py_type, Enum):
            return EnumType(py_type)
    # we can't depend on GenericAlias to act the way we expect it to, we instead use get_origin and get_args
    if get_origin(py_type) is collections.abc.Sequence:
        arg, = get_args(py_type)
        inner = setting_type(arg)
        return GenericSequenceType(inner)
    if get_origin(py_type) is collections.abc.Mapping:
        key_type, value_type = get_args(py_type)
        if key_type is not str:
            raise TypeError('the key for mapping setting types must always be str')
        inner = setting_type(value_type)
        return GenericMappingType(inner)
    raise RuntimeError(f'could not convert python value {py_type} to setting type')
