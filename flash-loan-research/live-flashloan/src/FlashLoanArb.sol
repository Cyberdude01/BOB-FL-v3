// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

interface IAavePool {
    function flashLoanSimple(
        address receiverAddress,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

interface IFlashLoanSimpleReceiver {
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool);
}

interface IUniV2LikeRouter {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);
}

/// @notice Minimal Aave V3 flash-loan arbitrage executor.
/// @dev This contract is deliberately conservative. If the route is not profitable
///      after paying the Aave premium, the whole transaction reverts. That means the
///      only loss from a bad attempt is gas, not principal.
contract FlashLoanArb is IFlashLoanSimpleReceiver {
    address public immutable owner;
    IAavePool public immutable pool;

    error NotOwner();
    error NotPool();
    error BadInitiator();
    error NotProfitable(uint256 finalBalance, uint256 owed, uint256 minProfit);
    error TransferFailed();

    struct ArbParams {
        address routerA;
        address routerB;
        address tokenBorrow;
        address tokenMid;
        uint256 minMidOut;
        uint256 minFinalOut;
        uint256 minProfit;
        uint256 deadline;
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
        pool = IAavePool(_pool);
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

        IERC20(p.tokenBorrow).approve(p.routerA, amount);
        address[] memory pathA = new address[](2);
        pathA[0] = p.tokenBorrow;
        pathA[1] = p.tokenMid;
        IUniV2LikeRouter(p.routerA).swapExactTokensForTokens(
            amount,
            p.minMidOut,
            pathA,
            address(this),
            p.deadline
        );

        uint256 midBalance = IERC20(p.tokenMid).balanceOf(address(this));
        IERC20(p.tokenMid).approve(p.routerB, midBalance);
        address[] memory pathB = new address[](2);
        pathB[0] = p.tokenMid;
        pathB[1] = p.tokenBorrow;
        IUniV2LikeRouter(p.routerB).swapExactTokensForTokens(
            midBalance,
            p.minFinalOut,
            pathB,
            address(this),
            p.deadline
        );

        uint256 owed = amount + premium;
        uint256 finalBalance = IERC20(asset).balanceOf(address(this));
        if (finalBalance < owed + p.minProfit) {
            revert NotProfitable(finalBalance, owed, p.minProfit);
        }

        IERC20(asset).approve(address(pool), owed);
        uint256 profit = finalBalance - owed;
        if (profit > 0) {
            if (!IERC20(asset).transfer(owner, profit)) revert TransferFailed();
        }
        emit ArbCompleted(asset, profit, premium);
        return true;
    }

    function withdraw(address token) external onlyOwner {
        uint256 bal = IERC20(token).balanceOf(address(this));
        if (bal > 0) {
            if (!IERC20(token).transfer(owner, bal)) revert TransferFailed();
        }
        emit Withdraw(token, bal);
    }
}
