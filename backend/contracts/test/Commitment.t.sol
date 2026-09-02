// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Commitment} from "../src/Commitment.sol";

contract CommitmentTest is Test {
    Commitment internal registry;

    event StateCommitted(
        address indexed committer,
        bytes32 indexed commitmentHash,
        uint64 timestamp,
        string label
    );

    function setUp() public {
        registry = new Commitment();
        vm.warp(1_767_225_600); // deterministic block time
    }

    function test_UnknownHashDoesNotExist() public view {
        (bool exists, uint64 ts, address who) = registry.verify(keccak256("nope"));
        assertFalse(exists);
        assertEq(ts, 0);
        assertEq(who, address(0));
    }

    function test_CommitThenVerifyRoundTrips() public {
        bytes32 h = keccak256("approved-handoff-1");
        registry.commit(h, "P-10482:icu_to_ward");

        (bool exists, uint64 ts, address who) = registry.verify(h);
        assertTrue(exists);
        assertEq(ts, uint64(block.timestamp));
        assertEq(who, address(this));
        assertEq(registry.totalCommitments(), 1);
    }

    function test_CommitEmitsEvent() public {
        bytes32 h = keccak256("approved-handoff-2");
        vm.expectEmit(true, true, false, true);
        emit StateCommitted(address(this), h, uint64(block.timestamp), "label");
        registry.commit(h, "label");
    }

    function test_RecommitRevertsAndPreservesFirstTimestamp() public {
        bytes32 h = keccak256("approved-handoff-3");
        registry.commit(h, "first");
        uint64 firstTs = uint64(block.timestamp);

        vm.warp(block.timestamp + 3600);
        vm.expectRevert(
            abi.encodeWithSelector(Commitment.AlreadyCommitted.selector, h, firstTs)
        );
        registry.commit(h, "second");

        (, uint64 ts,) = registry.verify(h);
        assertEq(ts, firstTs, "first commit time must survive");
    }

    function test_EmptyCommitmentReverts() public {
        vm.expectRevert(Commitment.EmptyCommitment.selector);
        registry.commit(bytes32(0), "label");
    }

    function test_DifferentCommittersRecordedSeparately() public {
        address alice = address(0xA11CE);
        bytes32 h = keccak256("approved-handoff-4");

        vm.prank(alice);
        registry.commit(h, "from alice");

        (,, address who) = registry.verify(h);
        assertEq(who, alice);
    }

    function testFuzz_AnyNonZeroHashRoundTrips(bytes32 h, string calldata label) public {
        vm.assume(h != bytes32(0));
        registry.commit(h, label);
        (bool exists,,) = registry.verify(h);
        assertTrue(exists);
    }
}
