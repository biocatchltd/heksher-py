from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Collection
from weakref import WeakSet

import heksher.main_client
from heksher.setting import Setting


class BaseHeksherClient(ABC):
    @abstractmethod
    def handover_main(self, other: BaseHeksherClient):
        """
        attempt to hand over the "main"-ness of the client from self to other. Might fail if self feels this
        shouldn't happen. Calling this when self is not the main client will result in a runtime error. Note that this
        method should only handle the stopping and cleanup of self, and not start other.
        """
        if heksher.main_client.Main is not self:
            raise RuntimeError('self must be the main client')

    @abstractmethod
    def add_undeclared(self, settings: Collection[Setting]):
        """
        Register a setting to be declared.
        Args:
            settings: the setting that needs to be declared.
        """
        pass

    @abstractmethod
    def context_namespace(self, ns: Mapping[str, str]) -> Mapping[str, str]:
        """
        Create a context namespace for ruleset resolution, with context features and their values.
        Args:
            ns: namespace provided by the user, to be treated as overriding values.

        Returns:
            A new mapping combining ns and the client's state, to be used for ruleset resolution.

        """
        pass

    def _set_as_main(self):
        """
        Internal method to transfer "main-ness" to self
        """
        heksher.main_client.Main.handover_main(self)
        heksher.main_client.Main = self


class TemporaryClient(BaseHeksherClient):
    """
    A temporary client, to hold undeclared settings until another client takes over.
    """

    def __init__(self):
        self.undeclared: WeakSet = WeakSet()

    def add_undeclared(self, settings: Collection[Setting]):
        self.undeclared.update(settings)

    def context_namespace(self, ns: Mapping[str, str]) -> Mapping[str, str]:
        return ns

    def handover_main(self, other: BaseHeksherClient):
        super().handover_main(other)
        other.add_undeclared(self.undeclared)


heksher.main_client.Main = TemporaryClient()
