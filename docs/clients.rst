Clients- Heksher clients
-------------------------

.. class:: AsyncHeksherClient(service_url: str, update_interval: int,\
            context_features: collections.abc.Sequence[str], *, http_client_args: dict[str, ...] = None)

    An asyncrhonous client for Heksher. Updates and declares settings in the background using asyncio tasks.

    :param service_url: The URL of the Heksher service.
    :param update_interval: The interval in seconds between updates.
    :param context_features: The context features to check for existence.
    :param http_client_args: Additional keyword arguments to pass to the underlying
        `async HTTPX client <https://www.python-httpx.org/async/>`_.


    .. method:: set_as_main()
        :async:

        Sets the client as the main client for heksher. Will wait until all currently defined settings are declared, and
        then will wait for an initial update.

        If the client is used as an async context manager, this method will be called on entry.

        If an error occurs during the declarations or the initial update, the exception will be raised.

        .. warning::
            If an error occurs in the update or declarations loops after the method returned, the exception will not be
            raised, instead the exception will be logged.

        .. code-block:: python

            async with AsyncHeksherClient(...) as client:
                ...

    .. method:: aclose()
        :async:

        Closes the client. This will cancel all pending tasks.

        If the client is used as an async context manager, this method will be called on exit.

    .. method:: close()
        :async:

        .. deprecated:: 0.2.0
            Use :meth:`aclose` instead.

        Legacy alias for :meth:`aclose`.

    .. method:: reload()
        :async:

        Updates all setting rules. This occurs automatically every ``update_interval`` seconds after :meth:`set_as_main`
        is called, but calling this method will perform a manual reload. Will also reset the update timer.

        If an error occurs during the update, the exception will be raised.

    .. attribute:: modification_lock
        :type: asyncio.Lock

        A lock that can be used to prevent concurrent modification of setting values. To ensure that no modifications
        are made to settings, acquire this lock.

        .. warning::

            Acquiring this lock will block any modification of setting values, including from the context that acquired
            it. meaning that the following snippet will deadlock:

            .. code-block:: python

                async with client.modification_lock:
                    await client.reload()

    .. method:: set_defaults(**kwargs: str | contextvars.ContextVar[str])

        Sets the default context feature values. The keys of *\*\*kwargs* should be context feature names. The values
        can be either an :class:`str`, in which case default value for the context feature will be the string.
        Alternatively, the default value may be a context variable, in which case the value will be fetched dynamically.

    .. method:: ping()->None
        :async:

        Pings the Heksher service.

        :raises: ``httpx.HTTPError`` if the ping fails.

    .. method:: get_settings()->Dict[str, ...]
        :async:

        Queries the Heksher service for all the settings declared on it (not just by this client).
        Returns a dict that maps setting names to their data. Setting data has the following attributes:

        * ``name`` (:class:`str`): The name of the setting.
        * ``configurable_features`` (:class:`list`\[:class:`str`\]): The context features configurable for this setting.
        * ``type`` (:class:`str`): The type of the setting by Heksher specs.
        * ``default_value`` (Any): The default value of the setting.
        * ``metadata`` (:class:`dict`\[:class:`str`, Any\]): The metadata of the setting.
        * ``aliases`` (:class:`list`\[:class:`str`\]): The aliases of the setting.
        * ``version`` (:class:`str`): The version of the setting's latest declaration.


    .. method:: track_contexts(**context_values: str | collections.abc.Collection[str])

        Tracks specific context feature values. When rules are queried from heksher, only rules that fully match all the
        tracked context features will be returned.

        The keys of *\*\*context_values* should be context feature names.
        The values can be either a single string, in which case the context feature will be tracked with the value only,
        or the value may be a collection of strings, in which case the context feature will be tracked with all of the
        strings as its value. Alternatively, a value may be the constant :data:`TRACK_ALL`, in which case all values of
        the context feature will be tracked.

    .. method:: on_update_error(exc: Exception)->None

        Called when an error occurs during a rule update. Override this method to add special error
        handling.

        :param exc: The exception that occurred.


    .. method:: on_update_ok()->None

        Called when a rule update completed successfully (including when no change is necessary).
        Override this method to add a callback on successful updates.


