# Telegram Premium Subscription: Comprehensive Research Report (2025–2026)

> Research compiled April 2026. All figures are exact where source-confirmed; gaps are explicitly noted.

---

## Executive Summary

Telegram Premium, launched June 19, 2022, is a single-tier subscription that doubles or triples most platform limits, removes download speed restrictions, provides unlimited voice-to-text transcription, and unlocks cosmetic customization features. As of 2025–2026, the subscription costs $4.99/month in the US (€5.49 EU, £4.99 UK) with an annual plan at $35.99 US. Premium users receive 4 boost votes assignable to channels and groups. The boost system (levels 1–100) unlocks progressive features including stories, custom reactions, wallpapers, and at level 50, the ability to disable sponsored messages. New Premium-exclusive features in 2025 include Star Messages (paywalled inbox), public post search, Premium-exclusive limited gifts, and custom emoji in folder names. No 'Premium Lite' tier exists. Bot API integration provides premium user identification and custom emoji support subject to bot owner Premium status or Fragment username ownership.

---

## Section 1: User-Level Premium Features

### 1.1 Core Limit Comparison Table

| Feature | Free Users | Premium Users | Source |
|---------|-----------|---------------|--------|
| **File upload size** | 2 GB | 4 GB | [1][2] |
| **Download speed** | Standard (capped) | No speed limit / ~4x faster [3] | [2][4] |
| **Message editing time** | 48 hours | 48 hours (same as free) | [5] |
| **Voice-to-text transcriptions** | 2 per week, max 5 min per message | Unlimited, no duration limit | [6] |
| **Custom emoji per message** | Saved Messages only; >100 replaced with standard emoji | Up to 100 per message, any chat | [6][7] |
| **Chat folders** | 10 | 30 | [6][8] |
| **Chats per folder** | 100 | 200 | [6] |
| **Pinned chats in a folder** | 100 | 200 | [6] |
| **Public folders** | 2 | 20 | [6] |
| **Items per public folder** | 100 | 200 | [6] |
| **Folder links per public folder** | 3 | 10 | [6] |
| **Pinned chats (main list)** | 5 chats/channels + 5 secret chats | 10 chats/channels | [6][9] |
| **Pinned messages per chat** | Unlimited | Unlimited | [6] |
| **Groups + channels to join** | 500 combined | 1,000 combined | [6][2] |
| **Favorite stickers** | 5 | 10 | [6][2] |
| **Favorite GIFs** | 200 | 400 | [6][2] |
| **Accounts (on official clients)** | 3 | 4–6 (varies by app) | [6][2] |
| **Public usernames (per account)** | 10 (including groups) | 20 (including groups) | [6] |
| **Saved messages capacity** | Unlimited | Unlimited | [6] |
| **Emoji packs installable** | 200 | 200 | [6] |
| **Custom emoji in folder names** | Not available | Available | [10] |

### 1.2 Feature Notes

**File upload size:** Premium users can upload files up to 4 GB. Any user (free or Premium) can download 4 GB files uploaded by Premium users. Free users are capped at 2 GB uploads [1][2].

**Download speed:** Telegram describes this as 'fastest possible download speeds' with no `FLOOD_PREMIUM_WAIT_X` errors for Premium. Third-party sources describe it as '~4x faster' compared to free users. No exact Mbps figure is published by Telegram — the description is 'no download speed limits from Telegram's side' [2][4].

**Message editing time:** 48 hours for ALL users (Premium and free). This is NOT a Premium-specific feature. Unlimited in Saved Messages and for admins with pinning rights [5].

**Voice-to-text:** Free users receive 2 transcriptions per week with a maximum duration of 5 minutes per voice message. Premium users have unlimited transcriptions with no per-message duration cap [6]. In groups at boost level 6+, all members (including free) get unlimited transcription [11].

**Custom emoji:** Premium users get access to 10 initial custom emoji packs containing 500+ Premium animated emoji at launch, with countless more created by the community. Both free and Premium users can install up to 200 emoji packs. The key difference: free users can only SEND custom emoji to Saved Messages (and more than 100 per message get replaced with standard emoji), while Premium users can send up to 100 custom emoji per message in any chat [7][6].

**Chat folders discrepancy:** The original June 2022 launch blog stated 'up to 20 chat folders' for Premium [2]. The current limits reference (limits.tginfo.me, updated 2026) states 30 folders. This indicates Telegram increased the folder limit from 20 to 30 at some point between 2022 and 2026; the exact date of this increase was not found in any source [6][8].

