"""
BHAM – Scanner Base
Per-session abort events and base class for all scanner implementations.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

# threading.Event because is_aborted() is also polled from executor threads.
_abort_events: dict[str, threading.Event] = {}


def abort_session(session_id: str) -> None:
    _abort_events.setdefault(session_id, threading.Event()).set()


def abort_all() -> int:
    for ev in _abort_events.values():
        ev.set()
    return len(_abort_events)


class BaseScanner(ABC):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def reset_abort(self) -> None:
        _abort_events[self.session_id] = threading.Event()

    def is_aborted(self) -> bool:
        ev = _abort_events.get(self.session_id)
        return ev is not None and ev.is_set()

    @abstractmethod
    async def scan(self, *args, **kwargs) -> None: ...
