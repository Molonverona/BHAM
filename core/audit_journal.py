"""
BHAM – Crash-Proof Audit Journal ("Registro Manovre Certificato")
================================================================
Append-only tamper-evident audit journal for all field bus write/override maneuvers.
Key security and reliability features:
  1. Write-Ahead Logging (WAL): Records INTENT before serial/UDP transmission with os.fsync.
     If the PC is disconnected, crashes, or power is cut, the intent is permanently on disk.
  2. Cryptographic Chaining: Every journal entry carries the SHA-256 hash of the previous
     entry (prev_hash -> entry_hash), forming a tamper-evident blockchain-like local log.
  3. Orphan Intent Auto-Recovery: On startup, any INTENT lacking a subsequent RESULT is detected
     and recorded as an interrupted/unconfirmed operation.
  4. Integrity Verification: Validates the cryptographic hash chain from Genesis to EOF.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from core.logger import logger
from core.paths import get_audit_journal_path

log = logger.getChild("audit_journal")

GENESIS_HASH = "0" * 64


def _canonical_json(data: dict[str, Any]) -> str:
    """Return deterministic JSON representation for reproducible hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_hash(prev_hash: str, payload_str: str) -> str:
    """Compute SHA-256 over previous hash + canonical payload."""
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(b"|")
    h.update(payload_str.encode("utf-8"))
    return h.hexdigest()


