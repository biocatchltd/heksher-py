Stub Clients- Stub Heksher clients for testing and mocking
----------------------------------------------------------------

In order to unit test code that relies on Heksher settings, we can use these helper stub clients to mock whatever
setting configuration we desire.

.. code-block::
    :caption: Code we want to test

    from heksher.settings import Setting

    background_color = Setting('background_color', str, default_value='blue',
                                configurable_features=['theme'])

    def foreground_color(theme: str):
        """
        Return a color that is inverse to the current background color
        """
        back_rgb = color_name_to_rgb(background_color.get(theme=theme))
        fore_rgb = (255 - back_rgb[0], 255 - back_rgb[1], 255 - back_rgb[2])
        return color_rgb_to_name(fore_rgb)

.. code-block::
    :caption: How to test the above code in pytest with a stub client
    :emphasize-lines: 7, 11, 15-18

    from pytest import fixture
    from heksher.clients.stub import SyncStubClient, Rule
    from my_module import background_color, foreground_color

    @fixture
    def stub_client():
        with SyncStubClient() as stub_client:
            yield stub_client

    def test_foreground_color(stub_client):
        with stub_client.patch(background_color, 'red'):
            assert foreground_color("any_theme") == 'cyan'

    def test_foreground_color_by_theme(stub_client):
        with stub_client.patch(background_color, [
                Rule({'theme': 'dark'}, 'black'),
                Rule({'theme': 'light'}, 'white'),
            ]):
            assert foreground_color("dark") == 'white'
            assert foreground_color("white") == 'black'
            assert foreground_color("dracula") == 'yellow'  # default is still blue

.. module:: clients.stub

.. class:: SyncStubHeksherClient(*args, **kwargs)

    A stub client that can be used to mock a synchronous Heksher client. All arguments are ignored.

    This class can be used as a context manager. Entering and exiting it does nothing.

    .. method:: patch(setting : setting.Setting, value: T | collections.abc.Collection[Rule[T]])

        Patch the given setting with the given value.

        :param setting: The setting to patch
        :param value: The value to patch it with, or a collection of rules to patch it with. If rules are given, they
            must all address exactly the same context features in exactly the same order.
        :return: A context manager that will restore the setting to its original value when exiting

    .. attribute:: reload

        A :class:`~unittest.mock.MagicMock` object that mocks the :meth:`~ThreadHeksherClient.reload` method.

    .. attribute:: close

        A :class:`~unittest.mock.MagicMock` object that mocks the :meth:`~ThreadHeksherClient.close` method.

    .. attribute:: ping

        A :class:`~unittest.mock.MagicMock` object that mocks the :meth:`~ThreadHeksherClient.ping` method.

.. class:: AsyncStubHeksherClient(*args, **kwargs)

    An async stub client that can be used to mock an async Heksher client. All arguments are ignored.

    This class can be used as an async context manager. Entering and exiting it does nothing.

    .. method:: patch(setting : setting.Setting, value: T | collections.abc.Collection[Rule[T]])

        Patch the given setting with the given value.

        :param setting: The setting to patch
        :param value: The value to patch it with, or a collection of rules to patch it with. If rules are given, they
            must all address exactly the same context features in exactly the same order.
        :return: A context manager that will restore the setting to its original value when exiting

    .. attribute:: reload

        A :class:`~unittest.mock.AsyncMock` object that mocks the :meth:`~AsyncHeksherClient.reload` method.

    .. attribute:: close

        A :class:`~unittest.mock.AsyncMock` object that mocks the :meth:`~AsyncHeksherClient.close` method.

    .. attribute:: ping

        A :class:`~unittest.mock.AsyncMock` object that mocks the :meth:`~AsyncHeksherClient.ping` method.

.. class:: Rule(match_conditions: collections.abc.Mapping[str, str | None], value: T)

    A rule used to patch a setting's value depending on context features.

    This class is a dataclass.

    :param match_conditions: A mapping of context feature names to their exact-match conditions.

        .. note::

            In sub clients, when multiple rules are given, they must have the exact same keys, in exactly the same
            order. These keys will be interpreted as the setting's context features.

    :param value: The value to patch the setting with when the conditions are met.

