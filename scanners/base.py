"""
BHAM – Scanner Base
Per-session abort events and base class for all scanner implementations.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

# Per-session abort signals – set by POST /scan/abort/{session_id}
_abort_events: dict[str, asyncio.Event] = {}


class BaseScanner(ABC):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def reset_abort(self) -> None:
        """Crea un nuovo evento di abort per questa sessione."""
        if self.session_id in _abort_events:
            _abort_events[self.session_id].clear()
        else:
            _abort_events[self.session_id] = asyncio.Event()

    def is_aborted(self) -> bool:
        if self.session_id not in _abort_events:
            _abort_events[self.session_id] = asyncio.Event()
        return _abort_events[self.session_id].is_set()

    def set_abort(self) -> None:
        """Segnala l'abort per questa sessione."""
        if self.session_id not in _abort_events:
            _abort_events[self.session_id] = asyncio.Event()
        _abort_events[self.session_id].set()

    @classmethod
    def clear_session_abort(cls, session_id: str) -> None:
        """Pulisce l'evento di abort per una sessione completata."""
        _abort_events.pop(session_id, None)

    @abstractmethod
    async def scan(self, *args, **kwargs) -> None: ...
