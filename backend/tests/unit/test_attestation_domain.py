"""The typed-data structure. Pure -- no chain, no store.

The single easiest place for this feature to break silently: if the Python
field order or types differ from Solidity's ATTESTATION_TYPEHASH string, the
digest never verifies and nothing says why. These tests pin both sides.
"""

import re
from pathlib import Path

import pytest
from eth_utils import keccak

from memora.attestation.domain import (
    ATTESTATION_TYPES,
    DOMAIN_NAME,
    DOMAIN_VERSION,
    SOLIDITY_TYPE_STRING,
    build_domain,
    build_message,
)

CONTRACT = Path(__file__).resolve().parents[2] / "contracts/src/Attestation.sol"
ADDR = "0x8B289101a7d6Bd7d066526B7b8D899Df582dd6b5"


def test_python_types_generate_the_solidity_type_string():
    """Derive the string from the Python declaration and compare. If someone
    reorders a field on one side only, this fails immediately."""
    fields = ATTESTATION_TYPES["ClinicalAttestation"]
    derived = "ClinicalAttestation(" + ",".join(
        f"{f['type']} {f['name']}" for f in fields) + ")"
    assert derived == SOLIDITY_TYPE_STRING


def test_the_contract_declares_the_same_typehash_string():
    """Read the literal out of the .sol file itself -- not a copy of it."""
    source = CONTRACT.read_text()
    match = re.search(r'"(ClinicalAttestation\([^"]*\))"', source)
    assert match, "no ClinicalAttestation typehash string found in Attestation.sol"
    assert match.group(1) == SOLIDITY_TYPE_STRING


def test_the_contract_declares_the_same_domain_name_and_version():
    source = CONTRACT.read_text()
    assert f'EIP712("{DOMAIN_NAME}", "{DOMAIN_VERSION}")' in source


def test_struct_field_order_matches_the_contract_struct():
    """abi.encode order in attest() must match the declared field order."""
    source = CONTRACT.read_text()
    struct = re.search(r"struct ClinicalAttestation \{(.*?)\}", source, re.DOTALL).group(1)
    declared = re.findall(r"\b(\w+);", struct)
    assert declared == [f["name"] for f in ATTESTATION_TYPES["ClinicalAttestation"]]


def test_typehash_is_stable():
    """A changed typehash invalidates every prior attestation. If this value
    changes, that was a deliberate decision, not an accident."""
    assert keccak(text=SOLIDITY_TYPE_STRING).hex() == (
        "8b6efc409e24cf313ef3224dbfb871986495d5a159b37084729bcc1f57bbfeaa")


def test_domain_binds_to_chain_and_contract():
    """Without both, a signature captured here is replayable elsewhere."""
    domain = build_domain(ADDR)
    assert domain["chainId"] == 84532
    assert domain["verifyingContract"] == ADDR
    assert domain["name"] == DOMAIN_NAME


def test_domain_refuses_to_build_without_a_contract(monkeypatch):
    from memora.config import settings
    monkeypatch.setattr(settings, "base_attestation_contract_address", "")
    with pytest.raises(ValueError, match="No attestation contract"):
        build_domain()


def test_message_keys_match_the_declared_field_names():
    message = build_message(b"\x11" * 32, b"\x22" * 32, b"\x33" * 32, 1, 2, 3, 4)
    assert list(message) == [f["name"] for f in ATTESTATION_TYPES["ClinicalAttestation"]]


def test_no_patient_content_can_enter_the_signed_message():
    """Every field is a hash, a counter or a timestamp -- by type."""
    for field in ATTESTATION_TYPES["ClinicalAttestation"]:
        assert field["type"] in ("bytes32", "uint64", "uint256"), field
