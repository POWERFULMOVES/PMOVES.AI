# Telegram Bot API Star Payments (XTR Currency) — Complete Reference

Generated: 2026-04-25 | Sources: Official Telegram docs, python-telegram-bot, aiogram, GramIO, community guides

---

## Table of Contents

1. [XTR Currency Overview](#1-xtr-currency-overview)
2. [Fee Structure & Star Value](#2-fee-structure--star-value)
3. [XTR vs Regular Payment Invoices](#3-xtr-vs-regular-payment-invoices)
4. [Methods — Complete Parameter Reference](#4-methods--complete-parameter-reference)
   - 4.1 sendInvoice (XTR Variant)
   - 4.2 createInvoiceLink (Star Variant)
   - 4.3 getMyStarBalance
   - 4.4 getStarTransactions
   - 4.5 refundStarPayment
5. [Related Types — Complete Field Reference](#5-related-types--complete-field-reference)
   - 5.1 LabeledPrice
   - 5.2 StarTransaction
   - 5.3 StarTransactions
   - 5.4 StarTransactionSource (Official) / TransactionPartner (PTB)
   - 5.5 StarTransactionPartner Sub-Types
6. [Limits & Restrictions](#6-limits--restrictions)
7. [Important Notes & Gotchas](#7-important-notes--gotchas)

---

## 1. XTR Currency Overview

- XTR is the ISO-style currency code for Telegram Stars in the Bot API
- Stars are an in-app virtual currency for purchasing digital goods and services
- Due to Apple/Google policies, all digital goods must use XTR exclusively (no fiat currencies)
- Physical goods must use regular fiat currencies and cannot use XTR
- Users acquire Stars via in-app purchases (Apple Pay, Google Pay) or @PremiumBot
- Bots receive Stars and can withdraw them via Fragment to TON/crypto

---

## 2. Fee Structure & Star Value

### Star Value
| Context | USD Value per Star |
---------|-------------------|
| User purchase price (retail) | ~$0.016 (varies by region/platform) |
| Bot creator withdrawal value | ~$0.013 USD (fixed by Telegram) |
| Fragment market rate (real-time) | ~$0.015 (fluctuates) |

Note: Telegram states the $0.013 rate is determined at its sole discretion and has no connection to purchase cost in any region.

### Fee Structure
| Party | Share | Notes |
-------|-------|-------|
| Telegram | **0%** | Telegram takes no commission from creators |
| Bot Creator | **100%** | Receives all Stars sent by users |
| Apple/Google | ~30% | Deducted on the buyer side during Star purchase |

The spread between purchase price (~$0.016) and withdrawal value (~$0.013) is entirely absorbed by app store fees on the purchasing side, not by Telegram.

---

## 3. XTR vs Regular Payment Invoices

| Aspect | XTR (Stars) Invoice | Regular Fiat Invoice |
--------|---------------------|-------------------|
| currency parameter | "XTR" | ISO 4217 code (e.g., "USD") |
| provider_token | **Must be OMITTED** (not passed at all) | Required — from @BotFather |
| prices array | Must contain **exactly 1 item** | Can contain multiple items |
| LabeledPrice amount | Integer Stars (no decimals) | Smallest currency unit (e.g., cents) |
| max_tip_amount | **Not supported** | Optional integer |
| suggested_tip_amounts | **Not supported** | Optional int array |
| need_name | Ignored | Optional boolean |
| need_phone_number | Ignored | Optional boolean |
| need_email | Ignored | Optional boolean |
| need_shipping_address | Ignored | Optional boolean |
| send_phone_number_to_provider | Ignored | Optional boolean |
| send_email_to_provider | Ignored | Optional boolean |
| is_flexible | Ignored | Optional boolean |
| provider_data | Optional | Optional |
| Payment provider | Telegram (built-in) | External provider (Stripe, etc.) |
| Shipping query | Never sent | Can be sent |
| start_parameter | Controls forwarding behavior | Deep-linking parameter |
| Subscription support | Yes (since Bot API 7.x) | No |
| Goods type | Digital only | Physical goods allowed |

---

## 4. Methods — Complete Parameter Reference

### 4.1 sendInvoice (XTR Variant)

Use this method to send an invoice as a message. For XTR, provider_token must be completely omitted from the request.

Returns: Message on success.

| Parameter | Type | Required | XTR Notes |
-----------|------|----------|----------|
| chat_id | Integer or String | Yes | — |
| message_thread_id | Integer | No | — |
| direct_messages_topic_id | Integer | No | — |
| title | String | Yes | Product name, 1-32 chars |
| description | String | Yes | Product description, 1-255 chars |
| payload | String | Yes | Bot-defined payload, 1-128 bytes |
| provider_token | String | **No (OMIT for XTR)** | Must NOT be included in the request for XTR invoices |
| currency | String | Yes | Must be "XTR" |
| prices | Array of LabeledPrice | Yes | Must contain exactly 1 item for XTR |
| max_tip_amount | Integer | No | **Not supported for XTR** |
| suggested_tip_amounts | Array of Integer | No | **Not supported for XTR** |
| start_parameter | String | No | Controls forwarding behavior; for XTR invoices, determines multi-chat vs single-chat forwarding |
| provider_data | String | No | JSON-serialized data about the invoice |
| photo_url | String | No | URL of product photo |
| photo_size | Integer | No | Photo size in bytes |
| photo_width | Integer | No | Photo width |
| photo_height | Integer | No | Photo height |
| need_name | Boolean | No | **Ignored for XTR** |
| need_phone_number | Boolean | No | **Ignored for XTR** |
| need_email | Boolean | No | **Ignored for XTR** |
| need_shipping_address | Boolean | No | **Ignored for XTR** |
| send_phone_number_to_provider | Boolean | No | **Ignored for XTR** |
| send_email_to_provider | Boolean | No | **Ignored for XTR** |
| is_flexible | Boolean | No | **Ignored for XTR** |
| disable_notification | Boolean | No | — |
| protect_content | Boolean | No | — |
| allow_paid_broadcast | Boolean | No | — |
| message_effect_id | String | No | — |
| suggested_post_parameters | SuggestedPostParameters | No | — |
| reply_parameters | ReplyParameters | No | — |
| reply_markup | InlineKeyboardMarkup | No | — |

---

### 4.2 createInvoiceLink (Star Variant)

Use this method to create a link for an invoice. Returns a String (the invoice link URL).

For XTR, provider_token behavior differs from sendInvoice: some implementations accept an empty string, but the official changelog says to omit it. Check your library's behavior.

| Parameter | Type | Required | XTR Notes |
-----------|------|----------|----------|
| title | String | Yes | Product name, 1-32 chars |
| description | String | Yes | Product description, 1-255 chars |
| payload | String | Yes | Bot-defined payload, 1-128 bytes |
| provider_token | String | **No (OMIT for XTR)** | Must NOT be included for XTR; some libraries accept empty string |
| currency | String | Yes | Must be "XTR" |
| prices | Array of LabeledPrice | Yes | Must contain exactly 1 item for XTR |
| business_connection_id | String | No | — |
| subscription_period | Integer | No | If used, currency MUST be "XTR"; must be 2592000 (30 days); subscription price must not exceed 10,000 Stars |
| max_tip_amount | Integer | No | **Not supported for XTR** |
| suggested_tip_amounts | Array of Integer | No | **Not supported for XTR** |
| provider_data | String | No | JSON-serialized data about the invoice |
| photo_url | String | No | URL of product photo |
| photo_size | Integer | No | Photo size in bytes |
| photo_width | Integer | No | Photo width |
| photo_height | Integer | No | Photo height |
| need_name | Boolean | No | **Ignored for XTR** |
| need_phone_number | Boolean | No | **Ignored for XTR** |
| need_email | Boolean | No | **Ignored for XTR** |
| need_shipping_address | Boolean | No | **Ignored for XTR** |
| send_phone_number_to_provider | Boolean | No | **Ignored for XTR** |
| send_email_to_provider | Boolean | No | **Ignored for XTR** |
| is_flexible | Boolean | No | **Ignored for XTR** |

---

### 4.3 getMyStarBalance

Use this method to get the number of Telegram Stars owned by the bot.

Returns: Integer — the bot's Star balance.

| Parameter | Type | Required | Notes |
-----------|------|----------|-------|
| *(none)* | — | — | Takes no parameters |

---

### 4.4 getStarTransactions

Returns the bot's Telegram Star transactions in chronological order.

Returns: StarTransactions object.

| Parameter | Type | Required | Notes |
-----------|------|----------|-------|
| offset | Integer | No | Number of transactions to skip in the response (for pagination) |
| limit | Integer | No | Maximum number of transactions to return; default behavior follows Bot API defaults (typically 100) |

---

### 4.5 refundStarPayment

Refunds a successful payment in Telegram Stars. You must store the telegram_payment_charge_id from the SuccessfulPayment object.

Returns: True on success.

| Parameter | Type | Required | Notes |
-----------|------|----------|-------|
| user_id | Integer | Yes | Identifier of the user whose payment will be refunded |
| telegram_payment_charge_id | String | Yes | Telegram payment identifier from SuccessfulPayment.telegram_payment_charge_id |

---

## 5. Related Types — Complete Field Reference

### 5.1 LabeledPrice

This type is reused for both regular and Star invoices.

| Field | Type | Required | XTR Notes |
-------|------|----------|----------|
| label | String | Yes | Component label (e.g., "Product price") |
| amount | Integer | Yes | For XTR: integer number of Stars (whole numbers, no decimals). For fiat: smallest currency unit (e.g., cents for USD) |

XTR constraint: The prices array must contain exactly one LabeledPrice item.

---

### 5.2 StarTransaction

Describes a single Telegram Star transaction.

| Field | Type | Required | Description |
-------|------|----------|-------------|
| id | String | Yes | Unique transaction identifier. Coincides with SuccessfulPayment.telegram_payment_charge_id for incoming payments. For refunds, coincides with original transaction ID. |
| amount | Integer | Yes | Number of Telegram Stars transferred (negative for outgoing). |
| nanostar_amount | Integer | No | Number of 1e-09 shares of Stars; range 0-999999999. Added in later Bot API versions. |
| date | Integer (Unix timestamp) | Yes | Date the transaction was created. |
| source | StarTransactionSource | No | Source of incoming transaction only. Present for incoming, absent for outgoing. |
| receiver | StarTransactionPartner | No | Receiver of outgoing transaction only. Present for outgoing, absent for incoming. |

Chargeback note: If the buyer initiates a chargeback with the payment provider (Apple/Google) after this transaction, refunded Stars will be deducted from the bot's balance. This is outside Telegram's control.

---

### 5.3 StarTransactions

Container type returned by getStarTransactions.

| Field | Type | Required | Description |
-------|------|----------|-------------|
| transactions | Array of StarTransaction | Yes | The list of transactions in chronological order. |

---

### 5.4 StarTransactionSource / StarTransactionPartner

The official Bot API defines these as separate types: StarTransactionSource (for incoming transactions, the source field) and StarTransactionPartner (for outgoing transactions, the receiver field). Both share the same sub-type structure differentiated by the type field.

Note: python-telegram-bot 22.x unified these into a single TransactionPartner hierarchy. The official Bot API keeps them separate but with identical sub-type structures.

### 5.5 StarTransactionPartner Sub-Types (ALL Fields)

All sub-types share a discriminator field:

| Field | Type | Present In | Description |
-------|------|-----------|-------------|
| type | String | ALL | Discriminator: "user", "fragment", "other", "chat", "telegram_api", "telegram_ads", "affiliate_program" |

#### StarTransactionSourceUser / StarTransactionPartnerUser

Type value: "user"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "user" |
| transaction_type | String | Yes | One of: "invoice_payment", "paid_media_payment", "gift_purchase" |
| user | User | Yes | Full User object of the buyer/sender |
| invoice_payload | String | No | Bot-specified invoice payload (only for transaction_type="invoice_payment") |
| paid_media | Array of PaidMedia | No | Paid media purchased (only for transaction_type="paid_media_payment") |
| paid_media_payload | String | No | Bot-specified payload for paid media |
| subscription_period | Integer | No | Subscription period in seconds (only for subscription payments) |
| gift | Gift | No | Gift information (only for transaction_type="gift_purchase") |
| affiliate | AffiliateInfo | No | Affiliate program information if applicable |
| premium_subscription_duration | Integer | No | Premium subscription duration if purchased via gift |

#### StarTransactionPartnerFragment

Type value: "fragment"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "fragment" |
| withdrawal_state | RevenueWithdrawalState | No | State of outgoing withdrawal transaction (e.g., pending, succeeded, failed) |

#### StarTransactionPartnerOther

Type value: "other"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "other" |

#### StarTransactionPartnerChat

Type value: "chat"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "chat" |
| chat | Chat | Yes | Full Chat object |
| gift | Gift | No | Gift information if applicable |

#### StarTransactionPartnerTelegramApi

Type value: "telegram_api"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "telegram_api" |
| request_count | Integer | Yes | Number of API requests paid for (used for paid broadcasting) |

#### StarTransactionPartnerTelegramAds

Type value: "telegram_ads"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "telegram_ads" |

#### StarTransactionPartnerAffiliateProgram

Type value: "affiliate_program"

| Field | Type | Required | Description |
-------|------|----------|-------------|
| type | String | Yes | Always "affiliate_program" |
| commission_per_mille | Integer | Yes | Stars received per 1,000 Stars received by the affiliate sponsor from referred users |

---

## 6. Limits & Restrictions

### Star Amount Limits
| Context | Min | Max |
---------|-----|-----|
| Single invoice price (one-time) | 1 Star | Not explicitly documented (very high or uncapped) |
| Subscription price | 1 Star | **10,000 Stars** |
| Subscription period | — | 2,592,000 seconds (30 days, only valid value) |
| Paid media (sendPaidMedia) | 1 Star | 25,000 Stars |
| Paid media in a post | 1 Star | 25,000 Stars |
| Personal paid message | 1 Star | 10,000 Stars |
| Paid reactions | 1 Star | 10,000 Stars |
| Stream paid message | 1 Star | 10,000 Stars |
| Stream pin via Stars | 10 Stars | 10,000 Stars |
| Collectible gift resale | 125 Stars | 100,000 Stars |
| Suggested message to channel | 5 Stars | 100,000 Stars |
| Paid broadcast | 0.1 Star/msg | 1,000 msgs/sec |
| Withdrawal from bot balance | 1,000 Stars | 25,000,000 Stars |

### LabeledPrice Constraint
- XTR invoices: prices array MUST contain exactly 1 LabeledPrice item
- Fiat invoices: prices array can contain multiple items (product, tax, discount, delivery, etc.)

### Subscription Constraints
- subscription_period is currently locked to 2,592,000 seconds (30 days)
- Multiple concurrent subscriptions can exist per bot, including from the same user
- Subscription invoice links use createInvoiceLink with subscription_period parameter

---

## 7. Important Notes & Gotchas

1. **provider_token must be OMITTED, not empty string** — The official changelog explicitly states provider_token must be omitted (not passed) for sendInvoice and createInvoiceLink when using XTR. Passing an empty string "" will cause errors in some implementations. Some libraries internally handle this, but the raw API call must not include the key.

2. **Chargeback risk** — If a user chargebacks their Stars purchase with Apple/Google, the Stars will be deducted from your bot's balance, even after you've delivered the digital good. This is outside Telegram's control.

3. **nanostar_amount field** — Added in later Bot API versions. Allows fractional Star amounts (1e-9 precision). Not all libraries may support this yet.

4. **Naming discrepancy** — The official Bot API uses StarTransactionSource (for source field on incoming) and StarTransactionPartner (for receiver field on outgoing). python-telegram-bot 22.x unified these into a TransactionPartner hierarchy with sub-classes. Other libraries may use different naming.

5. **SuccessfulPayment identifiers** — The SuccessfulPayment object contains both telegram_payment_charge_id (used for refunds) and provider_payment_charge_id (not relevant for XTR since there's no external provider). Always store telegram_payment_charge_id.

6. **No pre-checkout query for certain scenarios** — The answerPreCheckoutQuery method is still used for XTR invoices, but the 10-second timeout still applies.

7. **Withdrawal only via Fragment** — Bot creators can only withdraw Stars to TON/crypto through the Fragment platform. Minimum withdrawal: 1,000 Stars.

8. **Star value is fixed by Telegram** — The ~$0.013/Star withdrawal rate is set by Telegram at its discretion. It has no connection to purchase prices in any region and can theoretically change.

9. **test environment** — Telegram provides a test environment for Stars payments. Refer to the official payments-stars documentation for test setup instructions.

10. **start_parameter for XTR** — For XTR invoices, start_parameter controls whether the invoice can be forwarded to multiple chats or is restricted to a single chat, unlike regular invoices where it's a deep-linking parameter.

---

## Source Index

1. https://core.telegram.org/bots/payments-stars — Official Stars payments guide
2. https://core.telegram.org/bots/api — Official Bot API reference
3. https://docs.python-telegram-bot.org/en/stable/telegram.startransaction.html — PTB StarTransaction type
4. https://docs.python-telegram-bot.org/en/stable/telegram.startransactions.html — PTB StarTransactions type
5. https://docs.python-telegram-bot.org/en/stable/telegram.transactionpartner.html — PTB TransactionPartner hierarchy
6. https://docs.aiogram.dev/en/latest/api/methods/send_invoice.html — aiogram sendInvoice params
7. https://docs.aiogram.dev/en/latest/api/methods/create_invoice_link.html — aiogram createInvoiceLink params
8. https://docs.aiogram.dev/en/latest/api/methods/get_star_transactions.html — aiogram getStarTransactions
9. https://docs.aiogram.dev/en/latest/api/methods/refund_star_payment.html — aiogram refundStarPayment
10. https://docs.aiogram.dev/en/latest/api/methods/get_my_star_balance.html — aiogram getMyStarBalance
11. https://stackoverflow.com/questions/79492815/ — XTR provider_token omission requirement
12. https://paprika.bot/blog/telegram-stars/ — Fee structure analysis
13. https://blog.mihailgok.ru/en/payment-in-telegram-bots-with-stars/ — $0.013/Star withdrawal rate
14. https://bot-market.net/help/telegram-limit/ — Star limits compilation
15. https://bes-dev.github.io/telegram_stars_rates/ — Real-time Star/USDT rates
16. https://floqal.com/blog/telegram-stars/ — Star pricing overview
17. https://litegram.readthedocs.io/en/latest/api/methods/create_invoice_link.html — Subscription constraints
