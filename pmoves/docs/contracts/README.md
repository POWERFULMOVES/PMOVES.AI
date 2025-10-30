# Food Cooperative Smart Contracts

This guide documents the Hardhat workspace at [`pmoves/contracts/solidity`](../../contracts/solidity) that prototypes the Food-USD and GroToken flows described in the [Food Cooperative & Group Buying System – Tokenomics & Smart Contract Design (v2.0)](../../../CATACLYSM_STUDIOS_INC/ABOUT/Food%20Cooperative%20&%20Group%20Buying%20System%20%E2%80%93%20Tokenomics%20&%20Smart%20Contract%20Design%20(v2.0).md) brief. It also aligns deployment expectations with the brand governance roadmap outlined in the [Cataclysm Studios Platform Vision & Brand Identity](../../../CATACLYSM_STUDIOS_INC/ABOUT/Cataclysm%20Studios%20Platform%20Vision%20%26%20Brand%20Identity.md).

## Workspace Overview

The workspace ships the following core contracts:

- **FoodUSD** – Mintable/burnable stablecoin controlled by the cooperative treasury. Used to escrow funds for group purchases and disburse supplier payments.
- **GroToken** – Governance and incentive token issued by the treasury. GroToken can be locked in the vault to obtain ve-style voting power.
- **GroVault** – Time-locked staking vault that implements the quadratic voting multiplier \(\(1 + 0.5 \times (T-1)\)\) described in the tokenomics brief. Supports deposits, duration extensions, and withdrawals after unlock.
- **CoopGovernor** – Quadratic voting governor that consumes GroVault power, tracks per-proposal voting costs, enforces quorum thresholds, and emits execution events for downstream automation.
- **GroupPurchase** – Pooling contract for FoodUSD contributions. Finalizes purchases when targets are met, or allows refunds after deadlines expire.

JavaScript tests under [`test/`](../../contracts/solidity/test) exercise representative staking, quadratic voting, and group-buy scenarios using projections from the v2.0 model.

## Local Development

1. `cd pmoves/contracts/solidity`
2. `npm install`
3. `npm test`

The test suite provisions sample wallets, locks GroToken balances across 1–4 year intervals, and validates:

- Quadratic voting costs vs available voting power (including over-allocation guards).
- Proposal execution gating via quorum thresholds.
- Group purchase execution and refund flows, ensuring supplier disbursement and contributor safety.

Solidity version `0.8.24` is configured with optimizer enabled (200 runs). All contracts import OpenZeppelin 5.x libraries for ERC-20 primitives and math helpers.

## Deployment Checklist

| Phase | Actions | Notes |
| --- | --- | --- |
| **Testnet rehearsal** | Deploy FoodUSD, GroToken, GroVault, CoopGovernor, and GroupPurchase to a public testnet (e.g., Sepolia). Verify contract addresses, initialize governor thresholds, and mint seed supplies to cooperative signers. | Use Hardhat networks configuration overrides (`--network sepolia`) and persist deployment artifacts under `deployments/` for reproducibility. |
| **Treasury initialization** | Assign treasury multisig as the owner of FoodUSD and GroToken. Pre-authorize GroVault to pull GroToken via `approve`. Seed test participants for quadratic voting calibration. | Align signer set with cooperative governance in the brand blueprint to maintain continuity between on-chain and off-chain actors. |
| **Group purchase pilots** | Run capped-value pilots with pre-vetted suppliers. Exercise contribution, execute, and refund paths while mirroring state into Supabase for analytics. | See Supabase integration plan below for event capture. |
| **Production launch readiness** | Complete external audit, configure Safe modules for contract upgrades (if required), and publish immutable ABIs + deployment metadata in this repo. | Document upgrade policies and parameter management in `pmoves/docs/contracts/CHANGELOG.md` (to be added when parameters change). |

## Supabase & Telemetry Integration

To align with the governance observability strategy in the branding blueprint:

- Emit Hardhat tasks (or future off-chain indexers) that capture `ProposalCreated`, `VoteCast`, `ProposalExecuted`, `OrderCreated`, `OrderExecuted`, and `RefundClaimed` events.
- Stream decoded events into Supabase tables (`dao_proposals`, `dao_votes`, `group_orders`) via the existing telemetry ingestion pipeline (`pmoves/services/publisher/` + Supabase functions). Ensure table schemas record transaction hashes, block timestamps, and cooperative member IDs so dashboards can join on community records.
- Surface aggregated voting power vs spending charts in Supabase to demonstrate the quadratic deterrence effects referenced in the tokenomics projections.

## Audit & Risk Considerations

- **Vault math correctness** – Verify integer square root logic and multiplier scaling during audit to avoid precision loss or overflow. Unit tests cover representative values, but independent reviewers should fuzz extreme lock sizes.
- **Re-entrancy & fund safety** – GroupPurchase transfers FoodUSD via `transfer`. Because FoodUSD is an ERC-20, audit for hooks or malicious tokens before allowing third-party stablecoins. Consider adding re-entrancy guards if adapting to ERC-777 style assets.
- **Governance griefing** – CoopGovernor tracks per-proposal voting costs but does not penalize abstention. Model griefing scenarios (e.g., repeated zero votes) and extend contracts with spend decay if needed.
- **Upgrade & ownership controls** – Treasury owners must secure FoodUSD/GroToken mint permissions. Document Safe transaction templates for supply adjustments and emergency parameter updates.
- **Compliance alignment** – Coordinate stablecoin custody/legal review per Section 6 of the tokenomics brief before mainnet deployment. Keep KYC/AML operations off-chain but auditable.

## Next Steps

- Backfill Supabase schema documentation once telemetry tables are provisioned.
- Model cross-industry adaptations (energy, healthcare, education) by parameterizing GroVault multipliers and GroupPurchase deadlines as suggested in the v2.0 projections.
- Capture audit outputs and remediation notes in this directory when third-party reviews are complete.

For broader governance and brand messaging context, continue syncing with the [Cataclysm Studios Platform Vision & Brand Identity](../../../CATACLYSM_STUDIOS_INC/ABOUT/Cataclysm%20Studios%20Platform%20Vision%20%26%20Brand%20Identity.md) document.
