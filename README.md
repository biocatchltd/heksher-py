# heksher SDK for python
This is a library for using a [heksher](https://github.com/biocatchltd/Heksher) server from within python.
Compatible with python 3.7, 3.8, and 3.9. The library contains both an asynchronous client, as well as a thread-based
client. Also included are stub clients to make testing without a service simple.

## Example usage
```python
# main.py
from contextvars import ContextVar
from heksher import AsyncHeksherClient, Setting

user = ContextVar('user', default='guest')

class App:
    ...
    
    async def startup(self):
        ...
        
        # initialize the client, and set it as the process' main client
        self.heksher_client = AsyncHeksherClient('http://heksher.service.url',
                                            update_interval=60, 
                                            context_features=['user', 'trust', 'theme'])
        # set certain context features to be retrieved either from string constants or
        # context variables 
        self.heksher_client.set_defaults(user = user, theme="light")
        await self.heksher_client.set_as_main()
    
    async def shutdown(self):
        await self.heksher_client.close()        
        ...

cache_size_setting = Setting('cache_size', type=int, configurable_features=['user', 'trust'], default_value=10)
def foo(trust: str):
    ...
    # should be run after App.startup is completed
    cache_size = cache_size_setting.get(trust=trust)
    ...
```
Thread-based client usage is nearly identical. 