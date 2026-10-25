"""
BHAM – Scanner Base
Per-session abort events and base class for all scanner implementations.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

# threading.Event because is_aborted() is also polled from executor threads.
# Il registro viene mutato dalle route (event loop) e letto dai thread degli
# scanner: il lock rende espliciti i confini invece di affidarsi al GIL.
_lock = threading.Lock()
_abort_events: dict[str, threading.Event] = {}


def abort_session(session_id: str) -> bool:
    """
    Segnala l'abort a una sessione.

    Ritorna True se la sessione è stata effettivamente fermata ora, False se
    era già stata abortita. La sessione viene registrata anche se sconosciuta:
    una scansione potrebbe non avere ancora chiamato `reset_abort()`.
    """
    with _lock:
        event = _abort_events.setdefault(session_id, threading.Event())
        already_aborted = event.is_set()
        event.set()
        return not already_aborted


def abort_all() -> list[str]:
    """
    Segnala l'abort a tutte le scansioni in corso.

    Ritorna gli ID delle sessioni effettivamente fermate ora. In precedenza
    ritornava `len(_abort_events)`, cioè il numero di sessioni mai registrate:
    un valore che cresceva per tutta la giornata di lavoro e non corrispondeva
    alle scansioni attive. Inoltre il tipo (int) violava il modello di risposta
    dichiarato dall'endpoint, che falliva quindi la validazione con HTTP 500.
    """
    with _lock:
        stopped: list[str] = []
        for session_id, event in _abort_events.items():
            if not event.is_set():
                event.set()
                stopped.append(session_id)
        return stopped


def release_session(session_id: str) -> None:
    """
    Dimentica lo stato di abort di una sessione conclusa.

    Senza questa pulizia il registro cresceva a ogni scansione e non veniva mai
    liberato per tutta la durata del processo.
    """
    with _lock:
        _abort_events.pop(session_id, None)


def active_sessions() -> list[str]:
    """ID delle sessioni registrate e non ancora abortite."""
    with _lock:
        return [sid for sid, ev in _abort_events.items() if not ev.is_set()]


def tracked_sessions() -> int:
    """Numero di sessioni presenti nel registro (diagnostica e test)."""
    with _lock:
        return len(_abort_events)


class BaseScanner(ABC):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def reset_abort(self) -> None:
        with _lock:
            _abort_events[self.session_id] = threading.Event()

    def is_aborted(self) -> bool:
        with _lock:
            event = _abort_events.get(self.session_id)
        return event is not None and event.is_set()

    @abstractmethod
    async def scan(self, *args, **kwargs) -> None: ...
