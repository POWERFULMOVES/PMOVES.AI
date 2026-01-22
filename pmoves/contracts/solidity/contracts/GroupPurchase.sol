// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/// @title GroupPurchase
/// @notice Enables cooperative members to pool FoodUSD for bulk supplier orders with refund safety.
contract GroupPurchase {
    IERC20 public immutable foodUSD;

    struct Order {
        address creator;
        address supplier;
        uint256 targetAmount;
        uint256 totalContributed;
        uint64 deadline;
        bool executed;
    }

    uint256 public orderCount;
    mapping(uint256 => Order) public orders;
    mapping(uint256 => mapping(address => uint256)) public contributions;

    event OrderCreated(uint256 indexed orderId, address indexed creator, address indexed supplier, uint256 targetAmount, uint64 deadline);
    event ContributionReceived(uint256 indexed orderId, address indexed contributor, uint256 amount, uint256 newTotal);
    event OrderExecuted(uint256 indexed orderId, address indexed supplier, uint256 totalSent);
    event RefundClaimed(uint256 indexed orderId, address indexed participant, uint256 amount);

    constructor(IERC20 _foodUSD) {
        foodUSD = _foodUSD;
    }

    /// @notice Create a new group purchase order.
    function createOrder(address supplier, uint256 targetAmount, uint64 deadline) external returns (uint256) {
        require(supplier != address(0), "supplier zero");
        require(targetAmount > 0, "target zero");
        require(deadline > block.timestamp, "deadline past");

        orderCount += 1;
        orders[orderCount] = Order({
            creator: msg.sender,
            supplier: supplier,
            targetAmount: targetAmount,
            totalContributed: 0,
            deadline: deadline,
            executed: false
        });

        emit OrderCreated(orderCount, msg.sender, supplier, targetAmount, deadline);
        return orderCount;
    }

    /// @notice Contribute FoodUSD toward an order. Executes automatically once the target is met.
    function contribute(uint256 orderId, uint256 amount) external {
        require(amount > 0, "amount zero");
        Order storage order = orders[orderId];
        require(order.creator != address(0), "invalid order");
        require(!order.executed, "executed");
        require(block.timestamp <= order.deadline, "deadline passed");

        contributions[orderId][msg.sender] += amount;
        order.totalContributed += amount;
        require(foodUSD.transferFrom(msg.sender, address(this), amount), "transfer failed");

        emit ContributionReceived(orderId, msg.sender, amount, order.totalContributed);

        if (order.totalContributed >= order.targetAmount) {
            _execute(orderId);
        }
    }

    /// @notice Execute an order manually once the target has been reached.
    function execute(uint256 orderId) external {
        Order storage order = orders[orderId];
        require(order.creator != address(0), "invalid order");
        require(!order.executed, "executed");
        require(order.totalContributed >= order.targetAmount, "target not met");
        _execute(orderId);
    }

    /// @notice Claim a refund if the deadline has passed and the order was not executed.
    function claimRefund(uint256 orderId) external {
        Order storage order = orders[orderId];
        require(order.creator != address(0), "invalid order");
        require(!order.executed, "executed");
        require(block.timestamp > order.deadline, "deadline not passed");

        uint256 contributed = contributions[orderId][msg.sender];
        require(contributed > 0, "nothing to refund");
        contributions[orderId][msg.sender] = 0;
        order.totalContributed -= contributed;
        require(foodUSD.transfer(msg.sender, contributed), "transfer failed");

        emit RefundClaimed(orderId, msg.sender, contributed);
    }

    function _execute(uint256 orderId) internal {
        Order storage order = orders[orderId];
        require(order.totalContributed >= order.targetAmount, "target not met");

        order.executed = true;
        uint256 total = order.totalContributed;
        require(foodUSD.transfer(order.supplier, total), "supplier transfer failed");

        emit OrderExecuted(orderId, order.supplier, total);
    }
}
