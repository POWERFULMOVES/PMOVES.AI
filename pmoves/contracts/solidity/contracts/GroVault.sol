// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/// @title GroVault
/// @notice Time-locked staking vault that computes quadratic voting power with a lock multiplier.
contract GroVault {
    using Math for uint256;

    struct LockPosition {
        uint256 amount;
        uint64 unlockTime;
        uint8 durationYears;
    }

    IERC20 public immutable groToken;
    uint256 public totalLocked;

    uint256 private constant BASE_MULTIPLIER = 1e18;
    uint256 private constant LOCK_BONUS = 5e17; // 0.5 in ray precision
    uint256 private constant YEAR = 365 days;

    mapping(address => LockPosition) public locks;

    event LockCreated(address indexed account, uint256 amount, uint8 durationYears, uint64 unlockTime);
    event LockIncreased(address indexed account, uint256 additionalAmount, uint256 newAmount);
    event LockExtended(address indexed account, uint8 newDurationYears, uint64 newUnlockTime);
    event LockWithdrawn(address indexed account, uint256 amount);

    constructor(IERC20 _groToken) {
        groToken = _groToken;
    }

    /// @notice Create a new lock position. Users can only hold one active lock at a time.
    function createLock(uint256 amount, uint8 durationYears) external {
        require(amount > 0, "amount zero");
        LockPosition storage position = locks[msg.sender];
        require(position.amount == 0, "lock exists");
        _validateDuration(durationYears);

        uint64 unlockTime = uint64(block.timestamp + YEAR * durationYears);
        position.amount = amount;
        position.durationYears = durationYears;
        position.unlockTime = unlockTime;

        totalLocked += amount;
        require(groToken.transferFrom(msg.sender, address(this), amount), "transfer failed");

        emit LockCreated(msg.sender, amount, durationYears, unlockTime);
    }

    /// @notice Increase the amount locked without changing the duration.
    function increaseLock(uint256 additionalAmount) external {
        require(additionalAmount > 0, "amount zero");
        LockPosition storage position = locks[msg.sender];
        require(position.amount > 0, "no lock");
        require(block.timestamp < position.unlockTime, "lock expired");

        position.amount += additionalAmount;
        totalLocked += additionalAmount;
        require(groToken.transferFrom(msg.sender, address(this), additionalAmount), "transfer failed");

        emit LockIncreased(msg.sender, additionalAmount, position.amount);
    }

    /// @notice Extend the lock duration, updating the unlock timestamp.
    function extendLock(uint8 newDurationYears) external {
        LockPosition storage position = locks[msg.sender];
        require(position.amount > 0, "no lock");
        require(block.timestamp < position.unlockTime, "lock expired");
        require(newDurationYears > position.durationYears, "duration not increased");
        _validateDuration(newDurationYears);

        position.durationYears = newDurationYears;
        position.unlockTime = uint64(block.timestamp + YEAR * newDurationYears);

        emit LockExtended(msg.sender, newDurationYears, position.unlockTime);
    }

    /// @notice Withdraw the locked Gro tokens after the unlock time has elapsed.
    function withdraw() external {
        LockPosition storage position = locks[msg.sender];
        require(position.amount > 0, "no lock");
        require(block.timestamp >= position.unlockTime, "not unlocked");

        uint256 amount = position.amount;
        totalLocked -= amount;
        delete locks[msg.sender];
        require(groToken.transfer(msg.sender, amount), "transfer failed");

        emit LockWithdrawn(msg.sender, amount);
    }

    /// @notice Compute the effective voting power for an account per the quadratic + time-lock formula.
    function votingPower(address account) public view returns (uint256) {
        LockPosition memory position = locks[account];
        if (position.amount == 0 || block.timestamp >= position.unlockTime) {
            return 0;
        }

        uint256 sqrtAmount = position.amount.sqrt();
        uint256 multiplier = BASE_MULTIPLIER + LOCK_BONUS * (position.durationYears - 1);
        return (sqrtAmount * multiplier) / BASE_MULTIPLIER;
    }

    function _validateDuration(uint8 durationYears) private pure {
        require(durationYears >= 1 && durationYears <= 4, "invalid duration");
    }
}
