// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Attestation} from "../src/Attestation.sol";

contract AttestationTest is Test {
    Attestation internal registry;
    uint256 internal clinicianKey = 0xA11CE;
    address internal clinician;

    bytes32 constant TYPEHASH = keccak256(
        "ClinicalAttestation(bytes32 stateHash,bytes32 evidenceRoot,bytes32 contextHash,uint64 memoryVersion,uint64 issuedAt,uint64 expiresAt,uint256 nonce)"
    );

    function setUp() public {
        registry = new Attestation();
        clinician = vm.addr(clinicianKey);
        vm.warp(1_787_985_530);
    }

    function _att(bytes32 stateHash, uint256 nonce)
        internal view returns (Attestation.ClinicalAttestation memory)
    {
        return Attestation.ClinicalAttestation({
            stateHash: stateHash,
            evidenceRoot: keccak256("evidence"),
            contextHash: keccak256("context"),
            memoryVersion: 7,
            issuedAt: uint64(block.timestamp),
            expiresAt: uint64(block.timestamp + 900),
            nonce: nonce
        });
    }

    function _sign(Attestation.ClinicalAttestation memory a, uint256 key)
        internal view returns (bytes memory)
    {
        bytes32 structHash = keccak256(abi.encode(
            TYPEHASH, a.stateHash, a.evidenceRoot, a.contextHash,
            a.memoryVersion, a.issuedAt, a.expiresAt, a.nonce
        ));
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", registry.domainSeparator(), structHash)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    // ---- the happy path ---------------------------------------------------

    function test_AttestThenVerify() public {
        Attestation.ClinicalAttestation memory a = _att(keccak256("state-1"), 0);
        registry.attest(a, clinician, _sign(a, clinicianKey));

        (bool exists, address signer, uint64 ts, uint64 mv) = registry.verify(a.stateHash);
        assertTrue(exists);
        assertEq(signer, clinician);
        assertEq(ts, uint64(block.timestamp));
        assertEq(mv, 7);
        assertEq(registry.totalAttestations(), 1);
        assertEq(registry.nonces(clinician), 1, "nonce must be consumed");
    }

    function test_UnattestedStateDoesNotExist() public view {
        (bool exists,,,) = registry.verify(keccak256("never"));
        assertFalse(exists);
    }

    // ---- REPLAY PROTECTION: the actual security property -------------------

    function test_SameStateHashCannotBeAttestedTwice() public {
        Attestation.ClinicalAttestation memory a = _att(keccak256("state-2"), 0);
        registry.attest(a, clinician, _sign(a, clinicianKey));
        uint64 firstTs = uint64(block.timestamp);

        vm.warp(block.timestamp + 60);
        Attestation.ClinicalAttestation memory again = _att(keccak256("state-2"), 1);
        // Sign BEFORE expectRevert: _sign calls registry.domainSeparator(), and
        // expectRevert applies to the very next external call, so building the
        // signature inline would consume the expectation on a call that succeeds.
        bytes memory sig = _sign(again, clinicianKey);
        vm.expectRevert(
            abi.encodeWithSelector(Attestation.AlreadyAttested.selector, again.stateHash, firstTs)
        );
        registry.attest(again, clinician, sig);

        (, , uint64 ts,) = registry.verify(again.stateHash);
        assertEq(ts, firstTs, "the first attestation time must survive");
    }

    function test_ReusingANonceIsRejected() public {
        Attestation.ClinicalAttestation memory first = _att(keccak256("state-3"), 0);
        registry.attest(first, clinician, _sign(first, clinicianKey));

        // Different state, but the nonce has already been consumed.
        Attestation.ClinicalAttestation memory replay = _att(keccak256("state-4"), 0);
        bytes memory sig = _sign(replay, clinicianKey);   // see note above
        vm.expectRevert(abi.encodeWithSelector(Attestation.BadNonce.selector, 0, 1));
        registry.attest(replay, clinician, sig);
    }

    function test_NoncesAreTrackedPerSigner() public {
        uint256 otherKey = 0xB0B;
        address other = vm.addr(otherKey);

        Attestation.ClinicalAttestation memory a = _att(keccak256("state-5"), 0);
        registry.attest(a, clinician, _sign(a, clinicianKey));

        // A different signer still starts at nonce 0.
        Attestation.ClinicalAttestation memory b = _att(keccak256("state-6"), 0);
        registry.attest(b, other, _sign(b, otherKey));
        assertEq(registry.nonces(other), 1);
        assertEq(registry.totalAttestations(), 2);
    }

    // ---- deadline ---------------------------------------------------------

    function test_ExpiredAttestationIsRejected() public {
        Attestation.ClinicalAttestation memory a = _att(keccak256("state-7"), 0);
        bytes memory sig = _sign(a, clinicianKey);

        vm.warp(uint256(a.expiresAt) + 1);
        vm.expectRevert(
            abi.encodeWithSelector(
                Attestation.AttestationExpired.selector, a.expiresAt, block.timestamp)
        );
        registry.attest(a, clinician, sig);
    }

    // ---- signature integrity ----------------------------------------------

    function test_SignatureFromAnotherKeyIsRejected() public {
        Attestation.ClinicalAttestation memory a = _att(keccak256("state-8"), 0);
        bytes memory wrongSig = _sign(a, 0xBADBAD);
        vm.expectRevert();
        registry.attest(a, clinician, wrongSig);
    }

    function test_TamperedFieldInvalidatesTheSignature() public {
        Attestation.ClinicalAttestation memory a = _att(keccak256("state-9"), 0);
        bytes memory sig = _sign(a, clinicianKey);
        a.memoryVersion = 999;  // altered after signing
        vm.expectRevert();
        registry.attest(a, clinician, sig);
    }

    function test_EmptyStateHashIsRejected() public {
        Attestation.ClinicalAttestation memory a = _att(bytes32(0), 0);
        bytes memory sig = _sign(a, clinicianKey);        // see note above
        vm.expectRevert(Attestation.EmptyStateHash.selector);
        registry.attest(a, clinician, sig);
    }

    // ---- domain binding ---------------------------------------------------

    function test_DomainSeparatorIsBoundToThisDeployment() public {
        bytes32 mine = registry.domainSeparator();
        Attestation other = new Attestation();
        assertTrue(mine != other.domainSeparator(),
            "a signature must not be replayable against a different deployment");
    }

    function testFuzz_AnyDistinctStateAttestsOnce(bytes32 stateHash) public {
        vm.assume(stateHash != bytes32(0));
        Attestation.ClinicalAttestation memory a = _att(stateHash, 0);
        registry.attest(a, clinician, _sign(a, clinicianKey));
        (bool exists,,,) = registry.verify(stateHash);
        assertTrue(exists);
    }
}
