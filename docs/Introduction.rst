Introduction
========================

Heksher-py is a python library to interface with the `Heksher service <https://github.com/biocatchltd/Heksher>`_ through
its HTTP API. heksher-py supports both asynchronous and synchronous clients that update in the background.

.. code-block::
    :caption: example async usage
    :emphasize-lines: 9-13, 23-28, 30, 33, 36-39, 44, 51, 56, 60

    import asyncio
    import os
    import heksher
    import contextvars

    # in this example, we start up a service with two settings: a cache ttl, and a background color
    # we have 3 context features in all: environment, user, and theme

    cache_ttl = heksher.Setting(name="cache_ttl", type=int,
                                configurable_feature=['environment', 'user'], default_value=60)
    background_color = heksher.Setting(name="background_color", type=str,
                                       configurable_feature=['environment', 'theme'],
                                       default_value="white")

    theme_cv = contextvars.ContextVar('theme')
    # it is the app's responsibility to set this context variable

    class App:
        heksher_client: heksher.AsyncHeksherClient

        async def startup(self):
            ...
            self.heksher_client = heksher.AsyncHeksherClient(
                service_url = ...,
                update_interval = 300,  # update all settings every 5 minutes
                context_features = ['environment', 'user', 'theme'],
                http_client_args = {'headers': {'api_token': ...}},
            )
            environment : str = os.getenv('ENVIRONMENT', 'dev')
            self.heksher_client.set_defaults(environment=environment)
            # unless explicitly stated, we now fetch all our setting values as the environment
            # specified
            self.heksher_client.set_defaults(theme=theme_cv)
            # unless explicitly stated, we now fetch all our setting values as the theme specified
            # in the contextvar
            self.heksher_client.track_contexts(
                                environment=environment, user=heksher.TRACK_ALL,
                                theme=['bright', 'dark', 'blue']
            )
            # we have now configured our client to only track the environments we got from our own
            # env, only the themes "dark", "bright", and "blue", and to track all users, we will not
            # read any rules but those.

            await self.heksher_client.set_as_main()
            # will declare all settings configured in the service, and begin to update them in the
            # background every 5 minutes
            ...

        async def shutdown(self):
            ...
            await self.heksher_client.aclose() # will stop the background update task
            ...

        def get_cache_ttl(self, user):
            # no need to specify environment, since we set it's default at startup
            return cache_ttl.get(user=user)

        def get_background_color(self):
            # no need to specify environment or theme, since we set their default at startup
            return background_color.get()