**Emoji status duration:** Premium users can set an animated emoji status displayed next to their name in the chat list, profile, and groups. Users 'press and hold an emoji to set an animated status for a specific duration' [12]. The exact duration options (e.g., 1 hour, 8 hours, 1 day, 7 days) were NOT found in any official or third-party source. This is a confirmed data gap.

### 1.3 Premium-Exclusive Features (Non-Limit)

| Feature | Description |
|---------|-------------|
| **Premium badge** | Star icon next to name in chat and member lists |
| **Animated emoji status** | Custom animated emoji replacing the Premium badge [12] |
| **Animated profile pictures** | Video-based profile pictures |
| **Premium sticker packs** | Exclusive animated sticker sets [2] |
| **Exclusive reactions** | Additional reaction emoji not available to free users [13] |
| **App icons** | Custom app icons for iOS/Android [2] |
| **No ads** | Removal of sponsored messages in private chats [2] |
| **Advanced chat management** | Translated messages without 'translated by' tag [2] |
| **Voice message waveform visualization** | Premium users see a voice waveform; free users see a simplified waveform [2] |
| **Star Messages (private chats)** | Charge 1–10,000 Telegram Stars per incoming message from non-contacts [14] |
| **Public post search** | 'Posts' tab in search showing results from public channels [15] |
| **Premium-exclusive limited gifts** | Limited-edition gifts restricted to Premium users [15] |

---

## Section 2: Group/Channel Boost System

### 2.1 How Boosts Work

- Each Premium subscription provides **4 boosts** [11]
- Boosts are independently assignable to any channel or group
- A single Premium user can split their 4 boosts across multiple channels/groups simultaneously (e.g., 2 to a channel + 2 to a group)
- Boosts last as long as the Premium subscription remains active
- If Premium expires, those 4 boosts are removed from the assigned channel/group
- Gifting Premium via giveaway gives all 4 boosts to the hosting channel immediately [11]
- Direct person-to-person gifting of Premium gives the sender **3 boosts** assignable to their channel [16]

### 2.2 Boost Requirement Formula

The number of boosts needed per level **scales with subscriber count**. There is no single fixed number per level.

**Coefficient (c)** = `floor(subscribers / 250) + 1`

| Subscriber Range | Coefficient |
|:-----------------|:------------|
| 1–249 | 1 |
| 250–499 | 2 |
| 500–749 | 3 |
| 750–999 | 4 |
| 1,000–1,249 | 5 |
| 5,000–5,249 | 21 |
| 10,000–10,249 | 41 |

**Boosts needed per level** (current system, late 2024+):
- Levels 1–8: `ceil(c × level / 2)`
- Level 9: `c × 7`
- Level 10+: `c × level`

### 2.3 Example: Small Channel (1–249 subscribers, c=1)

| Level | Boosts for This Level | Cumulative Boosts |
|:-----:|:---------------------:|:------------------:|
| 1 | 1 | 1 |
| 2 | 1 | 2 |
| 3 | 2 | 4 |
| 4 | 2 | 6 |
| 5 | 3 | 9 |
| 6 | 3 | 12 |
| 7 | 4 | 16 |
| 8 | 4 | 20 |
| 9 | 7 | 27 |
| 10 | 10 | 37 |
| 20 | 20 | 177 |
| 50 | 50 | 527 |

### 2.4 Example: 1,000-Subscriber Channel (c=5)

| Level | Boosts for This Level | Cumulative Boosts |
|:-----:|:---------------------:|:------------------:|
| 1 | 3 | 3 |
| 2 | 5 | 8 |
| 3 | 8 | 16 |
| 4 | 10 | 26 |
| 5 | 13 | 39 |
| 6 | 15 | 54 |
| 7 | 18 | 72 |
| 8 | 20 | 92 |
| 9 | 35 | 127 |
| 10 | 50 | 177 |
| 20 | 100 | 1,177 |
| 50 | 250 | 6,677 |

### 2.5 Feature Unlock Table (Levels 1–10)

Source: Official Telegram Bot FAQ (`core.telegram.org/bots/sandbox-premium-faq-channels`) [11]

