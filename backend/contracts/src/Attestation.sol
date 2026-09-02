// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {Nonces} from "@openzeppelin/contracts/utils/Nonces.sol";

/// @title MEMORA clinical attestation registry
/// @notice Records that a specific approved clinical state was cryptographically
///         signed, by a specific signer, at a specific time.
///
/// NO PATIENT DATA IS EVER WRITTEN HERE. Every stored value is a hash, a
/// counter, an address or a timestamp. The chain proves a state was attested;
/// it reveals nothing about the patient it concerns.
///
/// THE SIGNERS ARE SYNTHETIC DEMO KEYS held server-side by the MEMORA
/// prototype. They are not real clinician identities and this contract must
/// not be described as an authentication mechanism.
///
/// Replay protection is deliberate and two-part: EIP-712 itself provides NONE.
/// The domain separator binds a signature to this chain and this contract; the
/// per-signer nonce stops the same signature being submitted twice; the
/// deadline bounds how long a captured signature stays usable.
contract Attestation is EIP712, Nonces {
    struct ClinicalAttestation {
        bytes32 stateHash;
        bytes32 evidenceRoot;
        bytes32 contextHash;
        uint64 memoryVersion;
        uint64 issuedAt;
        uint64 expiresAt;
        uint256 nonce;
    }

    /// @dev Must match memora/attestation/domain.py's SOLIDITY_TYPE_STRING
    ///      character for character. A mismatch produces a digest that never
    ///      verifies, and it fails silently rather than loudly.
    bytes32 private constant ATTESTATION_TYPEHASH = keccak256(
        "ClinicalAttestation(bytes32 stateHash,bytes32 evidenceRoot,bytes32 contextHash,uint64 memoryVersion,uint64 issuedAt,uint64 expiresAt,uint256 nonce)"
    );

    struct Record {
        address signer;
        uint64 timestamp;
        uint64 memoryVersion;
        bool exists;
    }

    mapping(bytes32 => Record) private _records;
    uint256 public totalAttestations;

    event ClinicalAttested(
        bytes32 indexed stateHash,
        address indexed signer,
        bytes32 evidenceRoot,
        bytes32 contextHash,
        uint64 memoryVersion,
        uint64 timestamp
    );

    error AttestationExpired(uint64 expiresAt, uint256 nowTs);
    error BadNonce(uint256 supplied, uint256 expected);
    error AlreadyAttested(bytes32 stateHash, uint64 timestamp);
    error SignerMismatch(address recovered, address claimed);
    error EmptyStateHash();

    constructor() EIP712("MEMORA Clinical Integrity", "1") {}

    /// @notice Record an attestation, verifying the signature on chain.
    function attest(
        ClinicalAttestation calldata a,
        address signer,
        bytes calldata signature
    ) external {
        if (a.stateHash == bytes32(0)) revert EmptyStateHash();
        if (block.timestamp > a.expiresAt) {
            revert AttestationExpired(a.expiresAt, block.timestamp);
        }

        uint256 expected = nonces(signer);
        if (a.nonce != expected) revert BadNonce(a.nonce, expected);

        Record storage existing = _records[a.stateHash];
        if (existing.exists) revert AlreadyAttested(a.stateHash, existing.timestamp);

        bytes32 structHash = keccak256(
            abi.encode(
                ATTESTATION_TYPEHASH,
                a.stateHash,
                a.evidenceRoot,
                a.contextHash,
                a.memoryVersion,
                a.issuedAt,
                a.expiresAt,
                a.nonce
            )
        );
        address recovered = ECDSA.recover(_hashTypedDataV4(structHash), signature);
        if (recovered != signer) revert SignerMismatch(recovered, signer);

        _useNonce(signer);

        _records[a.stateHash] = Record({
            signer: signer,
            timestamp: uint64(block.timestamp),
            memoryVersion: a.memoryVersion,
            exists: true
        });
        unchecked { ++totalAttestations; }

        emit ClinicalAttested(
            a.stateHash, signer, a.evidenceRoot, a.contextHash,
            a.memoryVersion, uint64(block.timestamp)
        );
    }

    function verify(bytes32 stateHash)
        external
        view
        returns (bool exists, address signer, uint64 timestamp, uint64 memoryVersion)
    {
        Record memory r = _records[stateHash];
        return (r.exists, r.signer, r.timestamp, r.memoryVersion);
    }

    /// @notice The EIP-712 domain separator, exposed so an off-chain signer can
    ///         confirm it is signing against this exact deployment.
    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }
}
