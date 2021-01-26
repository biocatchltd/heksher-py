from __future__ import annotations

import collections.abc
from abc import ABC, abstractmethod
from enum import Enum, IntFlag
from logging import getLogger
from typing import Union, Type, Any

import orjson

try:
    from types import GenericAlias  # pytype: disable=import-error
except ImportError:
    GenericAlias = None

try:
    from typing import get_args, get_origin  # pytype: disable=import-error
except ImportError:
    # functions only available for 3.8 and up
    def get_args(x):
        return getattr(x, '__args__', ())

    def get_origin(x):
        return getattr(x, '__origin__', None)

# in the library, a setting type is just a string denoting the type's specs (in heksher format), with an additional
# method to convert a JSON value to a more pythonic one (usually this will be a no-op)

logger = getLogger(__name__)


class SettingType(ABC):
    @abstractmethod
    def heksher_string(self) -> str:
        pass

    @abstractmethod
    def convert(self, x):
        # note that convert must only return x if it is immutable, passing mutable values through could be disastrous
        pass


class SimpleSettingType(SettingType):
    def __init__(self, name):
        self.name = name

    def heksher_string(self) -> str:
        return self.name

    def convert(self, x):
        return x


class FlagsType(SettingType):
    def __init__(self, flags_type: Type[IntFlag]):
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
    def __init__(self, enum_type: Type[Enum]):
        self.type_ = enum_type

    def heksher_string(self) -> str:
        return 'Enum[' + ','.join(sorted(str(orjson.dumps(x.value), 'utf-8') for x in self.type_)) + ']'

    def convert(self, x):
        return self.type_(x)


class GenericSequenceType(SettingType):
    def __init__(self, inner: SettingType):
        self.inner = inner

    def heksher_string(self) -> str:
        return f'Sequence<{self.inner.heksher_string()}>'

    def convert(self, x):
        return [self.inner.convert(i) for i in x]


class GenericMappingType(SettingType):
    def __init__(self, inner: SettingType):
        self.inner = inner

    def heksher_string(self) -> str:
        return f'Mapping<{self.inner.heksher_string()}>'

    def convert(self, x):
        return {k: self.inner.convert(v) for (k, v) in x.items()}


if GenericAlias:
    SettingTypeInput = Union[  # pytype: disable=invalid-annotation
        Type[str],
        Type[bool],
        Type[int],
        Type[float],
        GenericAlias,
        Type[Enum],
        Type[IntFlag],
    ]
else:
    SettingTypeInput = Any

_simples = {
    int: SimpleSettingType('int'),
    float: SimpleSettingType('float'),
    str: SimpleSettingType('str'),
    bool: SimpleSettingType('bool'),
}


def setting_type(py_type: SettingTypeInput) -> SettingType:  # pytype: disable=invalid-annotation
    if isinstance(py_type, type):
        simple = _simples.get(py_type)
        if simple:
            return simple
        if issubclass(py_type, IntFlag):
            return FlagsType(py_type)
        if issubclass(py_type, Enum):
            return EnumType(py_type)
    # we can't depend on GenericAlias to act the way we expect it to, we instead use get_origin and get_args
    if get_origin(py_type) in (list, collections.abc.Sequence, collections.abc.MutableSequence):
        arg, = get_args(py_type)
        inner = setting_type(arg)
        return GenericSequenceType(inner)
    if get_origin(py_type) in (dict, collections.abc.Mapping, collections.abc.MutableMapping):
        key_type, value_type = get_args(py_type)
        if key_type is not str:
            raise TypeError('the key for mapping setting types must always be str')
        inner = setting_type(value_type)
        return GenericMappingType(inner)
    raise RuntimeError(f'could not convert python value {py_type} to setting type')
