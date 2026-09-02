"""Runtime configuration.

Deliberately free of import-time side effects. An earlier draft raised
RuntimeError at module scope when the Sibyl store was missing, which made the
whole app un-importable the moment memory.db went away -- including during the
compliance deletion test, where the intended failure is a clean
SibylUnavailableError raised at the call site. Availability is checked by
memora.sibyl.preflight, not by importing this module.
"""

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "info"

    sibyl_db_path: Path = Path("~/.sibyl-memory/memory.db")

    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = ""

    base_rpc_url: str = "https://sepolia.base.org"
    base_private_key: str = ""
    base_commitment_contract_address: str = ""

    max_evidence_items: int = 8
    gate_strict_mode: bool = True

    @field_validator("sibyl_db_path")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return v.expanduser()


settings = Settings()
