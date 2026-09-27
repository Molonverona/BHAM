"""
BHAM – Scanner Base
Shared abort event and base class for all scanner implementations.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

# Global abort signal – set by POST /scan/abort
abort_event = asyncio.Event()


class BaseScanner(ABC):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    @classmethod
    def reset_abort(cls) -> None:
        """Azzera il segnale di abort prima dell'inizio di una nuova scansione."""
        abort_event.clear()

    def is_aborted(self) -> bool:
        return abort_event.is_set()

    @abstractmethod
    async def scan(self, *args, **kwargs) -> None: ...