| Level | Stories/Day | Custom Reactions | Name Colors | Link/Quote Styles | New Feature Unlocked |
|:-----:|:-----------:|:----------------:|:-----------:|:-----------------:|:---------------------|
| 1 | 1 | 1 | 7 | 7 | Stories, reactions, name colors, basic link styles |
| 2 | 2 | 2 | 7 | 14 | +7 link/quote styles |
| 3 | 3 | 3 | 7 | 21 | +7 link/quote styles (cap reached at 21) |
| 4 | 4 | 4 | 7 | 21 | Custom logos for links/quotes (channel) / Custom emoji sticker set (group) |
| 5 | 5 | 5 | 7 | 21 | 8 colors for channel cover |
| 6 | 6 | 6 | 7 | 21 | 16 colors for channel cover (expanded) / Unlimited voice transcription for non-Premium (group) |
| 7 | 7 | 7 | 7 | 21 | Custom logos for channel cover |
| 8 | 8 | 8 | 7 | 21 | 1,000+ emoji statuses |
| 9 | 9 | 9 | 7 | 21 | 8 fill channel/group backgrounds (wallpapers) |
| 10 | 10 | 10 | 7 | 21 | Custom channel/group backgrounds (any image) |

### 2.6 Higher Levels

| Level Range | Stories/Day | Custom Reactions | New Features |
|:-----------:|:-----------:|:----------------:|:-------------|
| 11–49 | N (same as level number) | N (same as level number) | NO new feature unlocks — only +1 story/day and +1 reaction per level |
| 50 | 50 | 50 | **Disable sponsored/official Telegram messages** (channels only) |
| 51–100 | N | N | NO new features beyond +1 story/reaction |
| 100 (max) | 100 | 100 | Maximum level — no further progression |

### 2.7 Features With Undocumented Exact Boost Levels

These exist in the Telegram API as config parameters but their exact numerical boost level requirements are **not publicly documented** — they are server-side values Telegram can change without notice:

| Feature | API Config Parameter | Status |
|---------|---------------------|--------|
| Autotranslation | `channel_autotranslation_level_min` | Exact value not published |
| Message accent color palette | `help.peerColorOption.min_level` | Per-palette (varies by color) |
| Profile cover icon/logo | `channel_profile_bg_icon_level_min` | Exact value not published |
| Chat theme background | `min_chat_theme_background_boost_level_` | Exact value not published |
| Profile background custom emoji | `min_profile_background_custom_emoji_boost_level_` | Exact value not published |
| Reply header custom emoji | `min_background_custom_emoji_boost_level_` | Channel only; exact value not published |

### 2.8 NOT Boost Features (Common Misconceptions)

- **Topics:** Base supergroup feature available at 200+ members, NOT boost-gated [11]
- **Slowmode bypass:** Boost level affects slowmode limits internally but is not a discrete unlock
- **Anti-troll protection / moderator skins:** Mentioned jokingly in Telegram's blog — not real features

---

## Section 3: Bot API Premium Integration

### 3.1 Bot Operator Premium Impact

| Question | Answer |
|----------|--------|
| Does bot operator's Premium status affect bot capabilities? | **Partially.** Bot owners with Premium can send custom emoji in messages directly sent by the bot to private, group, and supergroup chats. Without Premium, bots can only use custom emoji if the bot has a Fragment-purchased username [17]. |
| Can bots access Premium user upload/download limits? | **No.** Bots are limited to 50 MB file uploads regardless of bot owner's Premium status. The 4 GB upload limit is a client-side feature for human Premium accounts [18]. |
| Do Premium subscribers in a bot's group unlock features for the bot? | **No direct bot capability unlock.** However, Premium subscribers can boost the group, and group boost levels (e.g., level 6 for transcription) apply to all members including bots. The bot itself does not gain API-level Premium features from having Premium members. |

### 3.2 Bot API Premium-Related Fields

Complete changelog of all premium-related Bot API additions:

