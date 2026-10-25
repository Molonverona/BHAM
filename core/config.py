"""
BHAM – Core Configuration
Loads settings from environment variables / .env file using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field
import hmac
import platform
import secrets


def _env(name: str) -> AliasChoices:
    """
    Accetta sia il nome semplice (`PORT`) sia quello con prefisso di progetto
    (`BHAM_PORT`), allineandosi alle variabili runtime già usate da BHAM
    (`BHAM_DEMO`, `BHAM_NO_BROWSER`, `BHAM_PORTABLE`).
    """
    return AliasChoices(name, f"bham_{name}")

# Porta seriale di ripiego quando l'utente non ne ha selezionata una.
DEFAULT_SERIAL_PORT = "COM1" if platform.system() == "Windows" else "/dev/ttyUSB0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "BHAM – BACS Help Auto Mapper"
    app_version: str = "1.2.5"
    debug: bool = Field(default=False, validation_alias=_env("debug"))

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0", validation_alias=_env("host"))
    port: int = Field(default=8765, validation_alias=_env("port"))

    # ── Security & Remote LAN Access ─────────────────────────────────────────
    api_token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(16),
        validation_alias=_env("api_token"),
    )
    lan_auth_required: bool = Field(default=True, validation_alias=_env("lan_auth_required"))

    def verify_token(self, token: str | None) -> bool:
        """Verifica se il token fornito corrisponde a quello attivo del demone."""
        if not self.lan_auth_required:
            return True
        if not token or not self.api_token:
            return False
        return hmac.compare_digest(token.strip(), self.api_token.strip())

    # ── Modbus RTU defaults ──────────────────────────────────────────────────
    modbus_default_baudrates: list[int] = Field(
        default=[9600, 19200, 38400, 115200]
    )
    modbus_default_parities: list[str] = Field(default=["N", "E", "O"])
    modbus_default_stopbits: list[int] = Field(default=[1, 2])
    modbus_timeout: float = 0.5           # seconds – initial probe
    modbus_fast_timeout: float = 0.15     # seconds – after LOCK

    # ── Modbus TCP defaults ──────────────────────────────────────────────────
    modbus_tcp_port: int = 502
    modbus_tcp_timeout: float = 1.0

    # ── BACnet ───────────────────────────────────────────────────────────────
    bacnet_port: int = 47808
    bacnet_timeout: float = 3.0

    # ── IP Sniffer ───────────────────────────────────────────────────────────
    arp_sniff_duration: float = 30.0      # seconds
    arp_sniff_iface: str = ""             # empty = auto-detect


settings = Settings()
