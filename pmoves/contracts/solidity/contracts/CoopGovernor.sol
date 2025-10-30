// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {GroVault} from "./GroVault.sol";

/// @title Cooperative Governor
/// @notice Minimal governance contract implementing quadratic voting with time-locked GroVault power.
contract CoopGovernor {
    GroVault public immutable vault;
    address public chairperson;
    uint256 public proposalCount;
    uint256 public proposalThreshold;
    uint64 public votingPeriod;

    struct Proposal {
        uint256 id;
        string description;
        uint64 startTime;
        uint64 endTime;
        bool executed;
    }

    struct ProposalTally {
        uint256 forVotes;
        uint256 againstVotes;
    }

    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => ProposalTally) public tallies;
    mapping(uint256 => mapping(address => uint256)) public spentVotingPower;

    event ProposalCreated(uint256 indexed id, string description, uint64 startTime, uint64 endTime);
    event VoteCast(uint256 indexed proposalId, address indexed voter, bool support, uint256 rawVotes, uint256 cost);
    event ProposalExecuted(uint256 indexed id, uint256 forVotes, uint256 againstVotes);
    event GovernanceConfigUpdated(uint64 votingPeriod, uint256 proposalThreshold);

    modifier onlyChair() {
        require(msg.sender == chairperson, "not chair");
        _;
    }

    constructor(GroVault _vault, address _chairperson, uint64 _votingPeriod, uint256 _proposalThreshold) {
        require(address(_vault) != address(0), "vault zero");
        require(_chairperson != address(0), "chair zero");
        require(_votingPeriod > 0, "period zero");

        vault = _vault;
        chairperson = _chairperson;
        votingPeriod = _votingPeriod;
        proposalThreshold = _proposalThreshold;
    }

    /// @notice Create a new proposal for cooperative decision making.
    function createProposal(string calldata description) external returns (uint256) {
        proposalCount += 1;
        uint64 start = uint64(block.timestamp);
        uint64 end = start + votingPeriod;
        proposals[proposalCount] = Proposal({id: proposalCount, description: description, startTime: start, endTime: end, executed: false});

        emit ProposalCreated(proposalCount, description, start, end);
        return proposalCount;
    }

    /// @notice Cast a quadratic vote. The quadratic cost (rawVotes^2) must not exceed the remaining voting power.
    function castVote(uint256 proposalId, uint256 rawVotes, bool support) external {
        require(rawVotes > 0, "votes zero");
        Proposal memory proposal = proposals[proposalId];
        require(proposal.id != 0, "invalid proposal");
        require(block.timestamp >= proposal.startTime, "not started");
        require(block.timestamp <= proposal.endTime, "voting closed");

        uint256 cost = rawVotes * rawVotes;
        uint256 available = vault.votingPower(msg.sender);
        uint256 spent = spentVotingPower[proposalId][msg.sender];
        require(cost + spent <= available, "insufficient power");

        spentVotingPower[proposalId][msg.sender] = spent + cost;
        ProposalTally storage tally = tallies[proposalId];
        if (support) {
            tally.forVotes += rawVotes;
        } else {
            tally.againstVotes += rawVotes;
        }

        emit VoteCast(proposalId, msg.sender, support, rawVotes, cost);
    }

    /// @notice Execute a proposal once quorum is achieved and the voting period has ended.
    function execute(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id != 0, "invalid proposal");
        require(block.timestamp > proposal.endTime, "voting ongoing");
        require(!proposal.executed, "executed");

        ProposalTally memory tally = tallies[proposalId];
        require(tally.forVotes >= proposalThreshold, "quorum not met");
        require(tally.forVotes > tally.againstVotes, "not approved");

        proposal.executed = true;

        emit ProposalExecuted(proposalId, tally.forVotes, tally.againstVotes);
    }

    /// @notice Update governance configuration parameters.
    function updateGovernanceConfig(uint64 newVotingPeriod, uint256 newThreshold) external onlyChair {
        require(newVotingPeriod > 0, "period zero");
        require(newThreshold > 0, "threshold zero");
        votingPeriod = newVotingPeriod;
        proposalThreshold = newThreshold;

        emit GovernanceConfigUpdated(newVotingPeriod, newThreshold);
    }

    /// @notice Transfer chairperson role.
    function transferChairperson(address newChair) external onlyChair {
        require(newChair != address(0), "chair zero");
        chairperson = newChair;
    }
}
