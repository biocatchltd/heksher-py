Heksher-py Cookbook
---------------------------------

.. _renaming a setting:

Renaming a setting
====================

Say you have a setting called ``foo``

.. code-block:: python

    foo = Setting('foo', int, ...)

And you want to change the name of the setting to ``bar``. If you were to simply change the name of the setting, you
will run into the problem of essentially having declared a new setting. This means that all the rules defined in heksher
for ``foo`` will not transfer over to ``bar``.

To fix this, we'll use the "alias" parameter when declaring the setting.

.. code-block:: python

    bar = Setting('bar', int, ..., alias='foo')

This will inform the heksher service that the setting known as ``foo`` should be renamed to bar, along with all the
rules associated with it. As an added bonus, any app that uses the older name will not break, as they will be able to
access ``bar`` via its alias (and old name) ``foo``.

Offline Settings
====================

Sometimes we may want to have the Heksher client retrieve the rules from an online heksher service, but we
want to keep the option to override it. We can do this easily with a stub client.

For this example, we'll create the option to override the heksher values with a local file located at
``/etc/heksher.json``, where the decoded file will be a dictionary that maps setting names to their values.

.. code-block:: python
    :emphasize-lines: 11, 16, 18, 20-22

    import json
    from pathlib import Path
    from heksher import ThreadHeksherClient, Setting
    from heksher.clients.stub import SyncStubHeksherClient

    cache_size = Setting('cache_size', int, ...)
    cache_ttl = Setting('cache_ttl', int, ...)
    timeout = Setting('timeout', float, ...)

    class App:
        heksher_client: Union[ThreadHeksherClient, SyncStubHeksherClient]

        ...

        def startup(self):
            options_file = Path('/etc/heksher.json')
            if options_file.is_file():
                self.heksher_client = SyncStubHeksherClient()
                options = json.loads(options_file.read_text())
                self.heksher_client.patch(cache_size, options['cache_size'])
                self.heksher_client.patch(cache_ttl, options['cache_ttl'])
                self.heksher_client.patch(timeout, options['timeout'])
                # note that we don't need to enter the patch contexts here, since we never intend to
                # undo the patch
            else:
                self.heksher_client = ThreadHeksherClient(...)

            self.heksher_client.set_as_main()

        ...