class AuditJournal:
    """
    Thread-safe append-only audit journal with write-ahead logging and SHA-256 chaining.
    """

    def __init__(self, journal_path: Optional[Path] = None):
        self._path = journal_path or get_audit_journal_path()
        self._lock = threading.Lock()
        self._last_hash = GENESIS_HASH
        self._entry_counter = 0
        self._init_journal()

    @property
    def path(self) -> Path:
        return self._path

    def _init_journal(self) -> None:
        """Initialize journal file and restore last hash & counter from disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            log.info("Creazione nuovo Registro Manovre: %s", self._path)
            return

        # Scan existing entries to find last valid hash and entry counter
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if "entry_hash" in entry:
                            self._last_hash = entry["entry_hash"]
                        self._entry_counter += 1
                    except Exception:
                        pass
            log.debug("Registro Manovre caricato: %d manovre, hash=%s", self._entry_counter, self._last_hash[:12])
        except Exception as exc:
            log.error("Errore lettura Registro Manovre: %s", exc)

    def _refresh_last_entry_from_disk(self) -> None:
        """Syncs the latest hash and counter directly from disk to prevent stale chaining."""
        if not self._path.exists() or self._path.stat().st_size == 0:
            self._last_hash = GENESIS_HASH
            self._entry_counter = 0
            return

        try:
            with open(self._path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                buffer_size = min(8192, size)
                f.seek(-buffer_size, os.SEEK_END)
                lines = f.read().splitlines()
                for line in reversed(lines):
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str:
                        entry = json.loads(line_str)
                        if "entry_hash" in entry:
                            self._last_hash = entry["entry_hash"]
                        if "entry_id" in entry and entry["entry_id"].startswith("JNL-"):
                            try:
                                self._entry_counter = int(entry["entry_id"].split("-")[1])
                            except ValueError:
                                pass
                        break
        except Exception as exc:
            log.warning("Impossibile sincronizzare ultimo hash da disco: %s", exc)

    def _append_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Atomically appends an entry to the journal file with os.fsync."""
        with self._lock:
            self._refresh_last_entry_from_disk()
            self._entry_counter += 1
            entry_id = f"JNL-{self._entry_counter:06d}"
            t_epoch = time.time()
            t_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_epoch))

            entry["entry_id"] = entry_id
            entry["timestamp_epoch"] = round(t_epoch, 3)
            entry["timestamp_iso"] = t_iso
            entry["prev_hash"] = self._last_hash

            # Calculate hash over canonical representation excluding entry_hash itself
            payload_for_hash = {k: v for k, v in entry.items() if k != "entry_hash"}
            canonical = _canonical_json(payload_for_hash)
            entry_hash = _compute_hash(self._last_hash, canonical)
            entry["entry_hash"] = entry_hash
            self._last_hash = entry_hash

            # Write-ahead commit with os.fsync for power-cut resilience
            line_str = json.dumps(entry, ensure_ascii=False) + "\n"
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line_str)
                f.flush()
                os.fsync(f.fileno())

            log.info("Audit [%s] %s: %s (hash: %s)", entry.get("phase"), entry_id, entry.get("action"), entry_hash[:8])
            return entry

    def record_intent(
        self,
        action: str,
        protocol: str,
        target: dict[str, Any],
        value_requested: Any,
        operator: str = "field_engineer",
        job_order: str = "COMMESSA_DEFAULT",
        value_before: Optional[Any] = None,
        notes: str = "",
    ) -> str:
        """
        Stage 1 of WAL: Record INTENT *before* physical bus transmission.
        Returns the unique intent_id to be referenced in the RESULT stage.
        """
        entry = {
            "phase": "INTENT",
            "action": action,
            "protocol": protocol,
            "operator": operator or "anonymous",
            "job_order": job_order or "N/A",
            "target": target,
            "value_before": value_before,
            "value_requested": value_requested,
            "status": "pending",
            "notes": notes,
        }
        res = self._append_entry(entry)
        return res["entry_id"]

    def record_result(
        self,
        intent_id: str,
        action: str,
        protocol: str,
        target: dict[str, Any],
        status: str,  # "success" | "error" | "interrupted" | "mismatch"
        value_requested: Any,
        value_verified: Optional[Any] = None,
        operator: str = "field_engineer",
        job_order: str = "COMMESSA_DEFAULT",
        elapsed_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Stage 2 of WAL: Record RESULT *after* physical bus response & read-back verification.
        """
        entry = {
            "phase": "RESULT",
            "intent_id": intent_id,
            "action": action,
            "protocol": protocol,
            "operator": operator or "anonymous",
            "job_order": job_order or "N/A",
            "target": target,
            "status": status,
            "value_requested": value_requested,
            "value_verified": value_verified,
            "elapsed_ms": elapsed_ms,
            "error": error,
        }
        return self._append_entry(entry)

    def record_event(
        self,
        action: str,
        operator: str = "system",
        job_order: str = "N/A",
        details: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Record a single system-level event (e.g. safe mode armed, session startup)."""
        entry = {
            "phase": "EVENT",
            "action": action,
            "protocol": "system",
            "operator": operator,
            "job_order": job_order,
            "status": "success",
            "details": details or {},
        }
        return self._append_entry(entry)

    def recover_orphaned_intents(self) -> int:
        """
        Scans for INTENT records without a matching RESULT (e.g. laptop shut down mid-write).
        Appends an INTERRUPTED result for each orphan to certify incomplete maneuvers.
        """
        if not self._path.exists():
            return 0

        pending_intents: dict[str, dict[str, Any]] = {}
        completed_intents: set[str] = set()

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if e.get("phase") == "INTENT":
                            pending_intents[e["entry_id"]] = e
                        elif e.get("phase") == "RESULT" and e.get("intent_id"):
                            completed_intents.add(e["intent_id"])
                    except Exception:
                        pass
        except Exception as exc:
            log.error("Errore scansione intent orfani: %s", exc)
            return 0

        orphans = [e for eid, e in pending_intents.items() if eid not in completed_intents]
        if not orphans:
            return 0

        log.warning("Rilevati %d intent orfani (interruzione anomala/stacco alimentazione)!", len(orphans))
        for o in orphans:
            self.record_result(
                intent_id=o["entry_id"],
                action=o.get("action", "unknown"),
                protocol=o.get("protocol", "unknown"),
                target=o.get("target", {}),
                status="interrupted",
                value_requested=o.get("value_requested"),
                value_verified=None,
                operator=o.get("operator", "system_recovery"),
                job_order=o.get("job_order", "N/A"),
                error="Manovra interrotta da arresto improvviso del sistema prima della conferma bus.",
            )
        return len(orphans)

    def verify_integrity(self) -> dict[str, Any]:
        """
        Validates the cryptographic integrity of the entire journal.
        Returns validation status, total entries, and error list if tampering or corruption detected.
        """
        if not self._path.exists():
            return {
                "valid": True,
                "total_entries": 0,
                "genesis_hash": GENESIS_HASH,
                "last_hash": GENESIS_HASH,
                "errors": [],
            }

        prev_hash = GENESIS_HASH
        errors: list[str] = []
        count = 0

        with open(self._path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    entry = json.loads(line)
                except Exception as exc:
                    errors.append(f"Linea {line_idx}: JSON non valido ({exc})")
                    continue

                # Check prev_hash chaining
                entry_prev = entry.get("prev_hash")
                if entry_prev != prev_hash:
                    errors.append(
                        f"Linea {line_idx} [{entry.get('entry_id')}]: Discrepanza hash precedente. Atteso {prev_hash[:8]}, trovato {str(entry_prev)[:8]}"
                    )

                # Recompute hash
                payload_for_hash = {k: v for k, v in entry.items() if k != "entry_hash"}
                canonical = _canonical_json(payload_for_hash)
                expected_hash = _compute_hash(entry_prev or GENESIS_HASH, canonical)
                actual_hash = entry.get("entry_hash")

                if actual_hash != expected_hash:
                    errors.append(
                        f"Linea {line_idx} [{entry.get('entry_id')}]: Manomissione o corruzione dati. Hash ricalcolato={expected_hash[:8]}, hash nel file={str(actual_hash)[:8]}"
                    )

                prev_hash = actual_hash or expected_hash

        return {
            "valid": len(errors) == 0,
            "total_entries": count,
            "genesis_hash": GENESIS_HASH,
            "last_hash": prev_hash,
            "errors": errors,
        }

    def list_entries(self, limit: int = 100, reverse: bool = True) -> list[dict[str, Any]]:
        """Return the most recent journal entries."""
        if not self._path.exists():
            return []

        entries: list[dict[str, Any]] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
        except Exception as exc:
            log.error("Errore lettura lista manovre: %s", exc)

        if reverse:
            entries.reverse()
        return entries[:limit]


# Global singleton instance
audit_journal = AuditJournal()
