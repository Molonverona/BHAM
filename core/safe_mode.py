"""
BHAM – Safe Mode Interlock System ("Blocco Manovre & Sicurezza")
===============================================================
Prevents accidental writes/forces to physical plant controllers and meters.
Write commands (Modbus FC05/FC06/FC15/FC16 and BACnet WriteProperty) are strictly
blocked unless the field technician explicitly ARMS Safe Mode by identifying
themselves (Operator Name), specifying the Job Order / Commessa, and selecting
a bounded time window (e.g. 15, 30, 60 minutes) with automatic disarm.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

from core.audit_journal import audit_journal
from core.logger import logger

log = logger.getChild("safe_mode")


class SafeModeManager:
    """
    Manages operational write permissions on field fieldbuses.
    Default state is SAFE (DISARMED), where all write operations are rejected.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._armed: bool = False
        self._operator: str = ""
        self._job_order: str = ""
        self._armed_at: float = 0.0
        self._expires_at: float = 0.0

    @property
    def is_armed(self) -> bool:
        with self._lock:
            if not self._armed:
                return False
            now = time.time()
            if now >= self._expires_at:
                # Auto-disarm expired session
                self._armed = False
                prev_op = self._operator
                prev_order = self._job_order
                self._operator = ""
                self._job_order = ""
                log.warning("Safe Mode DISARMED automaticamente: sessione scaduta per %s (Commessa: %s)", prev_op, prev_order)
                audit_journal.record_event(
                    action="safe_mode_auto_expired",
                    operator=prev_op or "system",
                    job_order=prev_order or "N/A",
                    details={"reason": "session_timeout"},
                )
                return False
            return True

    @property
    def operator(self) -> str:
        return self._operator if self.is_armed else ""

    @property
    def job_order(self) -> str:
        return self._job_order if self.is_armed else ""

    def arm(self, operator: str, job_order: str, duration_minutes: int = 30) -> dict[str, Any]:
        """
        Arms Safe Mode, enabling write commands for the requested duration.
        """
        op = (operator or "").strip()
        jo = (job_order or "").strip()
        if not op:
            raise ValueError("Il nome operatore è obbligatorio per sbloccare le manovre di scrittura.")
        if not jo:
            raise ValueError("Il numero commessa/impianto è obbligatorio per tracciabilità.")

        duration_sec = max(60, min(duration_minutes * 60, 8 * 3600))  # Max 8h
        now = time.time()

        with self._lock:
            self._armed = True
            self._operator = op
            self._job_order = jo
            self._armed_at = now
            self._expires_at = now + duration_sec

        log.warning("⚠️  SAFE MODE ARMED da %s (Commessa: %s, durata: %d min)", op, jo, duration_minutes)
        audit_journal.record_event(
            action="safe_mode_armed",
            operator=op,
            job_order=jo,
            details={"duration_minutes": duration_minutes, "expires_at": self._expires_at},
        )

        return self.get_status()

    def disarm(self) -> dict[str, Any]:
        """
        Immediately disarms Safe Mode, locking all write operations.
        """
        with self._lock:
            prev_op = self._operator
            prev_order = self._job_order
            was_armed = self._armed
            self._armed = False
            self._operator = ""
            self._job_order = ""
            self._armed_at = 0.0
            self._expires_at = 0.0

        if was_armed:
            log.info("Safe Mode DISARMED manualmente.")
            audit_journal.record_event(
                action="safe_mode_disarmed",
                operator=prev_op or "system",
                job_order=prev_order or "N/A",
                details={"reason": "operator_manual_disarm"},
            )

        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        """Return current Safe Mode interlock status and countdown."""
        now = time.time()
        with self._lock:
            armed = self._armed and (now < self._expires_at)
            remaining_seconds = max(0, int(self._expires_at - now)) if armed else 0
            return {
                "armed": armed,
                "operator": self._operator if armed else "",
                "job_order": self._job_order if armed else "",
                "armed_at": self._armed_at if armed else None,
                "expires_at": self._expires_at if armed else None,
                "remaining_seconds": remaining_seconds,
                "remaining_minutes": round(remaining_seconds / 60, 1) if armed else 0.0,
            }


# Global singleton instance
safe_mode = SafeModeManager()
