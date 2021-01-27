from __future__ import annotations

from typing import TYPE_CHECKING

# avoid circular import
if TYPE_CHECKING:
    from heksher.heksher_client import BaseHeksherClient  # pragma: nocover

Main: BaseHeksherClient
"""
A central client, whose update loops run in the background, and to whom all settings declare themselves.
"""
