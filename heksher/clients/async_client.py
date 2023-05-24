from __future__ import annotations

from asyncio import (
    FIRST_COMPLETED, CancelledError, Event, Future, Lock, Queue, Task, TimeoutError, create_task, get_running_loop,
    wait, wait_for
)
from contextvars import ContextVar
from logging import getLogger
from typing import Any, Awaitable, Dict, NoReturn, Optional, Sequence, TypeVar, Union

import orjson
from httpx import AsyncClient, HTTPError, HTTPStatusError

from heksher.clients.subclasses import AsyncContextManagerMixin, ContextFeaturesMixin, V1APIClient
from heksher.clients.util import SettingsOutput
from heksher.setting import Setting

logger = getLogger(__name__)

T = TypeVar('T')
content_header = {"Content-type": "application/json"}

__all__ = ['AsyncHeksherClient']


class AsyncHeksherClient(V1APIClient, ContextFeaturesMixin, AsyncContextManagerMixin):
    """
    An asynchronous heksher client, using heksher's V1 HTTP API
    """

    def __init__(self, service_url: str, update_interval: float, context_features: Sequence[str], *,
                 http_client_args: Dict[str, Any] = None):
        """
        Args:
            service_url: The HTTP url to the Heksher server.
            update_interval: The interval to wait between any two regular update calls, in seconds.
            context_features: The context features to expect in the Heksher server.
            http_client_args: Forwarded as kwargs to httpx.AsyncClient constructor.
        """
        super().__init__(context_features)

        http_client_args = http_client_args or {}

        self._service_url = service_url
        self._update_interval = update_interval
        self._http_client = AsyncClient(base_url=service_url, **http_client_args)
        self._undeclared: Queue[Setting] = Queue()

        self._declaration_task: Optional[Task[NoReturn]] = None
        self._update_task: Optional[Task[NoReturn]] = None

        self.modification_lock = Lock()
        """
        A lock that is acquired whenever setting values are updated. To ensure that no modifications are made to
        settings, acquire this lock.
        """

        self._update_event = Event()
        """This event marks that an update occurred"""
        self._manual_update = Event()
        """This event is waited on by the update loop (with a timeout), set it to instantly begin an update"""
        self._declaration_error: Optional[Future[NoReturn]] = None
        """This future will throw an exception if a declaration fails"""
        self._update_error: Optional[Future[NoReturn]] = None
        """This future will throw an exception if an update fails"""

    async def _declaration_loop(self) -> NoReturn:
        """
        The method for the task that continuously declares new settings.
        """

        async def declare_setting(setting):
            response = await self._http_client.post('api/v1/settings/declare',
                                                    content=orjson.dumps(setting.to_v1_declaration_body()),
                                                    headers=content_header)
            self._handle_declaration_response(setting, response)

        while True:
            setting = None
            try:
                setting = await self._undeclared.get()
                await declare_setting(setting)
            except CancelledError:
                # in 3.7, cancelled is a normal exception
                raise
            except Exception as e:
                logger.exception('setting declaration failed', extra={'setting': setting and setting.name})
                if self._declaration_error is not None:
                    self._declaration_error.set_exception(e)
            finally:
                if setting:
                    self._undeclared.task_done()

    async def _update_loop(self) -> NoReturn:
        """
        The method for the task that continuously updates declared settings.
        """
        etag = ''

        async def update():
            nonlocal etag

            logger.debug('heksher reload started')

            response = await self._http_client.get('/api/v1/query', params={
                'settings': ','.join(sorted(self._tracked_settings.keys())),
                'context_filters': self._context_filters(),
                'include_metadata': False,
            }, headers={
                **content_header,
                'If-None-Match': etag,
            })

            if response.status_code == 304:
                logger.debug('heksher reload not necessary')
                return
            response.raise_for_status()
            etag = response.headers.get('ETag', '')

            updated_settings = response.json()['settings']
            async with self.modification_lock:
                self._update_settings_from_query(updated_settings)
            logger.info('heksher reload done')

        while True:
            try:
                await update()
            except CancelledError:
                # in 3.7, cancelled is a normal exception
                raise
            except Exception as e:
                log_extras = {}
                if isinstance(e, HTTPStatusError):
                    log_extras['response_content'] = e.response.content
                logger.exception('error during heksher update', extra=log_extras)
                if self._update_error is not None:
                    self._update_error.set_exception(e)
                self.on_update_error(e)
            finally:
                self._update_event.set()
                self.on_update_ok()

            try:
                self._manual_update.clear()
                # we only want to pass immediately if the event was passed while we are waiting
                await wait_for(self._manual_update.wait(), self._update_interval)
            except TimeoutError:
                pass

    async def _wait_for_declaration_error(self) -> NoReturn:
        """
        Waits for the declaration error to occur.
        """
        if self._declaration_error is not None:
            await self._declaration_error
        self._declaration_error = get_running_loop().create_future()
        try:
            await self._declaration_error
        except CancelledError:
            self._declaration_error = None
            raise

    async def _wait_for_update_error(self) -> NoReturn:
        """
        Waits for the declaration error to occur.
        """
        if self._update_error is not None:
            await self._update_error
        self._update_error = get_running_loop().create_future()
        try:
            await self._update_error
        except CancelledError:
            self._update_error = None
            raise

    async def set_as_main(self):
        await super().set_as_main()

        # check that we're dealing with the right context features
        try:
            response = await self._http_client.get('/api/v1/context_features')
            response.raise_for_status()
        except HTTPError:
            logger.exception('failure to get context_features from heksher service',
                             extra={'service_url': self._service_url})
        else:
            features_in_service = response.json()['context_features']
            if features_in_service != self._context_features:
                logger.warning('context feature mismatch', extra={
                    'features_in_service': features_in_service,
                    'features_in_client': self._context_features
                })

        try:
            self._declaration_task = create_task(self._declaration_loop())
            undeclared_task = create_task(self._undeclared.join())
            wait_for_update_error_task = create_task(self._wait_for_update_error())
            await wait_with_err_sentinel(undeclared_task, wait_for_update_error_task)
            # important to only start the update thread once all pending settings are declared, otherwise we may have
            # stale settings
            self._update_task = create_task(self._update_loop())
            await self.reload()
        except Exception:
            await self.aclose()
            raise

    async def reload(self):
        """
        Block until all the tracked settings are up to date
        """
        await self._undeclared.join()
        self._update_event.clear()
        self._manual_update.set()
        update_event_task = create_task(self._update_event.wait())
        wait_for_update_error_task = create_task(self._wait_for_update_error())
        await wait_with_err_sentinel(update_event_task, wait_for_update_error_task)

    async def aclose(self):
        await super().aclose()
        if self._update_task:
            self._update_task.cancel()
            try:
                await wait_for(self._update_task, 0.01)
            except CancelledError:
                pass
            self._update_task = None
        if self._declaration_task:
            self._declaration_task.cancel()
            try:
                await wait_for(self._declaration_task, 0.01)
            except CancelledError:
                pass
            self._declaration_task = None
        await self._http_client.aclose()

    def set_defaults(self, **kwargs: Union[str, ContextVar[str]]):
        redundant_keys = kwargs.keys() - set(self._context_features)
        if redundant_keys:
            logger.warning('context features are not specified in the client', extra={
                'redundant_keys': redundant_keys
            })
        super().set_defaults(**kwargs)

    async def ping(self) -> None:
        """
        Check the health of the heksher server
        Raises:
            httpx.HTTPError, if an error occurs
        """
        response = await self._http_client.get('/api/health')
        response.raise_for_status()

    async def get_settings(self) -> Dict:
        """
        List all the settings in the service
        """
        response = await self._http_client.get('/api/v1/settings', params={'include_additional_data': 'True'})
        response.raise_for_status()
        settings = SettingsOutput.parse_obj(response.json()).to_settings_data()
        return settings

    def on_update_error(self, exc):
        # override this method to handle update errors
        pass

    def on_update_ok(self):
        # override this method to handle update success
        pass


async def wait_with_err_sentinel(coro: Awaitable, err_future: Awaitable[NoReturn]):
    done, pending = await wait((coro, err_future), return_when=FIRST_COMPLETED)
    for future in pending:
        future.cancel()
        try:
            await wait_for(future, 0.01)
        except CancelledError:
            pass
    for future in done:
        await future
