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
    base_attestation_contract_address: str = ""
    base_chain_id: int = 84532  # Base Sepolia

    # Master seed for SYNTHETIC DEMO CLINICIAN KEYS ONLY. These are not, and
    # must never be described as, real clinician identities or an
    # authentication mechanism -- they exist so a hackathon demo can show a
    # cryptographically attributed signature. Never commit a real value.
    attestation_seed: str = ""

    # OPTION B signer authorisation: clinician_id -> wallet address, as
    # "dr_maya:0xABC...,dr_arun:0xDEF...". Only a pre-registered address may
    # sign as that clinician; a wallet signing as someone it is not mapped to
    # is refused even though its signature is cryptographically valid.
    #
    # A clinician with no registered wallet falls back to their synthetic demo
    # key, so the system still works with no wallet configured at all.
    clinician_wallets: dict[str, str] = {}

    @field_validator("clinician_wallets", mode="before")
    @classmethod
    def _parse_wallets(cls, v):
        if isinstance(v, str):
            mapping = {}
            for pair in v.split(","):
                if ":" not in pair:
                    continue
                cid, _, addr = pair.partition(":")
                if cid.strip() and addr.strip():
                    mapping[cid.strip()] = addr.strip()
            return mapping
        return v

    max_evidence_items: int = 8
    gate_strict_mode: bool = True

    # Frontend origins allowed to call this API from a browser. No CORS
    # middleware existed before this was added -- without it, every
    # browser-based fetch from the frontend is silently blocked. Defaults
    # cover the two hosts a local Next.js dev server binds to; override via
    # CORS_ALLOW_ORIGINS (comma-separated) for a deployed frontend origin.
    cors_allow_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("sibyl_db_path")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return v.expanduser()


settings = Settings()
