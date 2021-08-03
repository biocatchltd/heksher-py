from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
from logging import getLogger
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Dict, Optional, Sequence, TypeVar, Union

import orjson
from httpx import Client, HTTPError
from ordered_set import OrderedSet

from heksher.clients.subclasses import ContextFeaturesMixin, ContextManagerMixin, V1APIClient
from heksher.clients.util import SettingsOutput
from heksher.setting import MISSING, Setting

logger = getLogger(__name__)

T = TypeVar('T')
content_header = {"Content-type": "application/json"}

__all__ = ['ThreadHeksherClient']


class ThreadHeksherClient(V1APIClient, ContextFeaturesMixin, ContextManagerMixin):
    """
    A synchronous heksher client, using heksher's V1 HTTP API
    """
    declaration_loop_interval = 1
    """
    The timeout when waiting for new settings to declare. This is the maximum blocking time of the declare
     thread closing.
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

        self._service_url = service_url
        self._update_interval = update_interval
        self._http_client_args = http_client_args or {}
        self._undeclared: Queue[Setting] = Queue()

        self._declaration_thread: Optional[Thread] = None
        self._update_thread: Optional[Thread] = None

        self._last_cache_time: Optional[datetime] = None

        self.modification_lock = Lock()
        """
        A lock that is acquired whenever setting values are updated. To ensure that no modifications are made to
        settings, acquire this lock.
        """

        self._update_event = Event()
        """This event marks that an update occurred"""
        self._manual_update = Event()
        """This event is waited on by the update loop on a timeout, set it to true to instantly begin an update"""

        self._keep_going = True

    def _http_client(self):
        """
        Create an httpx client to interface with the service.
        Notes:
            httpx clients are not thread-safe
        """
        return Client(base_url=self._service_url, **self._http_client_args)

    def _declare_loop(self):
        """
        thread target to continuously declare new settings.
        """
        http_client = self._http_client()

        def declare_setting(setting):
            declaration_data = {
                'name': setting.name,
                'configurable_features': list(setting.configurable_features),
                'type': setting.type.heksher_string(),
                'metadata': setting.metadata,
            }
            if setting.default_value is not MISSING:
                declaration_data['default_value'] = setting.default_value
            response = http_client.put('api/v1/settings/declare', content=orjson.dumps(declaration_data),
                                       headers=content_header)
            self._handle_declaration_response(setting, response)

        while self._keep_going:
            try:
                setting = self._undeclared.get(timeout=self.declaration_loop_interval)
            except Empty:
                continue

            try:
                declare_setting(setting)
            except Exception:
                logger.exception('declaration failed', extra={'setting': setting.name})
            finally:
                self._undeclared.task_done()

    def _update_loop(self):
        """
        Thread target to continuously update declared settings.
        """

        http_client = self._http_client()

        def update():
            logger.debug('heksher reload started')
            data = {
                'setting_names': list(self._tracked_settings.keys()),
                'context_features_options': self._context_feature_options(),
                'include_metadata': False,
            }
            if self._last_cache_time:
                data['cache_time'] = self._last_cache_time.isoformat()
            new_cache_time = datetime.utcnow()

            response = http_client.post('/api/v1/rules/query', content=orjson.dumps(data),
                                        headers=content_header)
            response.raise_for_status()

            updated_settings = response.json()['rules']
            with self.modification_lock:
                self._update_settings_from_query(updated_settings)
            self._last_cache_time = new_cache_time
            logger.info('heksher reload done', extra={'updated_settings': updated_settings.keys()})

        while self._keep_going:
            try:
                update()
            except Exception:
                logger.exception('error during heksher update')
            finally:
                self._update_event.set()

            self._manual_update.clear()
            self._manual_update.wait(self._update_interval)

    def set_as_main(self):
        super().set_as_main()

        # check that we're dealing with the right context features
        try:
            response = self._http_client().get('/api/v1/context_features')
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
                # we let the service decide the features to avoid future conflict
                self._context_features = OrderedSet(features_in_service)

        self._declaration_thread = Thread(target=self._declare_loop, daemon=True)
        self._declaration_thread.start()
        self._undeclared.join()
        # important to only start the update thread once all pending settings are declared, otherwise we may have
        # stale settings
        self._update_thread = Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        self.reload()

    def reload(self):
        """
        Block until all the tracked settings are up to date
        """
        self._undeclared.join()
        self._update_event.clear()
        self._manual_update.set()
        self._update_event.wait()

    def close(self):
        super().close()
        self._keep_going = False
        self._manual_update.set()
        self._update_thread.join()
        self._declaration_thread.join()

    def set_defaults(self, **kwargs: Union[str, ContextVar[str]]):
        redundant_keys = kwargs.keys() - set(self._context_features)
        if redundant_keys:
            logger.warning('context features are not specified in the client', extra={
                'redundant_keys': redundant_keys
            })
        super().set_defaults(**kwargs)

    def ping(self) -> None:
        """
        Check the health of the heksher server
        Raises:
            httpx.HTTPError, if an error occurs
        """
        response = self._http_client().get('/api/health')
        response.raise_for_status()

    def get_settings(self) -> Dict:
        """
        List all the settings in the service
        """
        response = self._http_client().get('/api/v1/settings', params=orjson.dumps(
            {'include_additional_data': True}))
        response.raise_for_status()
        settings = SettingsOutput.parse_obj(response.json()).to_settings_data()
        return settings