| Date | Field/Class | Type | Description |
|------|-------------|------|-------------|
| June 20, 2022 | `custom_emoji_id` on `MessageEntity` | Field | String identifier for 'custom_emoji' type entities [17] |
| June 20, 2022 | `type` + `custom_emoji_id` on `Sticker` | Fields | Identifies premium/custom animated stickers [17] |
| Aug 12, 2022 | `icon_custom_emoji_id` on `KeyboardButton` | Field | Show custom emoji on keyboard buttons (requires bot custom emoji ability) [17] |
| Aug 12, 2022 | `icon_custom_emoji_id` on `InlineKeyboardButton` | Field | Show custom emoji on inline keyboard buttons (requires bot custom emoji ability) [17] |
| Aug 12, 2022 | `is_premium` on `WebAppUser` | Field | Boolean indicating if the Web App user has Premium [17] |
| Aug 12, 2022 | `accent_color_id` on `Chat` | Field | Chat accent color (Premium users set these on groups) [17] |
| Aug 12, 2022 | `background_custom_emoji_id` on `Chat` | Field | Custom emoji on chat background [17] |
| Aug 12, 2022 | `profile_accent_color_id` on `Chat` | Field | Profile accent color for boosted chats [17] |
| Aug 12, 2022 | `profile_background_custom_emoji_id` on `Chat` | Field | Custom emoji on profile background [17] |
| Feb 16, 2024 | `custom_emoji_sticker_set_name` on `Chat` | Field | Name of custom emoji sticker set for boosted groups [17] |

### 3.3 Bot Custom Emoji Access Requirements

Bots can use custom emoji in messages under **either** of these conditions:
1. The bot's owner has an active Telegram Premium subscription [17]
2. The bot has a username purchased on Fragment (the TON blockchain username marketplace) [19]

Without either condition, custom emoji entities in bot messages are silently ignored or replaced.

### 3.4 `premium_inline_query_results` Field

The original task requested documentation of a `premium_inline_query_results` field. This field was **NOT found** in the Bot API changelog, the current Bot API documentation, or any third-party documentation. It may be a MTProto-layer field not exposed in the Bot API, or it may not exist. Explicitly flagged as not found.

### 3.5 Bot Message Rate Limits (Premium-Adjacent)

While not a Premium feature per se, increased bot rate limits were introduced October 2024 and are paid via Telegram Stars:
- Free bot rate: 30 messages/second
- Increased limit: up to 1,000 messages/second at 0.1 Star per message above the free tier [20]
- Initially available for channels with thousands of subscribers

---

## Section 4: 2025–2026 Changes and Additions

### 4.1 New Premium-Exclusive Features

| Feature | Date Added | Description | Source |
|---------|-----------|-------------|--------|
| Star Messages (private chats) | Mar 7, 2025 | Charge 1–10,000 Stars per incoming message from non-contacts. Settings > Privacy > Messages. Allow exceptions for specific users/group members. Instant refund with one tap. | [14] |
| Public Post Search | Feb 2025 | 'Posts' tab in search shows results from public channels. Premium-only. | [15] |
| Premium-Exclusive Limited Gifts | Feb 2025 | Limited-edition gifts restricted to Premium users with limited purchase count per person. | [15] |
| Custom Emoji in Folder Names | Jan 1, 2025 | Use animated custom emoji in chat folder names. Premium-only. | [10] |

### 4.2 Notable Free Features Added (2025)

| Feature | Date Added | Description | Source |
|---------|-----------|-------------|--------|
| Collectible Gifts | Jan 1, 2025 | Standard gifts upgradable to NFT collectibles on TON blockchain with custom appearances and random traits. Upgrade cost: 'small amount of Stars.' | [10] |
| Reactions for Service Messages | Jan 1, 2025 | React to gifts, joins, video chats, calls, profile photo changes, chat backgrounds, giveaways. | [10] |
| Message Search Filters | Jan 1, 2025 | Filter search by private chats, group chats, or channels. | [10] |
| Third-Party Verification Icons | Jan 1, 2025 | Official services can assign extra verification icons to prevent scams. | [10] |
| Story Albums | Feb 2025 | Organize stories into albums on profile/channel. | [15] |
| Gift Collections | Feb 2025 | Group gifts into themed collections with granular filters. | [15] |
| Profile Rating | Feb 2025 | Numerical badge based on total Stars transaction volume. | [15] |
| Pinned Gifts | Mar 7, 2025 | Pin up to 6 gifts to showcase on gifts tab and profile cover. | [14] |
| Gift Premium with Stars | Mar 7, 2025 | Use Star balance to gift Premium subscriptions to friends. | [14] |
| Contact Confirmation | Mar 7, 2025 | Detailed info page for first-time messages from unknown users (country, shared groups, join date, username history). | [14] |
| Telegram Gateway 2.0 | Mar 7, 2025 | Business phone verification at $0.01/verification with max delivery time and auto-refund. | [14] |
| Chromecast Streaming | Mar 7, 2025 | Stream videos to Chromecast on Android. | [14] |

