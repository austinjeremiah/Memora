// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title MEMORA integrity commitment registry
/// @notice Anchors a hash of a clinician-approved handover on Base.
///
/// NO PATIENT DATA IS EVER WRITTEN HERE. The only value stored is a SHA-256
/// digest of a canonical serialisation of an approved brief, plus a short
/// non-identifying label. The chain proves that a specific approved state
/// existed at a specific time; it reveals nothing about the patient, and the
/// digest cannot be reversed into the brief.
contract Commitment {
    struct Record {
        uint64 timestamp;   // block time of first commit
        address committer;  // who anchored it
    }

    /// @dev timestamp + address pack into a single storage slot (64 + 160 bits).
    mapping(bytes32 => Record) private _records;

    uint256 public totalCommitments;

    event StateCommitted(
        address indexed committer,
        bytes32 indexed commitmentHash,
        uint64 timestamp,
        string label
    );

    error EmptyCommitment();
    error AlreadyCommitted(bytes32 commitmentHash, uint64 timestamp);

    /// @notice Anchor a commitment hash. Each hash may be committed once.
    /// @dev Re-committing reverts rather than overwriting: the value of this
    ///      registry is that a recorded timestamp is the FIRST time the state
    ///      existed, and a silent overwrite would destroy exactly that.
    function commit(bytes32 commitmentHash, string calldata label) external {
        if (commitmentHash == bytes32(0)) revert EmptyCommitment();

        Record storage existing = _records[commitmentHash];
        if (existing.timestamp != 0) {
            revert AlreadyCommitted(commitmentHash, existing.timestamp);
        }

        uint64 ts = uint64(block.timestamp);
        _records[commitmentHash] = Record({timestamp: ts, committer: msg.sender});
        unchecked {
            ++totalCommitments;
        }

        emit StateCommitted(msg.sender, commitmentHash, ts, label);
    }

    /// @notice Check whether a hash was anchored, and by whom.
    function verify(bytes32 commitmentHash)
        external
        view
        returns (bool exists, uint64 timestamp, address committer)
    {
        Record memory record = _records[commitmentHash];
        return (record.timestamp != 0, record.timestamp, record.committer);
    }
}