.. class:: ThreadHeksherClient(service_url: str, update_interval: int,\
            context_features: collections.abc.Sequence[str], *, http_client_args: dict[str, ...] = None)

    A synchronous client for Heksher. Updates and declares settings in the background using a separate thread.

    .. warning::
        Since the declarations and updates are performed in a separate thread, any errors that occur during these
        operations will not be raised. Instead, the error will be logged.

    :param service_url: The URL of the Heksher service.
    :param update_interval: The interval in seconds between updates.
    :param context_features: The context features to check for existence.
    :param http_client_args: Additional keyword arguments to pass to the underlying
        `HTTPX client <https://www.python-httpx.org/advanced/#client-instances>`_.

    .. method:: set_as_main()

        Sets the client as the main client for heksher. Will wait until all currently defined settings are declared, and
        then will wait for an initial update.

        If the client is used as a context manager, this method will be called on entry.

        .. code-block:: python

            with ThreadHeksherClient(...) as client:
                ...

    .. method:: close()

        Closes the client. This will close the background thread.

        If the client is used as a context manager, this method will be called on exit.

    .. method:: reload()

        Updates all setting rules. This occurs automatically every ``update_interval`` seconds after :meth:`set_as_main`
        is called, but calling this method will perform a manual reload. Will also reset the update timer.

    .. attribute:: modification_lock
        :type: threading.Lock

        A lock that can be used to prevent concurrent modification of setting values. To ensure that no modifications
        are made to settings, acquire this lock.

        .. warning::

            Acquiring this lock will block any modification of setting values, including from the context that acquired
            it. meaning that the following snippet will deadlock:

            .. code-block:: python

                with client.modification_lock:
                    client.reload()

    .. method:: set_defaults(**kwargs: str | contextvars.ContextVar[str])

        Sets the default context feature values. The keys of *\*\*kwargs* should be context feature names. The values
        can be either an :class:`str`, in which case default value for the context feature will be the string.
        Alternatively, the default value may be a context variable, in which case the value will be fetched dynamically.

    .. method:: ping()->None

        Pings the Heksher service.

        :raises: ``httpx.HTTPError`` if the ping fails.

    .. method:: get_settings()->Dict[str, ...]

        Queries the Heksher service for all the settings declared on it (not just by this client).
        Returns a dict that maps setting names to their data. Setting data has the following attributes:

        * ``name`` (:class:`str`): The name of the setting.
        * ``configurable_features`` (:class:`list`\[:class:`str`\]): The context features configurable for this setting.
        * ``type`` (:class:`str`): The type of the setting by Heksher specs.
        * ``default_value`` (Any): The default value of the setting.
        * ``metadata`` (:class:`dict`\[:class:`str`, Any\]): The metadata of the setting.
        * ``aliases`` (:class:`list`\[:class:`str`\]): The aliases of the setting.
        * ``version`` (:class:`str`): The version of the setting's latest declaration.


    .. method:: track_contexts(**context_values: str | collections.abc.Collection[str])

        Tracks specific context feature values. When rules are queried from heksher, only rules that fully match all the
        tracked context features will be returned.

        The keys of *\*\*context_values* should be context feature names.
        The values can be either a single string, in which case the context feature will be tracked with the value only,
        or the value may be a collection of strings, in which case the context feature will be tracked with all of the
        strings as its value. Alternatively, a value may be the constant :data:`TRACK_ALL`, in which case all values of
        the context feature will be tracked.

    .. method:: on_update_error(exc: Exception)->None

        Called when an error occurs during a rule update. Override this method to add special error
        handling.

        :param exc: The exception that occurred.


    .. method:: on_update_ok()->None

        Called when a rule update completed successfully (including when no change is necessary).
        Override this method to add a callback on successful updates.
