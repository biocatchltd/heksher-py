from enum import Enum, IntFlag, auto
from typing import Mapping, Sequence

from pytest import mark, raises

from heksher import HeksherEnum, HeksherFlags, HeksherMapping, HeksherSequence
from heksher.setting_type import Conversion, setting_type


@mark.parametrize('type_func', [lambda t: t, lambda t: HeksherEnum(t)])
def test_enum_type_from_heksher(type_func):
    class A(Enum):
        a = 0
        b = 1
        c = 'c'
        d = 3.5

    t = setting_type(type_func(A))
    assert t.heksher_string() == 'Enum["c",0,1,3.5]'
    assert t.convert_from_heksher(0) == Conversion(A.a)
    assert t.convert_from_heksher("c") == Conversion(A.c)
    with raises(TypeError):
        assert t.convert_from_heksher("b")


@mark.parametrize('type_func', [lambda t: t, lambda t: HeksherEnum(t)])
def test_enum_type_to_heksher(type_func):
    class A(Enum):
        a = 0
        b = 1
        c = 'c'
        d = 3.5

    t = setting_type(type_func(A))
    assert t.convert_to_heksher(A.a) == 0
    assert t.convert_to_heksher(A.c) == 'c'


@mark.parametrize('type_func', [lambda t: t, lambda t: HeksherFlags(t)])
def test_flag_type_from_heksher(type_func):
    class B(IntFlag):
        a = auto()
        b = auto()

    t = setting_type(type_func(B))

    assert t.heksher_string() == 'Flags["a","b"]'
    assert t.convert_from_heksher(["a", "c"]) == Conversion(B.a, [
        'server sent a flag value not found in the python type (c)'])
    assert t.convert_from_heksher([]) == Conversion(B(0), [])
    assert t.convert_from_heksher(["a", "b"]) == Conversion(B.a | B.b, [])


@mark.parametrize('type_func', [lambda t: t, lambda t: HeksherFlags(t)])
def test_flag_type_to_heksher(type_func):
    class B(IntFlag):
        a = auto()
        b = auto()

    t = setting_type(type_func(B))

    assert t.convert_to_heksher(B.b) == ["b"]
    assert t.convert_to_heksher(B.a | B.b) == ["a", "b"]


@mark.parametrize('type_func', [lambda t: Sequence[t], lambda t: HeksherSequence(HeksherEnum(t))])
def test_sequence_from_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.heksher_string() == 'Sequence<Enum["blue","green","red"]>'
    assert t.convert_from_heksher(["green", "red", "blue", "green"]) == Conversion(
        (Color.green, Color.red, Color.blue, Color.green), [])


@mark.parametrize('type_func', [lambda t: Sequence[t], lambda t: HeksherSequence(HeksherEnum(t))])
def test_sequence_to_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.convert_to_heksher((Color.green, Color.red, Color.blue, Color.green)) == ["green", "red", "blue", "green"]


@mark.parametrize('type_func', [lambda t: Sequence[t], lambda t: HeksherSequence(HeksherEnum(t))])
def test_sequence_coerce_from_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.heksher_string() == 'Sequence<Enum["blue","green","red"]>'
    assert t.convert_from_heksher(["green", "red", "blue", 'white', "green"]) == Conversion(
        (Color.green, Color.red, Color.blue, Color.green),
        ["failed to convert element 3: TypeError('value is not a valid enum member')"])


@mark.parametrize('type_func', [lambda t: Sequence[t], lambda t: HeksherSequence(HeksherEnum(t))])
def test_sequence_coerce_to_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.convert_to_heksher((Color.green, Color.red, Color.blue, Color.green)) == ["green", "red", "blue", "green"]


@mark.parametrize('type_func', [lambda t: Mapping[str, t], lambda t: HeksherMapping(HeksherEnum(t))])
def test_mapping_from_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.heksher_string() == 'Mapping<Enum["blue","green","red"]>'
    assert t.convert_from_heksher({'fg': 'blue', 'bg': 'red'}) == Conversion({'fg': Color.blue, 'bg': Color.red}, [])


@mark.parametrize('type_func', [lambda t: Mapping[str, t], lambda t: HeksherMapping(HeksherEnum(t))])
def test_mapping_to_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.convert_to_heksher({'fg': Color.blue, 'bg': Color.red}) == {'fg': 'blue', 'bg': 'red'}


@mark.parametrize('type_func', [lambda t: Mapping[str, t], lambda t: HeksherMapping(HeksherEnum(t))])
def test_mapping_coerce_from_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.heksher_string() == 'Mapping<Enum["blue","green","red"]>'
    assert t.convert_from_heksher({'fg': 'blue', 'bg': 'red', 'tx': 'white'}) == Conversion(
        {'fg': Color.blue, 'bg': Color.red}, [
            "failed to convert value for key tx: TypeError('value is not a valid enum member')"
        ])


@mark.parametrize('type_func', [lambda t: Mapping[str, t], lambda t: HeksherMapping(HeksherEnum(t))])
def test_mapping_coerce_to_heksher(type_func):
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(type_func(Color))
    assert t.convert_to_heksher({'fg': Color.blue, 'bg': Color.red}) == {'fg': 'blue', 'bg': 'red'}


def test_int_type_from_heksher():
    t = setting_type(int)
    assert t.heksher_string() == 'int'
    assert t.convert_from_heksher(1) == Conversion(1)
    with raises(TypeError):
        t.convert_from_heksher(1.5)
    with raises(TypeError):
        t.convert_from_heksher('1')


def test_int_type_to_heksher():
    t = setting_type(int)
    assert t.convert_to_heksher(1) == 1
