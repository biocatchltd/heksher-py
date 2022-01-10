Setting Types
===================

.. class:: SettingType(...)

    Abstract base class for all setting types.

    .. _coercions:

    .. note:: Coercions

        If the value received from the the server is of a type incompatible with the local declaration type, the
        setting may attempt to coerce the value to the local type instead of raising error. Each type may attempt
        to coerce the value in a different way. In all cases, if a coercion occurs, it will be logged. A setting may
        customize its coercion behavior by setting the :attr:`Setting.on_coerce` attribute.

.. function:: setting_type(arg)->SettingType

    Factory function for creating setting types. Arg can be one of following types:

    * A :class:`SettingType`, in which case it is returned as is.
    * A primitive type (str, int, float, bool), in which case a setting type for that primitive is returned.
    * An Enum class, IntFlag, or a generic type alias (see `Setting Types with Types and Generic Aliases`_).
      Discouraged.

.. class:: HeksherEnum(enum_type: typing.Type[enum.Enum])

    A setting type for Enum types.

    :param enum_type: The Enum type to use. All the type's members must be primitives.

.. class:: HeksherFlags(flags_type: typing.Type[enum.IntFlag])

    A setting type for IntFlag types.

    :param flags_type: The IntFlag type to use.

    .. note::

        The resulting heksher type will be a flag type whose options are the IntFlag's member names.

        .. code-block:: python

            class MyFlags(IntFlag):
                A = 1
                B = 2
                C = 4

            MyFlagsSetting = HeksherFlags(MyFlags)
            assert MyFlagsSetting.heksher_string == 'Flags["A","B","C"]'

    .. note:: coercions

        If any element of the flags value is not recognized by the IntFlag, that element will be ignored. For example,
        if the IntFlag has only two members, "green" and "blue", the server indicates value ["blue", "red"]. Heksher-py
        will coerce it to the value ["blue"].

.. class:: HeksherSequence(inner: SettingType[T])

    A setting type for sequences.

    :param inner: The type of each element in the sequence. Can also be an input to :func:`setting_type`.

    .. note:: coercions

        In addition to any coercions made by the inner type, if any element of the list fails conversion, only that
        element will be discarded.


.. class:: HeksherMapping(inner: SettingType[T])

    A setting type for maps.

    :param inner: The type of each value in the map. Can also be an input to :func:`setting_type`.

    .. note:: coercions

        In addition to any coercions made by the inner type, if any value of the dictionary fails conversion, only that
        key-value pair will be discarded.

Setting Types with Types and Generic Aliases
-----------------------------------------------------

In older versions, setting types would be created using types and generic aliases. This behaviour is now discouraged,
but still supported.

* an :class:`~enum.Enum` subclass for an Enum Heksher type.

  .. code-block::

    class Color(Enum):
        blue = "blue"
        green = "green"
        red = "red"

    assert setting_type(Color) == HeksherEnum(Color)

* an :class:`~enum.IntFlag` subclass for a Flags Heksher type.

  .. code-block::

    class AccessibilityFlags(IntFlag):
        color_blindness = auto()
        large_text = auto()
        text_to_speech = auto()


    assert setting_type(AccessibilityFlags) == HeksherFlags(AccessibilityFlags)

* a generic specialization of :class:`~collections.abc.Sequence` for a sequence Heksher type, with the
  inner argument as the generic type.

  .. code-block::

    assert setting_type(Sequence[int]) == HeksherSequence(int)

* a generic specialization of :class:`~collections.abc.Mapping` for a mapping Heksher type, with the
  value argument as the generic type. The key argument must be :class:`str`

  .. code-block::

    assert setting_type(Mapping[str, int]) == HeksherMapping(int)