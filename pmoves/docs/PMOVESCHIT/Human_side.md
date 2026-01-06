# CHIT Attribution System - Human Guide

Welcome to the PMOVES CHIT (Context-Hybrid Information Token) attribution system. This guide explains how your contributions to the ToKenism cooperative are tracked, weighted, and verified.

## What is CHIT?

CHIT is our system for **fair attribution** - making sure everyone gets credit for what they contribute to the cooperative economy. Whether you're spending FoodUSD at local grocers, staking your GroTokens, or voting on governance proposals, every action is recorded and attributed to you.

### Why Attribution Matters

In traditional systems, your contributions might go unnoticed. CHIT changes that by:

- **Recording every action** - Spending, staking, voting, group purchases
- **Weighting fairly** - Larger contributions get proportionally more weight
- **Proving ownership** - Cryptographic proofs verify your contributions
- **Enabling rewards** - Attribution feeds into reward distribution

## How Your Contributions Are Weighted

### The Dirichlet Distribution (In Plain English)

Imagine a pie representing all contributions in a category (like "groceries"). Each member's slice is sized based on how much they contributed.

**Key principles:**

1. **More contribution = larger slice** - If you spend $100 and someone else spends $50, your slice is roughly twice as large
2. **Everyone starts with something** - Even new members get a small base slice (smoothing)
3. **Recent activity counts more** - Contributions gradually decay over time, so staying active matters
4. **Slices always total 100%** - The math guarantees fair proportional weighting

### Example

```
Week 1 Grocery Contributions:
- Alice: $150 (slice: 45%)
- Bob: $100 (slice: 30%)
- Carol: $85 (slice: 25%)
Total: $335 (100%)
```

Alice contributed the most, so she gets the largest attribution weight for that week's grocery category.

## Understanding Your CGP (CHIT Geometry Packet)

Each week, the system generates a **CGP document** - a snapshot of all attributions. Think of it like a weekly report card for the cooperative.

### What's in a CGP?

| Component | What It Means |
|-----------|---------------|
| **Super Nodes** | Major categories (GroToken, FoodUSD, Staking, etc.) |
| **Constellations** | Groups of related activities |
| **Points** | Individual attribution records |
| **Attribution** | Your weighted contributions |
| **Merkle Root** | Cryptographic proof the data hasn't been tampered with |

### Reading Your Attribution

```
Attribution: groceries (Week 5)
  Address: 0xYOUR_ADDRESS
  Weight: 0.32 (32%)
  Raw Contribution: $150.00
  Action: spending
```

This means you contributed 32% of that week's grocery spending, with a raw amount of $150.

## Verifying Your Attribution

One of CHIT's most powerful features is **verifiable proofs**. You can mathematically prove your contributions without trusting anyone.

### What is a Merkle Proof?

A Merkle proof is like a receipt that can be verified against a public "root hash." If the proof checks out, your attribution is guaranteed to be authentic.

```
Your Proof:
  CHIT ID: chit-1234-abcd-5678
  Leaf Hash: 0xabc123...
  Merkle Root: 0xdef456...
  Path: [0x..., 0x..., 0x...]
```

### How to Verify

1. **Find the Merkle Root** - Posted on-chain or in the weekly CGP
2. **Use our verification tool** - Provide your CHIT ID and proof
3. **Get confirmation** - Tool reports "Valid" if your attribution is authentic

## Types of Attributed Actions

| Action | Description | Attribution Category |
|--------|-------------|---------------------|
| **token_received** | Receiving GroToken rewards | grotoken |
| **spending** | Using FoodUSD at merchants | Category-specific (groceries, utilities, etc.) |
| **group_contribution** | Participating in group purchases | grouppurchase |
| **staking** | Locking GroTokens in vault | staking |
| **voting** | Participating in governance | governance |
| **loyalty_earned** | Earning loyalty points | loyalty |
| **reward_claimed** | Claiming reward distributions | rewards |

## Swarm Optimization - How We Improve

The cooperative tracks key metrics to optimize for better outcomes:

| Metric | Target | What It Means |
|--------|--------|---------------|
| **Gini Coefficient** | < 0.30 | Wealth inequality measure (lower = more equal) |
| **Poverty Rate** | < 10% | Members below poverty threshold |
| **Participation Rate** | > 70% | Active member engagement |
| **Fitness Score** | Maximize | Overall cooperative health (0-1 scale) |

Your attributions contribute to these metrics. When the cooperative does well, everyone benefits through better reward distributions.

## Frequently Asked Questions

### Q: How often are attributions recorded?
**A:** Every action is recorded in real-time. Weekly CGP documents summarize all attributions.

### Q: Can I dispute my attribution?
**A:** Yes. Contact cooperative governance with your CHIT ID and they can investigate using the Merkle proofs.

### Q: Does larger spending mean larger rewards?
**A:** Not directly. Attribution weight influences reward calculations, but other factors (staking, governance participation) also matter.

### Q: What happens if I'm inactive?
**A:** Your past attributions gradually decay over time. Stay active to maintain your attribution weight.

### Q: Is my data private?
**A:** Your address and contributions are recorded, but the Merkle proof system means only you can prove your specific attributions. Others can see totals but not individual details without your proof.

### Q: How do I see my current attribution?
**A:** Use the cooperative dashboard or query the CGP API with your address.

## Getting Help

- **Dashboard**: View your attributions at `dashboard.pmoves.ai/attribution` *(coming soon)*
- **Discord**: Ask questions in `#tokenism-support`
- **Documentation**: Technical details at `docs.pmoves.ai/chit` *(coming soon)*

---

*This guide is part of the PMOVES ToKenism cooperative documentation.*
*Version: 1.0.0 | Schema: chit.cgp.v0.2 | Updated: December 2025*
