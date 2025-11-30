// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title FoodUSD Stablecoin
/// @notice Simple mintable/burnable ERC20 used for cooperative group purchases
contract FoodUSD is ERC20, Ownable {
    constructor(address treasury) ERC20("Food USD", "FUSD") Ownable(treasury) {}

    /// @notice Mint FoodUSD to a recipient. Only callable by the cooperative treasury.
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    /// @notice Burn FoodUSD from the caller's balance.
    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }
}
