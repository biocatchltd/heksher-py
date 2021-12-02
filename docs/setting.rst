:mod:`setting` --- Heksher Settings
=========================================================

.. module:: setting
    :synopsis: Heksher Settings.

-------

.. _Sequence: https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence

This module contains the `Setting` type, which is used to define a variable setting in Heksher. Settings are registered
to a global repository upon construction, and are declared and updated by the
:class:`Heksher Client <BaseHeksherClient>`.

.. warning::

    The settings are registered globally as :mod:`weak references <weakref>`, so they will not be updated or declared if the setting is
    destroyed. Therefore it is recommended to initialize settings as global variables.

    .. code-block::

        def foo():
            cache_ttl = heksher.Setting(name="cache_ttl", type=int,
                                        configurable_feature= ['environment', 'user'],
                                        default_value=60)

        foo()
        # the setting "cache_ttl" will not be declared

.. class:: Setting(name: str, type, configurable_features: collections.abc.Sequence[str], default_value = ..., metadata: collections.abc.Mapping[str, ...] = None, alias : str = None)

    A setting, that is declared to and updated from a Heksher service, by a Heksher client.

    :param name: The name of the setting.
    :param type: The type of the setting. Can be one of:

        * a primitive type (:class:`int`, :class:`float`, :class:`str` or :class:`bool`), for that primitive Heksher
          type.

          .. code-block::

            cache_size = Setting('cache_size', int)

        * an :class:`~enum.Enum` subclass for an Enum Heksher type. All the values of an enum must be Heksher
          primitives.

          .. code-block::

            class Color(Enum):
                blue = "blue"
                green = "green"
                red = "red"

            background_color = Setting('background_color', Color)
            # will declare a setting with type Enum["blue","green", "red"]

        * an :class:`~enum.IntFlag` subclass for a Flags Heksher type. All the values of the Flags will be by the class
          **member name**.

          .. code-block::

            class AccessibilityFlags(IntFlag):
                color_blindness = auto()
                large_text = auto()
                text_to_speech = auto()


            accessibility = Setting('accessibility', AccessibilityFlags)
            # will declare a setting with type Flags["color_blindness","large_text",
                                                     "text_to_speech"]

        * a generic specialization of :class:`~collections.abc.Sequence` for a sequence Heksher type, with the
          inner argument as the generic type.

          .. code-block::

            field_names = Setting('field_names', Sequence[str])
            # will declare a setting with type Sequence<str>

        * a generic specialization of :class:`~collections.abc.Mapping` for a mapping Heksher type, with the
          value argument as the generic type. The key argument must be :class:`str`

          .. code-block::

            item_costs = Setting('item_costs', Mapping[str, int])
            # will declare a setting with type Mapping<int>

    :param configurable_features: A sequence of context feature names, will decide which features the setting is
        configurable by.
    :param default_value: If specified, and no matching rule is found for the context, this value will be returned
        instead. If unspecified, a :exc:`NoMatchError` will be raised in that case.
    :param metadata: additional metadata to use when declaring the setting.
    :param  alias: An alias for the setting, see :ref:`renaming a setting`.

    .. method:: add_validator(validator: collections.abc.Callable)

        Adds a validator to be called the setting's rules are updated.

        :param validator: A callable that processes a rule and returns its new value. The callable should accept 3
            positional arguments: The rule's value, the rule's exact-match context variables, and the setting object
            itself.

        .. code-block::

            fields_to_use = Setting('fields_to_use', str, default_value = None)

            def compile_value(value: str, *args):
                return re.compile('^' + value + '$')

            fields_to_use.add_validator(compile_value)

            compiled: Optional[Pattern[str]] = fields_to_use.get()

        Default values are unaffected by validators. If multiple validators are added, they are called in the order they
        are added.

        Returns the validator itself, to be used like a decorator.

        .. warning::
            The validators **must** return an immutable value. Validators may assume that the rule value is immutable.

    .. method:: get(**contexts: str) -> value

        Get the value of the setting for a set of context features.

        :param \*\*contexts: the context values of the current context, any configurable context feature specified in
            the constructor must be either specified here, or provided by the client a as default (see
            :meth:`AsyncHeksherClient.set_defaults` and :meth:`ThreadHeksherClient.set_defaults`).

        Returns the value of the highest-priority rule to match the context, or the setting's default value if not
        rules matched.

        :raises NoMatchError: if no rules matched and no default value was specified.