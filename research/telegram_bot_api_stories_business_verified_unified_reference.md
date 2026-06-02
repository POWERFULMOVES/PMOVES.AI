# Telegram Bot API — Stories, Business Accounts & Verified Bots: Unified Reference

> Compiled: 2026-04-25 | Sources: core.telegram.org/bots/api, web research, Bot API changelog
> Bot API version: 9.6+ | Ground truth validated against official docs

---

## Table of Contents

1. [Stories](#part-1-stories)
2. [Business Accounts](#part-2-business-accounts)
3. [Verified Bots](#part-3-verified-bots)

===========================================================================

# PART 1: STORIES

===========================================================================

§§include(/a0/usr/projects/pmoves/research/telegram_bot_api_stories_reference.md)

===========================================================================

# PART 2: BUSINESS ACCOUNTS

===========================================================================

§§include(/a0/usr/projects/pmoves/research/telegram_bot_api_business_accounts_reference.md)

===========================================================================

# PART 3: VERIFIED BOTS

===========================================================================

## 1. Overview

Telegram offers a verification badge (white tick inside blue star) for bots, channels, and groups representing organizations, public figures, or notable entities. This is distinct from the Premium badge (star icon) and is free to obtain.

---

## 2. How to Apply

**Only via @VerifyBot** — there is no BotFather command, no application form URL, no dashboard.

1. Open @VerifyBot in Telegram
2. Send your bot's `@username` or `t.me/` link
3. Follow the bot's instructions to provide verification evidence
4. Wait for manual review (several days to several weeks, no SLA)

---

## 3. Verification Requirements (3 Pathways)

At least ONE pathway must be satisfied, PLUS the universal press requirement:

### Pathway A: Multi-Platform Verification
- Verified accounts on **2+ platforms** from this list:
  - TikTok, Instagram, Facebook, YouTube, Twitter/X, VK, Snapchat
- Each verified account must have a bio/description containing a link to the Telegram entity

### Pathway B: Single Platform + Wikipedia
- 1 verified social account (from the list above) with bio link to Telegram entity
- PLUS an undisputed Wikipedia page that links to the Telegram entity

### Pathway C: Official Website
- An official organization website that publishes the Telegram link
- Website must be clearly the official web presence of the entity

### Universal Requirement (ALL pathways)
- **2+ press articles** from well-known publishers (English preferred)
- Articles must be about the entity, not just mentioning it in passing

### Accelerated Path (TON Foundation)
- 500K+ users for bots, 100K+ subscribers for channels
- Requires Mini Apps SDK integration
- Fast-tracked through TON Foundation partnership

---

## 4. Disqualification Criteria

- Fake or misleading identity
- Impersonation of other entities
- ToS violations
- Inactive bot/channel
- Name/username changes while verified (locked during verification)

---

## 5. API Fields Related to Verification

### Bot API (HTTP JSON API)
- **NO `is_verified` field exists** on the User type or Bot type
- The User type only has `is_premium` (Boolean) — this is NOT verification
- There is NO way to check verification status via Bot API

### MTProto Layer API
- `user.flags.17` — `verified` boolean on User objects
- `channel.flags.7` — `verified` boolean on Channel objects
- `chatInvite.flags.7` — `verified` boolean on ChatInvite objects
- To check verification from bot code, you MUST use MTProto libraries (Pyrogram, Telethon, etc.) — NOT Bot API

### Bot API 8.2 Methods (January 2025) — Third-Party Verification
These are NOT for standard verification status queries:

| Method | Description |
|--------|-------------|
| `verifyUser` | Verify a user (third-party verifier only) |
| `verifyChat` | Verify a chat (third-party verifier only) |
| `removeUserVerification` | Remove user verification (third-party verifier only) |
| `removeChatVerification` | Remove chat verification (third-party verifier only) |

These methods are exclusively for organizations that have been approved as third-party verifiers. They use custom icons (not blue ticks). Tapping the icon reveals who verified the entity and why.

---

## 6. Verified Badge vs Premium Badge

| Aspect | Verified Badge | Premium Badge |
|--------|---------------|---------------|
| Appearance | White tick inside blue star | Star icon next to name |
| Who gets it | Organizations, public figures (approved via @VerifyBot) | Any user (paid subscription ~$4.99/mo) |
| Can bots get it? | Yes | No — bots can ONLY get verified badges, never premium |
| Cost | Free | Paid subscription |
| Revocable | Yes (ToS violations or voluntary) | Expires if subscription lapses |
| API field | MTProto `verified` flag | Bot API `is_premium` on User type |

---

## 7. Revocation

- **Voluntary**: Send `/unverify` command to @VerifyBot
- **Involuntary**: ToS violations, impersonation, misleading identity
- Name and username are **locked** while verified — changing them requires unverification first

---

## 8. Bot vs Channel vs Group Verification

Identical requirements, identical process, identical badge, identical cost (free). No differences between entity types for verification purposes.

---

## 9. Key Facts Summary

| Fact | Detail |
|------|--------|
| Application method | @VerifyBot only |
| Cost | Completely free |
| Timeline | Several days to several weeks, no SLA, no status tracking |
| API check (Bot API) | Not possible — no field exists |
| API check (MTProto) | `user.flags.17`, `channel.flags.7` |
| Badge appearance | White tick inside blue star |
| Bots can be premium? | No — bots can only be verified, never premium |
| Third-party verification | Available since Bot API 8.2 (Jan 2025) for approved orgs |
| Name lock while verified | Yes — name/username cannot be changed |

---

*End of unified reference document*
