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

.. class:: Setting(name: str, type: SettingType[T] | Type[int] | Type[float] | Type[bool] | Type[str], \
            configurable_features: collections.abc.Sequence[str], \
            default_value: T, metadata: collections.abc.Mapping[str, ...] = None, alias : str = None, \
            version: str = '1.0', on_coerce: Optional[Callable[...]] = ...)

    A setting, that is declared to and updated from a Heksher service, by a Heksher client.

    :param name: The name of the setting.
    :param type: The type of the setting. Must be a subclass of :class:`SettingType`, or a valid input to
        :func:`setting_type`.
    :param configurable_features: A sequence of context feature names, will decide which features the setting is
        configurable by.
    :param default_value: If specified, and no matching rule is found for the context, this value will be returned
        instead.
    :param metadata: additional metadata to use when declaring the setting.
    :param alias: An alias for the setting, see :ref:`renaming a setting`.
    :param version: The version of the setting declaration.
    :param on_coerce: A callable that will be called when a value for the setting has undergone coercion.
        The callable should accept 5 positional parameters: the coerced value, the original raw value, a sequence of
        strings representing the coercions that were applied, the rule object that the value came from (or ``None`` if
        value is supposed to be the default value), and the setting itself. The callable should return a value for the
        rule or default value. The callable may raise a :exc:`TypeError` to reject the value. Setting ``on_coerce`` to
        ``None`` will raise a :exc:`TypeError` on all coercions. Default value is to return the coerced value.

    .. method:: add_validator(validator: collections.abc.Callable)

        Adds a validator to be called when the setting's rules are updated.

        :param validator: A callable that processes a rule or server default and returns its new value. The callable
            should accept 3 positional arguments: The rule's value, the rule object (or noe for server defaults), and
            the setting object itself. Validators may raise a :exc:`TypeError` to reject the value.

        .. code-block::

            fields_to_use = Setting('fields_to_use', str, default_value = None)

            def compile_value(value: str, *args):
                return re.compile('^' + value + '$')

            fields_to_use.add_validator(compile_value)

            compiled: Optional[Pattern[str]] = fields_to_use.get()

        Local default values are unaffected by validators. If multiple validators are added, they are called in the
        order they are added.

        Returns the validator itself, to be used like a decorator.

        .. warning::
            The validators **must** return an immutable value. Validators may assume that the input is immutable.

    .. method:: get(**contexts: str) -> value

        Get the value of the setting for a set of context features.

        :param \*\*contexts: the context values of the current context, any configurable context feature specified in
            the constructor must be either specified here, or provided by the client a as default (see
            :meth:`AsyncHeksherClient.set_defaults` and :meth:`ThreadHeksherClient.set_defaults`).

        Returns the value of the highest-priority rule to match the context, or the setting's default value if not
        rules matched.

        :raises NoMatchError: if no rules matched and no default value was specified.