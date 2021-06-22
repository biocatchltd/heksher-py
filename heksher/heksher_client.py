from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Collection, Mapping
from weakref import WeakSet

import heksher.main_client
from heksher.setting import Setting


class BaseHeksherClient(ABC):
    @abstractmethod
    def add_settings(self, settings: Collection[Setting]):
        """
        Register a setting to be declared.
        Args:
            settings: the setting that needs to be declared.
        """
        pass

    @abstractmethod
    def context_namespace(self, user_namespace: Mapping[str, str]) -> Mapping[str, str]:
        """
        Create a context namespace for ruleset resolution, with context features and their values.
        Args:
            user_namespace: namespace provided by the user, to be treated as overriding values.

        Returns:
            A new mapping combining ns and the client's state, to be used for ruleset resolution.

        """
        pass

    def _set_as_main(self):
        """
        Internal method to transfer "main-ness" to self
        """
        if not isinstance(heksher.main_client.Main, TemporaryClient):
            raise TypeError(f'cannot remove cliant of type {type(heksher.main_client.Main).__name__} from main')
        self.add_settings(heksher.main_client.Main.undeclared)
        heksher.main_client.Main = self


class TemporaryClient(BaseHeksherClient):
    """
    A temporary client, to hold undeclared settings until another client takes over.
    """

    def __init__(self):
        self.undeclared: WeakSet = WeakSet()

    def add_settings(self, settings: Collection[Setting]):
        self.undeclared.update(settings)

    def context_namespace(self, user_namespace: Mapping[str, str]) -> Mapping[str, str]:
        return user_namespace


heksher.main_client.Main = TemporaryClient()
