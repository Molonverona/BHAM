"""
BHAM – Core Configuration
Loads settings from environment variables / .env file using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "BHAM – BACS Help Auto Mapper"
    app_version: str = "0.6.0"
    debug: bool = False

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8765

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
