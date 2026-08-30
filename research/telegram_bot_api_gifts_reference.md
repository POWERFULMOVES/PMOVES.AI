# Telegram Bot API Gifts — Comprehensive Reference

> Compiled: 2025-04-25 | Sources: core.telegram.org/bots/api, python-telegram-bot v22.7, aiogram 3.27, litegram 1.0.10, tgram, pyTelegramBotAPI 4.33

---

## Table of Contents

1. [Methods](#methods)
   - [sendGift](#sendgift)
   - [getAvailableGifts](#getavailablegifts)
   - [getBusinessAccountGifts](#getbusinessaccountgifts)
   - [convertGiftToStars](#convertgifttostars)
   - [upgradeGift](#upgradegift)
   - [transferGift](#transfergift)
   - [setBusinessAccountGiftSettings](#setbusinessaccountgiftsettings)
2. [Types](#types)
   - [Gift](#gift)
   - [OwnedGift (Union Type)](#ownedgift-union-type)
   - [OwnedGiftRegular](#ownedgiftregular)
   - [OwnedGiftUnique](#ownedgiftunique)
   - [UniqueGift](#uniquegift)
   - [UniqueGiftModel](#uniquegiftmodel)
   - [UniqueGiftSymbol](#uniquegiftsymbol)
   - [UniqueGiftBackdrop](#uniquegiftbackdrop)
   - [UniqueGiftColors](#uniquegiftcolors)
   - [UniqueGiftBackdropColors](#uniquegiftbackdropcolors)
   - [GiftBackground](#giftbackground)
   - [GiftInfo](#giftinfo)
   - [UniqueGiftInfo](#uniquegiftinfo)
   - [Gifts](#gifts)
   - [OwnedGifts](#ownedgifts)
   - [AcceptedGiftTypes](#acceptedgifttypes)
3. [Gift Categories: Limited / Regular / Unique / Rare](#gift-categories)
4. [Gift-Related Message Fields](#gift-related-message-fields)
5. [Bot Restrictions on Sending Gifts](#bot-restrictions-on-sending-gifts)
6. [Business Account Gift Rights](#business-account-gift-rights)

---

## Methods

### sendGift

Sends a gift to a user. The gift is paid for using Telegram Stars from the bot's balance.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | Integer | Optional* | Unique identifier of the target user. Required if `chat_id` is not specified. |
| `chat_id` | Integer or String | Optional* | Unique identifier for the target chat. Required if `user_id` is not specified. |
| `gift_id` | String | **Yes** | Identifier of the gift to send. Obtain from `getAvailableGifts`. |
| `pay_for_upgrade` | Boolean | Optional | Pass `true` to pay for the upgrade of the gift to a unique gift. The cost is `gift.upgrade_star_count` Stars. |
| `text` | String | Optional | Text to accompany the gift. 0-128 characters. |
| `text_parse_mode` | String | Optional | Parse mode for `text` (e.g., `"HTML"`, `"MarkdownV2"`). |
| `text_entities` | Array of MessageEntity | Optional | Special entities in `text` (for custom parse modes). |

*Exactly one of `user_id` or `chat_id` must be specified.

**Returns:** `True` on success.

**Restrictions:**
- Limited gifts cannot be sent to channel chats.
- Gifts sent via `sendGift` cannot be converted to Telegram Stars by the receiver.

---

### getAvailableGifts

Returns all gifts that can be sent by the bot.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| (none) | — | — | This method takes no parameters. |

**Returns:** `Gifts` object (contains array of `Gift` objects).

---

### getBusinessAccountGifts

Returns the gifts received and owned by a managed business account.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | **Yes** | Unique identifier of the business connection. |
| `exclude_unsaved` | Boolean | Optional | Pass `true` to exclude gifts not displayed on the profile page. |
| `exclude_saved` | Boolean | Optional | Pass `true` to exclude gifts displayed on the profile page. |
| `exclude_unlimited` | Boolean | Optional | Pass `true` to exclude unlimited regular gifts. |
| `exclude_limited` | Boolean | Optional | Pass `true` to exclude all limited gifts (both upgradable and non-upgradable). |
| `exclude_limited_upgradable` | Boolean | Optional | Pass `true` to exclude limited gifts that can be upgraded to unique. |
| `exclude_limited_non_upgradable` | Boolean | Optional | Pass `true` to exclude limited gifts that cannot be upgraded to unique. |
| `exclude_unique` | Boolean | Optional | Pass `true` to exclude unique gifts. |
| `exclude_from_blockchain` | Boolean | Optional | Pass `true` to exclude gifts assigned from the TON blockchain that can't be resold or transferred. |
| `sort_by_price` | Boolean | Optional | Pass `true` to sort results by price. |
| `offset` | String | Optional | Offset string for pagination. |
| `limit` | Integer | Optional | Maximum number of results to return. |

**Requires:** `can_view_gifts_and_stars` business bot right.

**Returns:** `OwnedGifts` object on success.

---

### convertGiftToStars

Converts a gift received by a business account into Telegram Stars credited to the business account balance.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | **Yes** | Unique identifier of the business connection. |
| `owned_gift_id` | String | **Yes** | Identifier of the received gift to convert. |

**Requires:** `can_convert_gifts_to_stars` business bot right.

**Returns:** `True` on success.

---

### upgradeGift

Upgrades a regular gift owned by a business account to a unique gift. Upgrading means the gift becomes a one-of-a-kind unique gift with a unique number, model, symbol, and backdrop. The upgrade assigns randomized visual components based on rarity distribution.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | **Yes** | Unique identifier of the business connection. |
| `owned_gift_id` | String | **Yes** | Identifier of the regular gift to upgrade. |
| `keep_original_details` | Boolean | Optional | Pass `true` to keep the original gift text, sender, and receiver in the upgraded gift. |
| `star_count` | Integer | Optional* | Amount of Telegram Stars paid for the upgrade from the business account balance. If `gift.prepaid_upgrade_star_count > 0`, pass `0` (upgrade was prepaid). Otherwise, this is required and must equal `gift.upgrade_star_count`. |

*Required if the upgrade was not prepaid (`prepaid_upgrade_star_count` is 0 or absent).

**Requires:** `can_transfer_and_upgrade_gifts` business bot right. If `star_count > 0`, also requires `can_transfer_stars`.

**Returns:** `True` on success.

---

### transferGift

Transfers a unique gift owned by a business account to another user or channel chat.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | **Yes** | Unique identifier of the business connection. |
| `owned_gift_id` | String | **Yes** | Identifier of the unique gift to transfer. |
| `new_owner_chat_id` | Integer | **Yes** | Unique identifier of the target user or channel chat that will receive the gift. |
| `star_count` | Integer | Optional | Amount of Telegram Stars paid for the transfer from the business account balance. If positive, the `can_transfer_stars` business bot right is required. |

**Requires:** `can_transfer_and_upgrade_gifts` business bot right. If `star_count > 0`, also requires `can_transfer_stars`.

**Returns:** `True` on success.

---

### setBusinessAccountGiftSettings

Configures gift settings for a business account.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | **Yes** | Unique identifier of the business connection. |
| `show_gift_button` | Boolean | **Yes** | Whether to show the gift button in the business account's chat. |
| `accepted_gift_types` | AcceptedGiftTypes | **Yes** | Types of gifts accepted by the business account. |

**Requires:** `can_change_gift_settings` business bot right.

**Returns:** `True` on success.

---

## Types

### Gift

Describes a gift available for sending.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | String | Yes | Unique identifier of the gift. |
| `sticker` | Sticker | Yes | The sticker that represents the gift. |
| `star_count` | Integer | Yes | Number of Telegram Stars that must be paid to send this gift. |
| `upgrade_star_count` | Integer | Optional | Number of Telegram Stars that must be paid to upgrade this gift to a unique gift. Omitted if the gift cannot be upgraded. |
| `is_premium` | Boolean | Optional | `true` if the gift is exclusively available to Telegram Premium subscribers. |
| `has_colors` | Boolean | Optional | `true` if the upgraded unique gift can have a custom color scheme. |
| `total_count` | Integer | Optional | Total number of this gift type that can be sent by all users. Present for limited gifts only. |
| `remaining_count` | Integer | Optional | Number of remaining gifts of this type. Present for limited gifts only. |
| `personal_total_count` | Integer | Optional | Total number of this gift type the current user can send. Present for limited gifts only. |
| `personal_remaining_count` | Integer | Optional | Number of remaining gifts of this type the current user can send. Present for limited gifts only. |
| `background` | GiftBackground | Optional | Background of the gift. |
| `unique_gift_variant_count` | Integer | Optional | Number of unique gift variants that can be created from this regular gift (i.e., how many unique numbers are available). |
| `publisher_chat` | Chat | Optional | Chat that published this gift. |

---

### OwnedGift (Union Type)

Describes a gift received and owned by a user or chat. This is a union type — the `type` field determines which subtype is used:

- `type == "regular"` → `OwnedGiftRegular`
- `type == "unique"` → `OwnedGiftUnique`

No standalone fields beyond the `type` discriminator.

---

### OwnedGiftRegular

Describes a regular (non-unique) gift received and owned by a user or chat.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | String | Yes | Type of the owned gift. Always `"regular"`. |
| `gift` | Gift | Yes | Information about the regular gift. |
| `owned_gift_id` | String | Optional | Unique identifier of the gift for the bot. Only present for gifts received on behalf of business accounts. |
| `sender_user` | User | Optional | Sender of the gift, if it is a known user. |
| `send_date` | Integer (Unix timestamp) | Yes | Date the gift was sent. |
| `text` | String | Optional | Text of the message added to the gift. |
| `entities` | Array of MessageEntity | Optional | Special entities in `text`. |
| `is_private` | Boolean | Optional | `true` if the sender and gift text are shown only to the gift receiver. |
| `is_saved` | Boolean | Optional | `true` if the gift is displayed on the profile page. Only for business account gifts. |
| `convert_star_count` | Integer | Optional | Number of Telegram Stars claimable by converting the gift. Omitted if conversion is impossible. Only for business account gifts. |
| `prepaid_upgrade_star_count` | Integer | Optional | Number of Telegram Stars prepaid for upgrading this gift. |
| `is_upgrade_separate` | Boolean | Optional | `true` if the gift's upgrade was purchased after the gift was sent (vs. prepaid at send time). |
| `can_be_upgraded` | Boolean | Optional | `true` if the gift can be upgraded to a unique gift. |
| `was_refunded` | Boolean | Optional | `true` if the gift was refunded. |
| `unique_gift_number` | Integer | Optional | Unique number reserved for this gift when upgraded. Corresponds to `UniqueGift.number`. |

---

### OwnedGiftUnique

Describes a unique gift (upgraded from a regular gift) received and owned by a user or chat.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | String | Yes | Type of the owned gift. Always `"unique"`. |
| `gift` | UniqueGift | Yes | Information about the unique gift. |
| `owned_gift_id` | String | Optional | Unique identifier of the gift for the bot. Only for business account gifts. |
| `sender_user` | User | Optional | Sender of the gift, if it is a known user. |
| `send_date` | Integer (Unix timestamp) | Yes | Date the gift was sent. |
| `is_saved` | Boolean | Optional | `true` if the gift is displayed on the profile page. Only for business account gifts. |
| `can_be_transferred` | Boolean | Optional | `true` if the gift can be transferred to another owner. Only for business account gifts. |
| `transfer_star_count` | Integer | Optional | Number of Telegram Stars that must be paid to transfer the gift. Omitted if the bot cannot transfer the gift. |
| `next_transfer_date` | Integer (Unix timestamp) | Optional | Date when the gift can be transferred. If in the past, transfer is available now. |
| `is_from_blockchain` | Boolean | Optional | `true` if the gift is assigned from the TON blockchain and can't be resold or transferred in Telegram. |
| `colors` | UniqueGiftColors | Optional | Color scheme for the gift owner's name, replies, and link previews. Only for business account gifts and gifts currently on sale. |
| `publisher_chat` | Chat | Optional | Chat that published the gift. |
| `origin` | String | Optional | Origin of the gift: `"upgrade"`, `"transfer"`, or `"resale"`. |
| `last_resale_currency` | String | Optional | Three-letter ISO 4217 currency code of the last resale price. |
| `last_resale_amount` | Integer | Optional | Last resale price in the smallest units of the currency. |

---

### UniqueGift

Describes a unique gift that was upgraded from a regular gift.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gift_id` | String | Yes | Identifier of the regular gift from which this unique gift was upgraded. |
| `base_name` | String | Yes | Human-readable name of the original regular gift. |
| `name` | String | Yes | Unique name of the gift. Used in `https://t.me/nft/...` links and story areas. |
| `number` | Integer | Yes | Unique number of this upgraded gift among all gifts upgraded from the same regular gift. |
| `model` | UniqueGiftModel | Yes | Model (visual appearance) of the unique gift. |
| `symbol` | UniqueGiftSymbol | Yes | Symbol of the unique gift. |
| `backdrop` | UniqueGiftBackdrop | Yes | Backdrop of the unique gift. |
| `publisher_chat` | Chat | Optional | Chat that published the gift. |
| `is_premium` | Boolean | Optional | `true` if the original regular gift was exclusively purchaseable by Telegram Premium subscribers. |
| `is_from_blockchain` | Boolean | Optional | `true` if the gift is assigned from the TON blockchain and can't be resold or transferred. |
| `colors` | UniqueGiftColors | Optional | Color scheme for the owner's name, replies, and link previews. Only for business account gifts and gifts on sale. |
| `is_burned` | Boolean | Optional | `true` if the gift was used to craft another gift and is no longer available. |

---

### UniqueGiftModel

Describes the model (main visual) of a unique gift.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Name of the model. |
| `sticker` | Sticker | Yes | The sticker that represents the unique gift model. |
| `rarity_per_mille` | Integer | Yes | Number of unique gifts that receive this model per 1000 upgrades. Always `0` for crafted gifts. |
| `rarity` | String | Optional | Rarity tier for crafted models only. Values: `"uncommon"`, `"rare"`, `"epic"`, `"legendary"`. |

---

### UniqueGiftSymbol

Describes the symbol component of a unique gift.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Name of the symbol. |
| `sticker` | Sticker | Yes | The sticker that represents the symbol. |
| `rarity_per_mille` | Integer | Yes | Number of unique gifts that receive this symbol per 1000 upgrades. |

---

### UniqueGiftBackdrop

Describes the backdrop component of a unique gift.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Name of the backdrop. |
| `colors` | UniqueGiftBackdropColors | Yes | Colors of the backdrop. |
| `rarity_per_mille` | Integer | Yes | Number of unique gifts that receive this backdrop per 1000 upgrades. |

---

### UniqueGiftColors

Color scheme for a unique gift owner's chat name, message replies, and link previews.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_custom_emoji_id` | String | Yes | Custom emoji identifier of the unique gift's model. |
| `symbol_custom_emoji_id` | String | Yes | Custom emoji identifier of the unique gift's symbol. |
| `light_theme_main_color` | Integer | Yes | Main color in light themes (RGB). |
| `light_theme_other_colors` | Array of Integer (1-3) | Yes | Additional colors in light themes (RGB). |
| `dark_theme_main_color` | Integer | Yes | Main color in dark themes (RGB). |
| `dark_theme_other_colors` | Array of Integer (1-3) | Yes | Additional colors in dark themes (RGB). |

---

### UniqueGiftBackdropColors

Color definitions for a unique gift's backdrop. (Sub-type of `UniqueGiftBackdrop.colors`)

Exact field names not confirmed from primary sources. Likely contains RGB color integers similar to `UniqueGiftColors` pattern. Consult the official Bot API documentation for definitive field listing.

---

### GiftBackground

Background colors for a gift's display.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `center_color` | Integer | Yes | Center color of the background (RGB). |
| `edge_color` | Integer | Yes | Edge color of the background (RGB). |
| `text_color` | Integer | Yes | Text color on the background (RGB). |

---

### GiftInfo

Information about a regular gift attached to a message (service message when a gift is sent to a chat where the bot is a member).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gift` | Gift | Yes | Information about the gift. |
| `owned_gift_id` | String | Optional | Unique identifier of the received gift for the bot. Only for business account gifts. |
| `convert_star_count` | Integer | Optional | Number of Telegram Stars claimable by converting the gift. Omitted if conversion is impossible. |
| `prepaid_upgrade_star_count` | Integer | Optional | Number of Telegram Stars prepaid for upgrading this gift. |
| `can_be_upgraded` | Boolean | Optional | `true` if the gift can be upgraded to a unique gift. |
| `text` | String | Optional | Text of the message added to the gift. |
| `entities` | Array of MessageEntity | Optional | Special entities in `text`. |
| `is_private` | Boolean | Optional | `true` if sender and gift text are shown only to the receiver. |
| `unique_gift_number` | Integer | Optional | Unique number reserved for this gift if upgraded. |
| `is_upgrade_separate` | Boolean | Optional | `true` if the upgrade was purchased after the gift was sent. |

---

### UniqueGiftInfo

Information about a unique gift attached to a message.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gift` | UniqueGift | Yes | Information about the unique gift. |
| `origin` | String | Yes | Origin: `"upgrade"` (upgraded from regular), `"transfer"` (transferred from other user/channel), `"resale"` (bought from another user). |
| `last_resale_currency` | String | Optional | Three-letter ISO 4217 currency code of the last resale price. |
| `last_resale_amount` | Integer | Optional | Last resale price in smallest currency units. |
| `owned_gift_id` | String | Optional | Unique identifier for the bot. Only for business account gifts. |
| `transfer_star_count` | Integer | Optional | Stars required to transfer. Omitted if bot cannot transfer. |
| `next_transfer_date` | Integer (Unix timestamp) | Optional | Date when the gift can next be transferred. |

---

### Gifts

Return type for `getAvailableGifts`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gifts` | Array of Gift | Yes | Array of available gifts. |

---

### OwnedGifts

Return type for `getBusinessAccountGifts`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gifts` | Array of OwnedGift | Yes | Array of owned gifts (each is either `OwnedGiftRegular` or `OwnedGiftUnique` based on `type` field). |
| `next_offset` | String | Optional | Offset string for the next page of results. Omitted if no more results. |

---

### AcceptedGiftTypes

Describes which gift types a business account accepts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `unlimited_gifts` | Boolean | Yes | `true` if unlimited regular gifts are accepted. |
| `limited_gifts` | Boolean | Yes | `true` if limited regular gifts are accepted. |
| `unique_gifts` | Boolean | Yes | `true` if unique gifts (or gifts that can be upgraded to unique for free) are accepted. |
| `premium_subscription` | Boolean | Yes | `true` if Telegram Premium subscriptions are accepted as gifts. |
| `gifts_from_channels` | Boolean | Yes | `true` if transfers of unique gifts from channels are accepted. |

---

## Gift Categories

### Regular Gifts (Unlimited)
- No `total_count` or `remaining_count` fields.
- Always available for sending (subject to Star balance).
- Can potentially be upgraded to unique if `upgrade_star_count` is present.
- Displayed with the gift's `sticker` and optional `background`.

### Regular Gifts (Limited)
- Have `total_count` and `remaining_count` fields (global supply).
- May have `personal_total_count` and `personal_remaining_count` (per-user limits).
- Cannot be sent to channel chats.
- May or may not be upgradeable (`upgrade_star_count` presence determines this).
- `unique_gift_variant_count` indicates how many unique numbers exist for this gift type.

### Unique Gifts
- Created by upgrading a regular gift (costs `upgrade_star_count` Stars).
- Each has a unique `number` within its base gift type.
- Composed of randomized visual components: `model`, `symbol`, `backdrop` — each with `rarity_per_mille` distribution.
- For crafted models, `rarity` is one of: `"uncommon"`, `"rare"`, `"epic"`, `"legendary"`.
- Can be transferred to other users/channels (with cooldown via `next_transfer_date`).
- Can be resold (tracked via `origin`, `last_resale_currency`, `last_resale_amount`).
- May have a color scheme (`UniqueGiftColors`) applied to the owner's chat presence.
- Can be "burned" (used to craft another gift) — tracked by `is_burned`.
- Blockchain-assigned unique gifts (`is_from_blockchain`) cannot be resold or transferred in Telegram.

### Rare Gifts
- "Rare" is a rarity tier within the unique gift system, not a separate gift category.
- Applies to crafted `UniqueGiftModel` instances via the `rarity` field.
- Rarity tiers (ascending): `"uncommon"` → `"rare"` → `"epic"` → `"legendary"`.
- Non-crafted models use `rarity_per_mille` for probabilistic distribution instead.

---

## Gift-Related Message Fields

There is NO dedicated `GiftSent` Update type. Gift information appears as optional fields on the `Message` object when a gift is sent in a chat where the bot is a member:

| Message Field | Type | When Present |
|---------------|------|-------------|
| `gift` | GiftInfo | When a regular gift is sent. |
| `unique_gift` | UniqueGiftInfo | When a unique gift is sent/transferred. |

These appear as service messages in the chat. The bot does not receive an Update for gifts sent directly to users (only to groups/channels where the bot is present).

---

## Bot Restrictions on Sending Gifts

1. **No conversion for recipients:** Gifts sent via `sendGift` cannot be converted to Telegram Stars by the receiver (unlike gifts sent directly by users).
2. **Limited gifts to channels:** Limited gifts (`total_count` present) cannot be sent to channel chats via `sendGift`. Only unlimited regular gifts can be sent to channels.
3. **Payment:** Gifts are paid for from the bot's Telegram Stars balance. The bot must have sufficient Stars.
4. **Business account methods:** Most gift management methods (convert, upgrade, transfer) require a business connection and specific bot rights.
5. **No store catalog access:** The Bot API does not provide a method to retrieve the full Telegram Store gift catalog. `getAvailableGifts` returns only gifts the bot can send.

---

## Business Account Gift Rights

The following `BusinessBotRights` fields govern gift operations:

| Right | Controls |
|-------|----------|
| `can_change_gift_settings` | Ability to call `setBusinessAccountGiftSettings`. |
| `can_view_gifts_and_stars` | Ability to call `getBusinessAccountGifts`. |
| `can_convert_gifts_to_stars` | Ability to call `convertGiftToStars`. |
| `can_transfer_and_upgrade_gifts` | Ability to call `upgradeGift` and `transferGift`. |
| `can_transfer_stars` | Required when `star_count > 0` in `upgradeGift` or `transferGift`. |

---

## Quick Reference: Method Summary

| Method | Min Required Params | Key Right | Returns |
|--------|---------------------|-----------|---------|
| `sendGift` | `user_id`/`chat_id`, `gift_id` | (Stars balance) | `True` |
| `getAvailableGifts` | (none) | (none) | `Gifts` |
| `getBusinessAccountGifts` | `business_connection_id` | `can_view_gifts_and_stars` | `OwnedGifts` |
| `convertGiftToStars` | `business_connection_id`, `owned_gift_id` | `can_convert_gifts_to_stars` | `True` |
| `upgradeGift` | `business_connection_id`, `owned_gift_id` | `can_transfer_and_upgrade_gifts` | `True` |
| `transferGift` | `business_connection_id`, `owned_gift_id`, `new_owner_chat_id` | `can_transfer_and_upgrade_gifts` | `True` |
| `setBusinessAccountGiftSettings` | `business_connection_id`, `show_gift_button`, `accepted_gift_types` | `can_change_gift_settings` | `True` |

---

## Notes

- `UniqueGiftBackdropColors` exact fields are not confirmed from primary sources — likely follows the RGB integer array pattern seen in `UniqueGiftColors`.
- The `sendGift` method's `text_parse_mode` and `text_entities` parameters are inferred from standard Telegram Bot API text formatting patterns (consistent with `sendMessage`); they appear in library implementations but may not be explicitly named in the official Bot API method description.
- Bot API version coverage: Methods and types documented here reflect Bot API v9.6+ (2025) as implemented in python-telegram-bot v22.7 and aiogram 3.27.
- The MTProto API (core.telegram.org/api/gifts) has a different type hierarchy (`starGift`, `gift`, `upgradedGift`) — this document covers only the Bot API types.
