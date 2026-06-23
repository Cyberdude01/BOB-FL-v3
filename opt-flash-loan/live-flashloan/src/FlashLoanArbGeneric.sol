// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20Generic {
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

interface IAavePoolGeneric {
    function flashLoanSimple(
        address receiverAddress,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

interface IFlashLoanSimpleReceiverGeneric {
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool);
}

/// @notice Generic Aave V3 atomic flash-loan executor.
/// @dev Executes two arbitrary router calls inside one flash-loan callback.
///      If final balance is not enough to repay + minProfit, it reverts.
contract FlashLoanArbGeneric is IFlashLoanSimpleReceiverGeneric {
    address public immutable owner;
    IAavePoolGeneric public immutable pool;

    error NotOwner();
    error NotPool();
    error BadInitiator();
    error RouterCallFailed(uint8 leg, bytes reason);
    error NotProfitable(uint256 finalBalance, uint256 owed, uint256 minProfit);
    error TransferFailed();

    struct ArbParams {
        address routerA;
        address routerB;
        address tokenBorrow;
        address tokenMid;
        uint256 minProfit;
        bytes callDataA;
        bytes callDataB;
    }

    event ArbRequested(address indexed asset, uint256 amount);
    event ArbCompleted(address indexed asset, uint256 profit, uint256 premium);
    event Withdraw(address indexed token, uint256 amount);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(address _pool) {
        owner = msg.sender;
        pool = IAavePoolGeneric(_pool);
    }

    function executeArb(ArbParams calldata p, uint256 amount) external onlyOwner {
        emit ArbRequested(p.tokenBorrow, amount);
        pool.flashLoanSimple(address(this), p.tokenBorrow, amount, abi.encode(p), 0);
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        if (msg.sender != address(pool)) revert NotPool();
        if (initiator != address(this)) revert BadInitiator();

        ArbParams memory p = abi.decode(params, (ArbParams));

        // Approve exactly what each router needs for each leg.
        IERC20Generic(p.tokenBorrow).approve(p.routerA, 0);
        IERC20Generic(p.tokenBorrow).approve(p.routerA, amount);
        (bool okA, bytes memory retA) = p.routerA.call(p.callDataA);
        if (!okA) revert RouterCallFailed(1, retA);

        uint256 midBalance = IERC20Generic(p.tokenMid).balanceOf(address(this));
        IERC20Generic(p.tokenMid).approve(p.routerB, 0);
        IERC20Generic(p.tokenMid).approve(p.routerB, midBalance);
        (bool okB, bytes memory retB) = p.routerB.call(p.callDataB);
        if (!okB) revert RouterCallFailed(2, retB);

        uint256 owed = amount + premium;
        uint256 finalBalance = IERC20Generic(asset).balanceOf(address(this));
        if (finalBalance < owed + p.minProfit) {
            revert NotProfitable(finalBalance, owed, p.minProfit);
        }

        IERC20Generic(asset).approve(address(pool), 0);
        IERC20Generic(asset).approve(address(pool), owed);
        uint256 profit = finalBalance - owed;
        if (profit > 0) {
            if (!IERC20Generic(asset).transfer(owner, profit)) revert TransferFailed();
        }
        emit ArbCompleted(asset, profit, premium);
        return true;
    }

    function withdraw(address token) external onlyOwner {
        uint256 bal = IERC20Generic(token).balanceOf(address(this));
        if (bal > 0) {
            if (!IERC20Generic(token).transfer(owner, bal)) revert TransferFailed();
        }
        emit Withdraw(token, bal);
    }
}
