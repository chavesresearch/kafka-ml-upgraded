// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

import "./ERC20.sol";

/// @notice The reward token minted for the optional FEDML_BLOCKCHAIN
/// feature. Name/symbol are real constructor arguments (ERC20's own
/// constructor already supports this) rather than baked into the source
/// per deployment - lets this contract be compiled once, ahead of time,
/// instead of recompiled from a dynamically-generated string on every
/// backend startup. See app/blockchain.py for why.
contract Token is ERC20 {
    constructor(string memory name_, string memory symbol_) ERC20(name_, symbol_) {
        _mint(msg.sender, 1e25);
    }
}
