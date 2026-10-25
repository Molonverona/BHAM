"""
BHAM – Resource Guard
Mutua esclusione sulle risorse di campo che ammettono un solo utilizzatore.

Alcune risorse usate in collaudo non sono condivisibili:

- una porta seriale RS485 può essere aperta da un solo processo: una scansione
  Modbus RTU e uno sniffer passivo sulla stessa `/dev/ttyUSB0` si contendono il
  device e producono letture corrotte;
- il discovery BACnet/IP effettua il bind della porta 47808: due scansioni
  contemporanee collidono sul bind;
- il discovery KNXnet/IP e il Group Monitor fanno il bind della 3671.

Senza una guardia il secondo avvio falliva in modo oscuro (o, peggio, i due
consumatori si rubavano i byte a vicenda falsando la diagnosi del bus). Qui la
risorsa viene rivendicata prima di partire e l'eventuale conflitto viene
riportato all'operatore con il nome della scansione che la sta già usando.

Il registro è protetto da un lock di threading perché gli scanner rilasciano la
risorsa anche da thread di executor, non solo dall'event loop.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

# ── Chiavi di risorsa ─────────────────────────────────────────────────────────

#: Il discovery BACnet/IP effettua il bind di una porta UDP fissa.
BACNET_IP = "bacnet-ip"
#: Discovery KNXnet/IP e Group Monitor condividono il socket multicast 3671.
KNX_IP = "knx-ip"


def serial_resource(port: str | None) -> str:
    """Chiave di risorsa per una porta seriale (es. `serial:/dev/ttyUSB0`)."""
    return f"serial:{(port or '').strip() or 'non-specificata'}"


def iface_resource(kind: str, iface: str | None) -> str:
    """Chiave di risorsa per una cattura legata a un'interfaccia di rete."""
    return f"{kind}:{(iface or '').strip() or 'auto'}"


# ── Rivendicazioni ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResourceClaim:
    """Una risorsa attualmente rivendicata da una sessione di scansione."""

    resource: str
    session_id: str
    label: str
    acquired_at: datetime

    def age_seconds(self, now: datetime | None = None) -> float:
        return ((now or datetime.now(timezone.utc)) - self.acquired_at).total_seconds()

    def as_dict(self) -> dict:
        return {
            "resource": self.resource,
            "session_id": self.session_id,
            "label": self.label,
            "acquired_at": self.acquired_at.isoformat(),
            "age_seconds": round(self.age_seconds(), 1),
        }


class ResourceBusyError(RuntimeError):
    """La risorsa richiesta è già rivendicata da un'altra sessione."""

    def __init__(self, resource: str, holder: ResourceClaim) -> None:
        self.resource = resource
        self.holder = holder
        super().__init__(
            f"Risorsa '{resource}' già in uso da '{holder.label}' "
            f"(sessione {holder.session_id})"
        )

    def as_detail(self) -> dict:
        """Corpo di risposta per l'HTTP 409, con indicazione dell'azione."""
        age = int(self.holder.age_seconds())
        return {
            "detail": (
                f"La risorsa è già in uso da «{self.holder.label}», avviata "
                f"{age} second{'o' if age == 1 else 'i'} fa."
            ),
            "resource": self.resource,
            "conflicting_session_id": self.holder.session_id,
            "conflicting_label": self.holder.label,
            "hint": (
                "Attendi il termine dell'operazione in corso oppure arrestala "
                "con POST /api/v1/scan/abort/{session_id}."
            ),
        }


# ── Registro ──────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_claims: dict[str, ResourceClaim] = {}


def acquire(resource: str, session_id: str, label: str) -> ResourceClaim:
    """
    Rivendica `resource` per `session_id`.

    Rivendicare di nuovo la stessa risorsa dalla stessa sessione è idempotente
    (serve ai riavvii interni di una scansione). Se la detiene un'altra
    sessione solleva `ResourceBusyError`.
    """
    with _lock:
        holder = _claims.get(resource)
        if holder is not None and holder.session_id != session_id:
            raise ResourceBusyError(resource, holder)
        claim = ResourceClaim(
            resource=resource,
            session_id=session_id,
            label=label,
            acquired_at=holder.acquired_at if holder else datetime.now(timezone.utc),
        )
        _claims[resource] = claim
        return claim


def release_resource(resource: str) -> bool:
    """Rilascia una risorsa. True se era effettivamente rivendicata."""
    with _lock:
        return _claims.pop(resource, None) is not None


def release_if_owner(resource: str, session_id: str) -> bool:
    """
    Rilascia la risorsa solo se è rivendicata da `session_id`.

    Serve a chi arresta un servizio di lunga durata (p.es. il KNX Group
    Monitor) senza rischiare di liberare una risorsa passata nel frattempo a
    un'altra sessione.
    """
    with _lock:
        holder = _claims.get(resource)
        if holder is not None and holder.session_id == session_id:
            del _claims[resource]
            return True
        return False


def release_session(session_id: str) -> list[str]:
    """Rilascia tutte le risorse di una sessione. Ritorna le chiavi liberate."""
    with _lock:
        freed = [r for r, c in _claims.items() if c.session_id == session_id]
        for r in freed:
            del _claims[r]
        return freed


def claim_for(resource: str) -> ResourceClaim | None:
    """Ritorna la rivendicazione attiva per una risorsa, se esiste."""
    with _lock:
        return _claims.get(resource)


def claims() -> list[ResourceClaim]:
    """Elenco delle risorse attualmente rivendicate, dalla più vecchia."""
    with _lock:
        return sorted(_claims.values(), key=lambda c: c.acquired_at)


def reset() -> None:
    """Svuota il registro. Usato all'arresto del demone e nei test."""
    with _lock:
        _claims.clear()
