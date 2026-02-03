// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title GroToken
/// @notice Governance and rewards token used for staking and voting power
contract GroToken is ERC20, Ownable {
    constructor(address treasury) ERC20("Gro Token", "GRO") Ownable(treasury) {}

    /// @notice Mint new Gro tokens for incentives or treasury programs.
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    /// @notice Burn Gro tokens from the caller's balance.
    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }
}
