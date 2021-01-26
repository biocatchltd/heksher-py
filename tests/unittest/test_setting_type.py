from enum import Enum, IntFlag, auto
from typing import Sequence, Mapping

from pytest import raises

from heksher.setting_type import setting_type, SettingType


def test_enum_type():
    class A(Enum):
        a = 0
        b = 1
        c = 'c'
        d = 3.5

    t = setting_type(A)
    assert t.heksher_string() == 'Enum["c",0,1,3.5]'
    assert t.convert(0) == A.a
    assert t.convert("c") == A.c
    with raises(ValueError):
        assert t.convert("b")


def test_flag_type():
    class B(IntFlag):
        a = auto()
        b = auto()

    t = setting_type(B)

    assert t.heksher_string() == 'Flags["a","b"]'
    assert t.convert(["a", "c"]) == B.a
    assert t.convert([]) == B(0)
    assert t.convert(["a", "b"]) == B.a | B.b


def test_sequence():
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(Sequence[Color])
    assert t.heksher_string() == 'Sequence<Enum["blue","green","red"]>'
    assert t.convert(["green", "red", "blue", "green"]) == [Color.green, Color.red, Color.blue, Color.green]


def test_mapping():
    class Color(Enum):
        red = 'red'
        blue = 'blue'
        green = 'green'

    t = setting_type(Mapping[str, Color])
    assert t.heksher_string() == 'Mapping<Enum["blue","green","red"]>'
    assert t.convert({'fg': 'blue', 'bg': 'red'}) == {'fg': Color.blue, 'bg': Color.red}