### 4.3 Features Moved Between Tiers

| Feature | Change | Date | Notes |
|---------|--------|------|-------|
| Voice message transcription | Premium → partially free | Dec 2023 | Free users get 2 transcriptions/week (max 5 min). Still unlimited for Premium and in boosted groups (level 6+). |

**No additional features were moved from Premium to free, or from free to Premium, in 2024, 2025, or 2026 based on available sources.** Telegram's stated policy is that all pre-Premium features remain free; new features are sometimes introduced as Premium-exclusive but rarely demoted.

### 4.4 Premium Lite

**Telegram Premium Lite does NOT exist.** Searched official FAQ, blog posts, Wikipedia, Android Authority, Android Police, and multiple third-party sources. No official announcement, leaked beta, or credible rumor of a lite tier in 2025 or 2026 was found. Only one subscription tier exists: Telegram Premium.

### 4.5 Gifting Premium

| Method | Durations Available | Boost Allocation | Notes |
|--------|---------------------|------------------|-------|
| **Direct person-to-person** | 3 months, 6 months, 12 months (at discount vs regular pricing) | Sender receives **3 boosts** assignable to their channel | Open recipient's profile > ⋮ > Gift Premium. Delivered as animated gift box. [16] |
| **Channel/group giveaway** | Same durations (set by admin) | Admin receives all **4 boosts** per Premium given away | Winners selected randomly from members/followers. [11] |
| **Stars-based gifting** (new Mar 2025) | Not specified | Not specified | Use Star balance instead of cash. Profile > ⋮ > Send a Gift. [14] |

### 4.6 Star Monetization Integration

| Aspect | Details |
|--------|---------|
| **Star Messages (Premium)** | Premium users charge 1–10,000 Stars per incoming private message from non-contacts. Stars pricing: $0.02/Star via @PremiumBot [14]. |
| **Star Messages (Groups)** | Free feature — group admins enable 'Charge Stars for Messages' in Permissions section [14]. |
| **Gift Premium with Stars** | Use accumulated Star balance to gift Premium subscriptions [14]. |
| **Bot increased limits** | Up to 1,000 msg/sec at 0.1 Star per message above free tier [20]. |
| **Ad revenue sharing** | Developers earn 50% of Telegram Ads revenue; Stars can fund advertising [20]. |
| **Star withdrawal** | $0.013/Star via TON (Fragment), available 21 days after receiving. Reinvestment in Telegram Ads: $0.02/Star (subsidized rate). Telegram's cut: less than 5% [20]. |

### 4.7 Telegram Stars Pricing

| Stars | Price (USD, via @PremiumBot) | Price per Star |
|------:|:-----------------------------:|:-------------:|
| 50 | $1.00 | $0.020 |
| 100 | $2.00 | $0.020 |
| 250 | $5.00 | $0.020 |
| 500 | $10.00 | $0.020 |
| 1,000 | $20.00 | $0.020 |
| 2,500 | $50.00 | $0.020 |

Prices are $0.02/Star consistently via @PremiumBot. App Store/Google Play add approximately 30% markup (e.g., 100 Stars via App Store = $2.39 vs $2.00 via @PremiumBot). Packs range from 50 to 2,500 Stars [20].

---

## Section 5: Pricing

### 5.1 Primary Markets

| Region | Monthly | Annual | Source |
|--------|:-------:|:------:|--------|
| United States | $4.99 | $35.99 | [3][21] |
| European Union | €5.49 | Not confirmed | [3][21] |
| United Kingdom | £4.99 | Not confirmed | [3][21] |

### 5.2 Regional Pricing Examples

| Region | Monthly (USD equiv.) | Source |
|--------|:--------------------:|--------|
| India | $2.49–$2.99 (₹219) | [3] |
| Turkey | $1.99–$2.49 (110 TRY) | [3] |
| Colombia | $3.41 (14,500 COP) | [22] |
| Colombia (annual) | $26.23 (111,500 COP) | [22] |

### 5.3 Pricing Notes

- Pricing is based on the country code of the phone number associated with the Telegram account [1]
- Purchase via @PremiumBot is cheaper than App Store/Google Play due to the absence of the ~30% platform commission
- Regional pricing varies significantly — some regions pay less than half the US price
- Gift Premium (3/6/12 months) is offered at a discount compared to standard subscription pricing [16]

---

## Confirmed Data Gaps

