Clients- Heksher clients
-------------------------

.. class:: AsyncHeksherClient(service_url: str, update_interval: int,\
            context_features: collections.abc.Sequence[str], *, http_client_args: dict[str, ...] = None)

    An asyncrhonous client for Heksher. Updates and declares settings in the background using asyncio tasks.

    :param service_url: The URL of the Heksher service.
    :param update_interval: The interval in seconds between updates.
    :param context_features: The context features to check for existance.
    :param http_client_args: Additional keyword arguments to pass to the underlying
        `HTTPX client <https://www.python-httpx.org/async/>`_.

    .. method:: set_as_main()
        :async:

        Sets the client as the main client for heksher. Will wait until all currently defined settings are declared, and
        then will wait for an initial update.

        If the client is used as an async context manager, this method will be called on entry.

        .. code-block:: python

            async with AsyncHeksherClient(...) as client:
                ...

    .. method:: close()
        :async:

        Closes the client. This will cancel all pending tasks.

        If the client is used as an async context manager, this method will be called on exit.

    .. method:: reload()
        :async:

        Updates all setting rules. This occurs automatically every ``update_interval`` seconds after :meth:`set_as_main`
        is called, but callign this method will perform a manual reload. Will also reset the update timer.

    .. method:: set_defaults(**kwargs: str | contextvars.ContextVar[str])

        Sets the default context feature values. The keys of *\*\*kwargs* should be context feature names. The values
        can be either an :class:`str`, in which case default value for the context feature will be the string.
        Alternatively, the default value may be a context variable, in which case the value will be fetched dynamically.

    .. method:: ping()->None
        :async:

        Pings the Heksher service.

    .. method:: get_settings()->Dict[str, ...]
        :async:

        Queries the Heksher service for all the settings declared on it (not just by this client).
        Returns a dict that maps setting names to their data. Setting data has the following attributes:

        * ``name`` (:class:`str`): The name of the setting.
        * ``configurable_features`` (:class:`list`\[:class:`str`\]): The context features configurable for this setting.
        * ``type`` (:class:`str`): The type of the setting by Heksher specs.
        * ``default_value`` (Any): The default value of the setting.
        * ``metadata`` (:class:`dict`\[:class:`str`, Any\]): The metadata of the setting.


    .. method:: track_contexts(**context_values: str | collections.abc.Collection[str])

        Tracks specific context feature values. When rules are queried from heksher, only rules that fully match all the
        tracked context features will be returned.

        The keys of *\*\*context_values* should be context feature names.
        The values can be either a single string, in which case the context feature will be tracked with the value only,
        or the value may be a collection of strings, in which case the context feature will be tracked with all of the
        strings as its value. Alternatively, a value may be the constant :data:`TRACK_ALL`, in which case all values of
        the context feature will be tracked.