The following exact figures could NOT be found across all sources consulted (official Telegram pages, API documentation, blog posts, FAQ, third-party tech news, community references):

1. **Emoji status duration options:** Premium users can set emoji status 'for a specific duration' but the exact options (e.g., 1 hour, 8 hours, 1 day, 7 days, permanent) are not documented anywhere.
2. **`premium_inline_query_results` Bot API field:** Referenced in the original task but not found in Bot API changelog, current API docs, or third-party documentation. May be a MTProto-layer field not exposed in Bot API, or may not exist.
3. **Exact date folder limit increased from 20 to 30:** The original June 2022 blog stated 20 folders for Premium; the current limits reference states 30. The date of this increase is unknown.
4. **Exact Star pricing for gifting Premium:** The Stars-based gifting feature (March 2025) was announced but the exact Star cost for 3/6/12 month gifts was not specified in any source.
5. **Premium account limit variance:** Premium allows '4–6 accounts depending on the app' but the exact per-app breakdown was not documented.
6. **Exact boost level for autotranslation, accent color palettes, profile cover icons, chat theme backgrounds:** These exist as server-side config parameters but their values are not publicly documented.

---

## Sources

[1] Telegram Premium FAQ — https://telegram.org/faq_premium
[2] 700 Million Users and Telegram Premium (blog) — https://telegram.org/blog/700-million-and-premium
[3] TuttoDigitale: Costi di Telegram Premium nel Mondo — https://tuttodigitale.net/mobiletech/costo-telegram-premium/
[4] gHacks: Telegram Premium Subscription Features — https://www.ghacks.net/2022/06/20/telegram-premium-subscription-features/
[5] Free Press Journal: WhatsApp vs Telegram editing comparison — https://www.freepressjournal.in/business/whatsapp-users-can-now-edit-messages-within-15-minutes-after-they-are-sent
[6] Telegram Limits (tginfo.me) — https://limits.tginfo.me/en
[7] Telegram Emoji Platform blog — https://telegram.org/blog/custom-emoji
[8] Telegram Premium FAQ (folder reference) — https://telegram.org/faq_premium
[9] Telegram Bugs: Pin more chats — https://bugs.telegram.org/c/64
[10] Collectible Gifts and More (blog, Jan 2025) — https://telegram.org/blog/collectible-gifts-and-more
[11] Telegram Bot FAQ: Channel Boosts — https://core.telegram.org/bots/sandbox-premium-faq-channels
[12] HT Tech: Telegram Emoji Statuses — https://tech.hindustantimes.com/photos/telegram-emoji-statuses-infinite-reactions-rolled-out-know-how-to-use-71663497381876.html
[13] Infinite Reactions, Emoji Statuses blog — https://telegram.org/blog/infinite-reactions-statuses
[14] Star Messages, Pinned Gifts, Gateway 2.0 (blog, Mar 2025) — https://telegram.org/blog/star-messages-gateway-2-0-and-more
[15] Public Post Search, Story Albums (blog, Feb 2025) — https://telegram.org/blog/post-search-story-albums-and-more
[16] Telegram Premium gifting reference — https://t.me/premium/135
[17] Bot API Changelog — https://core.telegram.org/bots/api-changelog
[18] Telegram Bots FAQ (file size limit) — https://core.telegram.org/bots/faq
[19] Stack Overflow: How to use custom emoji in telegram bot — https://stackoverflow.com/questions/79058032/how-to-use-custom-emoji-in-telegram-bot
[20] Durov's Code: About Telegram Stars — https://durovscode.com/about-telegram-stars
[21] Invitemember Blog: Telegram Premium Features — https://blog.invitemember.com/telegram-premium-all-about-features-price-and-benefits/
[22] Reddit: Price of Telegram Premium in your country — https://www.reddit.com/r/Telegram/comments/1fcqdkd/price_of_telegram_premium_in_your_country/
[23] Telegram API: Premium — https://core.telegram.org/api/premium
[24] Telegram API: Boost — https://core.telegram.org/api/boost
[25] Telegram API: Files — https://core.telegram.org/api/files
[26] tginfo.me: New Boost Conditions — https://tginfo.me/new-levels-ranking-en/
[27] Dynamic Video Quality and More (blog, Oct 2024) — https://telegram.org/blog/dynamic-video-quality-and-more
[28] Android Police: Telegram New Premium Perks — https://www.androidpolice.com/telegram-new-premium-perks/
