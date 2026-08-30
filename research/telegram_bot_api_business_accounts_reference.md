# Telegram Bot API — Business Accounts: Complete Technical Reference

> Compiled: 2026-04-25 | Source: core.telegram.org/bots/api, Bot API changelog, library docs
> Bot API version: 9.6+ | Covers all business-related types, methods, updates, and fields

---

## Table of Contents

1. [Overview: Business Bot vs Regular Bot](#1-overview)
2. [User Connection Flow](#2-user-connection-flow)
3. [Types](#3-types)
   - 3.1 BusinessConnection
   - 3.2 BusinessBotRights
   - 3.3 BusinessMessagesDeleted
   - 3.4 InputChecklist
4. [Message Fields Related to Business](#4-message-fields)
   - 4.1 sender_business_bot
5. [Update Types](#5-update-types)
6. [Methods](#6-methods)
   - 6.1 Connection Management
   - 6.2 Message Operations (on behalf of business)
   - 6.3 Account Profile Management
   - 6.4 Gift & Stars Management
   - 6.5 Story Management
   - 6.6 Checklist Methods
   - 6.7 Draft Streaming
7. [Methods Accepting business_connection_id (Full List)](#7-methods-accepting-business_connection_id)
8. [Naming Discrepancies](#8-naming-discrepancies)

---

## 1. Overview {#1-overview}

A **business bot** is a regular Telegram bot that has been connected to a user's Telegram Business account. The connection grants the bot specific rights to act on behalf of the business account user in their private chats.

Key differences from a regular bot:

| Aspect | Regular Bot | Business Bot |
|--------|-------------|--------------|
| Sends messages as | The bot itself | The business account user (appears as the user) |
| Can read messages | Only messages sent to the bot | Can mark business account messages as read (if right granted) |
| Can delete messages | Only its own messages | Can delete sent/all messages (if right granted) |
| Can edit profile | No | Can edit name, bio, username, photo (if right granted) |
| Can post stories | No | Yes (if can_manage_stories right granted) |
| Can manage gifts/stars | Only bot's own | Can manage business account's gifts and stars (if right granted) |
| Connection required | No | Must receive BusinessConnection update with rights |
| Receives updates | message, edited_message, etc. | business_message, edited_business_message, deleted_business_messages, business_connection |

There is NO separate "business bot" bot type. Any regular bot can become a business bot when a Telegram Business user connects it. There is NO `is_business_bot` field on the User or Bot type in the Bot API.

---

## 2. User Connection Flow {#2-user-connection-flow}

1. Business account user opens Telegram app settings
2. Navigates to **Telegram Business > Chatbots**
3. Types the bot's username
4. Telegram shows connection options including which rights to grant
5. User enables/disables specific rights (reply to messages, read messages, delete messages, edit profile, etc.)
6. User confirms the connection
7. Bot receives an `update.business_connection` Update with a `BusinessConnection` object
8. The bot stores the `business_connection_id` for subsequent API calls
9. The bot can now act on behalf of the business user using methods with the `business_connection_id` parameter

To disconnect or modify rights, the user revisits Telegram Business > Chatbots settings. The bot receives a new `business_connection` update with `is_enabled: false` or updated rights.

---

## 3. Types {#3-types}

### 3.1 BusinessConnection {#3-1-businessconnection}

Describes the connection of the bot with a business account.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | String | Yes | Unique identifier of the business connection |
| `user` | User | Yes | Business account user that created the business connection |
| `user_chat_id` | Integer | Yes | Identifier of a private chat with the user who created the business connection. This number may have more than 32 significant bits and some programming languages may have difficulty/silent defects in interpreting it. But it has at most 52 significant bits, so a 64-bit integer or double-precision float type are safe for storing this identifier. |
| `date` | Integer | Yes | Date the connection was established in Unix time |
| `rights` | BusinessBotRights | No | Rights of the business bot |
| `is_enabled` | Boolean | Yes | True, if the connection is active |

Note: Earlier Bot API versions also included a `can_reply` field (Boolean, Optional). This has been superseded by `rights.can_reply` in the `BusinessBotRights` object. Some libraries may still expose it for backward compatibility.

---

### 3.2 BusinessBotRights {#3-2-businessbotrights}

Describes the rights of a business bot. All fields are Optional with type `True` (Boolean). A field is present and `true` only if the business user explicitly granted that right during connection setup.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `can_reply` | True | No | True, if the bot can send and edit messages in the private chats that had incoming messages in the last 24 hours |
| `can_read_messages` | True | No | True, if the bot can mark incoming private messages as read |
| `can_delete_sent_messages` | True | No | True, if the bot can delete messages sent by the bot |
| `can_delete_all_messages` | True | No | True, if the bot can delete all private messages in managed chats |
| `can_edit_name` | True | No | True, if the bot can edit the first and last name of the business account |
| `can_edit_bio` | True | No | True, if the bot can edit the bio of the business account |
| `can_edit_profile_photo` | True | No | True, if the bot can edit the profile photo of the business account |
| `can_edit_username` | True | No | True, if the bot can edit the username of the business account |
| `can_change_gift_settings` | True | No | True, if the bot can change the privacy settings pertaining to gifts for the business account |
| `can_view_gifts_and_stars` | True | No | True, if the bot can view gifts and the amount of Telegram Stars owned by the business account |
| `can_convert_gifts_to_stars` | True | No | True, if the bot can convert regular gifts owned by the business account to Telegram Stars |
| `can_transfer_and_upgrade_gifts` | True | No | True, if the bot can transfer and upgrade gifts owned by the business account |
| `can_transfer_stars` | True | No | True, if the bot can transfer Telegram Stars received by the business account to its own account, or use them to upgrade and transfer gifts |
| `can_manage_stories` | True | No | True, if the bot can post, edit and delete stories on behalf of the business account |

Total: **14 rights fields**

---

### 3.3 BusinessMessagesDeleted {#3-3-businessmessagesdeleted}

This object is received when messages are deleted from a connected business account.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `chat` | Chat | Yes | Information about a chat in the business account. The bot may not have access to the chat or the corresponding user. |
| `message_ids` | Array of Integer | Yes | The list of identifiers of deleted messages in the chat of the business account |

**IMPORTANT**: The type name is `BusinessMessagesDeleted` (PLURAL). The Update field name is `deleted_business_messages`. There is NO singular `businessMessageDeleted` type in the Bot API.

---

### 3.4 InputChecklist {#3-4-inputchecklist}

Used in sendChecklist and editMessageChecklist methods. This object describes a checklist to be sent or edited. (Exact sub-fields depend on Bot API version; refer to official docs for full InputChecklist specification.)

---

## 4. Message Fields Related to Business {#4-message-fields}

### 4.1 sender_business_bot {#4-1-sender_business_bot}

| Field | Type | Required | Parent Type | Description |
|-------|------|----------|-------------|-------------|
| `sender_business_bot` | BusinessConnection | No | Message | Information about the business connection from which the message was sent. Present only if the message was sent on behalf of a business account. |

**CRITICAL CORRECTION**: There is NO `is_business_bot` field anywhere in the Telegram Bot API (not on User type, not on Bot type, not anywhere). The field that indicates a message was sent via a business connection is `sender_business_bot` on the `Message` type. This field contains the full `BusinessConnection` object (with id, user, rights, etc.) when present.

---

## 5. Update Types {#5-update-types}

The `Update` object has four business-related fields:

| Update Field | Type | Description |
|--------------|------|-------------|
| `business_connection` | BusinessConnection | The bot was connected to or disconnected from a business account, or a user edited an existing connection with the bot |
| `business_message` | Message | New message from a connected business account |
| `edited_business_message` | Message | New version of a message from a connected business account |
| `deleted_business_messages` | BusinessMessagesDeleted | Messages were deleted from a connected business account |

To receive business updates, the bot must include the corresponding field names in the `allowed_updates` parameter of `getUpdates` or the webhook `allowed_updates` setting.

---

## 6. Methods {#6-methods}

### 6.1 Connection Management {#6-1-connection}

#### getBusinessConnection

Use this method to get information about the connection of the bot with a business account. Returns a BusinessConnection object on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |

**Returns**: BusinessConnection

---

### 6.2 Message Operations (on behalf of business) {#6-2-message-ops}

#### readBusinessMessage

Use this method to mark incoming messages as read on behalf of a business account. Requires the `can_read_messages` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `chat_id` | Integer or String | Yes | Unique identifier for the target chat |
| `message_id` | Integer | Yes | Identifier of the message to mark as read |

**Returns**: True

---

#### deleteBusinessMessages

Use this method to delete messages on behalf of a business account. Requires the `can_delete_sent_messages` or `can_delete_all_messages` business bot right depending on the messages. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `message_ids` | Array of Integer | Yes | Identifiers of the messages to delete |

Note: There is NO `chat_id` parameter in the official Bot API method signature. The message identifiers are sufficient.

**Returns**: True

---

### 6.3 Account Profile Management {#6-3-profile}

#### setBusinessAccountName

Use this method to change the name of a business account. Requires the `can_edit_name` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `first_name` | String | Yes | New first name for the business account |
| `last_name` | String | No | New last name for the business account (if omitted, the last name is removed) |

**Returns**: True

---

#### setBusinessAccountBio

Use this method to change the bio of a business account. Requires the `can_edit_bio` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `bio` | String | Yes | The new value of the bio for the business account; 0-140 characters |

**Returns**: True

---

#### setBusinessAccountUsername

Use this method to change the username of a business account. Requires the `can_edit_username` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `username` | String | Yes | The new value of the username for the business account; 0-32 characters |

**Returns**: True

---

#### setBusinessAccountProfilePhoto

Use this method to set a profile photo for a business account. Requires the `can_edit_profile_photo` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `photo` | InputFile | Yes | New profile photo for the business account |

**Returns**: True

---

#### removeBusinessAccountProfilePhoto

Use this method to remove the profile photo of a business account. Requires the `can_edit_profile_photo` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |

**Returns**: True

---

### 6.4 Gift & Stars Management {#6-4-gifts-stars}

#### getBusinessAccountStarBalance

Use this method to check the current Telegram Star balance of a managed business account. Requires the `can_view_gifts_and_stars` business bot right. Returns StarTransactions object on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |

**Returns**: StarTransactions

---

#### getBusinessAccountGifts

Use this method to get the list of gifts received by a managed business account. Requires the `can_view_gifts_and_stars` business bot right. Returns an array of OwnedGift objects on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `exclude_unsaved` | Boolean | No | Pass True to exclude gifts that aren't saved to the account's profile page |
| `exclude_saved` | Boolean | No | Pass True to exclude gifts that are saved to the account's profile page |
| `exclude_unlimited` | Boolean | No | Pass True to exclude gifts that can be purchased an unlimited number of times |
| `exclude_limited_upgradable` | Boolean | No | Pass True to exclude gifts that can be purchased a limited number of times and can be upgraded to unique |
| `exclude_limited_non_upgradable` | Boolean | No | Pass True to exclude gifts that can be purchased a limited number of times and can't be upgraded to unique |
| `exclude_unique` | Boolean | No | Pass True to exclude unique gifts |

Note: Earlier versions had `exclude_from_blockchain` and `exclude_limited` parameters which were replaced by the more granular `exclude_limited_upgradable` and `exclude_limited_non_upgradable`.

**Returns**: Array of OwnedGift

---

#### convertGiftToStars

Use this method to convert gifts received by a managed business account to Telegram Stars. Requires the `can_convert_gifts_to_stars` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `owned_gift_id` | String | Yes | Identifier of the gift to convert |

**Returns**: True

---

#### upgradeGift

Use this method to upgrade regular gifts received by a managed business account to unique gifts. Requires the `can_transfer_and_upgrade_gifts` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `owned_gift_id` | String | Yes | Identifier of the gift to upgrade |

**Returns**: True

---

#### transferGift

Use this method to transfer unique gifts owned by a managed business account to another user. Requires the `can_transfer_and_upgrade_gifts` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `owned_gift_id` | String | Yes | Identifier of the gift to transfer |
| `new_owner_chat_id` | Integer or String | Yes | Chat ID of the new gift owner |

**Returns**: True

---

#### transferBusinessAccountStars

Transfers Telegram Stars from the business account balance to the bot's balance. Requires the `can_transfer_stars` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `star_count` | Integer | Yes | Number of Telegram Stars to transfer; 1-10000 |

**Returns**: True

---

#### setBusinessAccountGiftSettings

Use this method to change the privacy settings pertaining to incoming gifts in a managed business account. Requires the `can_change_gift_settings` business bot right. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `show_gift_button` | Boolean | Yes | Whether to show the gift button |
| `accepted_gift_types` | Array of String | Yes | Array of accepted gift type identifiers |

**Returns**: True

---

### 6.5 Story Management {#6-5-stories}

All story methods require the `can_manage_stories` business bot right. Regular bots CANNOT post stories.

#### postStory

Use this method to post a story on behalf of a business account. Returns Story object on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `content` | InputStoryContent | Yes | Content of the story |
| `active_period` | Integer | Yes | Period after which the story is moved to the archive, in seconds; must be one of `21600` (6h), `43200` (12h), `86400` (24h), or `172800` (48h) |
| `caption` | String | No | Caption of the story, 0-2048 characters after entities parsing |
| `parse_mode` | String | No | Mode for parsing entities in the story caption. See formatting options for more details. |
| `caption_entities` | Array of MessageEntity | No | A JSON-serialized list of special entities that appear in the caption, which can be specified instead of parse_mode |
| `areas` | Array of StoryArea | No | A JSON-serialized list of clickable areas to be shown on the story |

**Returns**: Story (minimal — only contains `chat` and `id` fields)

---

#### editStory

Use this method to edit a story posted on behalf of a business account. Returns Story object on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `story_id` | Integer | Yes | Unique identifier of the story to edit |
| `content` | InputStoryContent | Yes | Content of the story |
| `caption` | String | No | Caption of the story, 0-2048 characters after entities parsing |
| `parse_mode` | String | No | Mode for parsing entities in the story caption |
| `caption_entities` | Array of MessageEntity | No | A JSON-serialized list of special entities that appear in the caption, which can be specified instead of parse_mode |
| `areas` | Array of StoryArea | No | A JSON-serialized list of clickable areas to be shown on the story |

**Returns**: Story (minimal)

---

#### deleteStory

Use this method to delete a story posted on behalf of a business account. Returns True on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `story_id` | Integer | Yes | Unique identifier of the story to delete |

**Returns**: True

---

#### repostStory

Use this method to repost a story on behalf of a business account. Both business accounts must be managed by the same bot. The source story must have been posted or reposted by the bot itself. Requires `can_manage_stories` right for both the source and destination accounts. Returns Story object on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection |
| `from_chat_id` | Integer | Yes | Unique identifier of the chat which posted the story that should be reposted |
| `from_story_id` | Integer | Yes | Unique identifier of the story that should be reposted |
| `active_period` | Integer | Yes | Period after which the story is moved to the archive, in seconds; must be one of `21600` (6h), `43200` (12h), `86400` (24h), or `172800` (48h) |
| `post_to_chat_page` | Boolean | No | Pass True to keep the story accessible after it expires |
| `protect_content` | Boolean | No | Pass True if the content of the story must be protected from forwarding and screenshotting |

**Returns**: Story (minimal)

---

### 6.6 Checklist Methods {#6-6-checklists}

#### sendChecklist

Use this method to send a checklist on behalf of a business account. Returns Message on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection on behalf of which the message will be sent |
| `chat_id` | Integer | Yes | Unique identifier for the target chat |
| `checklist` | InputChecklist | Yes | A JSON-serialized object for the checklist to send |
| `disable_notification` | Boolean | No | Sends the message silently. Users will receive a notification with no sound. |
| `protect_content` | Boolean | No | Protects the contents of the sent message from forwarding and saving |
| `message_effect_id` | String | No | Unique identifier of the message effect to be added to the message |
| `reply_parameters` | ReplyParameters | No | A JSON-serialized object for description of the message to reply to |

**Returns**: Message

---

#### editMessageChecklist

Use this method to edit a checklist on behalf of a business account. Returns Message on success.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `business_connection_id` | String | Yes | Unique identifier of the business connection on behalf of which the message will be sent |
| `chat_id` | Integer | Yes | Unique identifier for the target chat |
| `message_id` | Integer | Yes | Unique identifier for the target message |
| `checklist` | InputChecklist | Yes | A JSON-serialized object for the new checklist |

**Returns**: Message

---

### 6.7 Draft Streaming {#6-7-draft}

#### sendMessageDraft

Introduced in Bot API 9.3 (Dec 31, 2025), available to all bots since Bot API 9.5 (Mar 1, 2026). Allows partial messages to be streamed to a user while being generated. This is a purpose-built method for streaming LLM output — superior to the send-then-repeatedly-edit approach.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `chat_id` | Integer | Yes | Unique identifier for the target private chat |
| `draft_id` | Integer | Yes | Unique identifier of the message draft; must be non-zero. Changes of drafts with the same identifier are animated |
| `text` | String | Yes | Text of the message to be sent, 1-4096 characters after entities parsing |
| `message_thread_id` | Integer | No | Unique identifier for the target message thread |
| `parse_mode` | String | No | Mode for parsing entities in the message text. See formatting options for more details. |
| `entities` | Array of MessageEntity | No | A JSON-serialized list of special entities that appear in message text, which can be specified instead of parse_mode |

Note: As of Bot API 9.6, sendMessageDraft does NOT accept `reply_markup`, `link_preview_options`, or `disable_web_page_preview` parameters. It is intentionally minimal for streaming use cases. The draft is displayed to the user in real-time as a typing preview. To finalize the draft, send a regular `sendMessage` with the complete text.

**Returns**: True

---

## 7. Methods Accepting business_connection_id (Full List) {#7-methods-accepting-business_connection_id}

### Methods where business_connection_id is REQUIRED

These methods can ONLY be called with a business connection — they have no non-business equivalent:

1. `readBusinessMessage`
2. `deleteBusinessMessages`
3. `setBusinessAccountName`
4. `setBusinessAccountUsername`
5. `setBusinessAccountBio`
6. `setBusinessAccountProfilePhoto`
7. `removeBusinessAccountProfilePhoto`
8. `setBusinessAccountGiftSettings`
9. `sendChecklist`
10. `transferBusinessAccountStars`
11. `getBusinessAccountStarBalance`
12. `getBusinessAccountGifts`
13. `convertGiftToStars`
14. `upgradeGift`
15. `transferGift`
16. `postStory`
17. `editStory`
18. `deleteStory`
19. `repostStory`

### Methods where business_connection_id is OPTIONAL

These methods have a non-business mode (regular bot operation) and gain business-account behavior when the parameter is provided:

20. `sendMessage`
21. `sendPhoto`
22. `sendAudio`
23. `sendDocument`
24. `sendVideo`
25. `sendAnimation`
26. `sendVoice`
27. `sendVideoNote`
28. `sendSticker`
29. `sendChatAction`
30. `sendInvoice`
31. `editMessageText`
32. `editMessageCaption`
33. `editMessageMedia`
34. `editMessageLiveLocation`
35. `stopMessageLiveLocation`
36. `editMessageReplyMarkup`
37. `editMessageChecklist`
38. `stopPoll`

**Total: 38 methods** (19 required + 19 optional)

---

## 8. Naming Discrepancies {#8-naming-discrepancies}

| Incorrect Name | Correct Name | Notes |
|----------------|---------------|-------|
| `businessMessageDeleted` | `BusinessMessagesDeleted` | Type name is PLURAL. No singular variant exists in Bot API. |
| `businessMessageDeleted` (update field) | `deleted_business_messages` | The Update field uses snake_case plural form. |
| `is_business_bot` | `sender_business_bot` | `is_business_bot` does NOT exist anywhere in Bot API. The Message field is `sender_business_bot` and contains a full BusinessConnection object, not a boolean. |
| `can_reply` (on BusinessConnection) | `rights.can_reply` | The standalone `can_reply` field on BusinessConnection was deprecated in favor of the `rights` BusinessBotRights sub-object. Some libraries still expose it. |
| `exclude_limited` (on getBusinessAccountGifts) | `exclude_limited_upgradable` + `exclude_limited_non_upgradable` | The single `exclude_limited` parameter was split into two more granular filters. |
| `exclude_from_blockchain` (on getBusinessAccountGifts) | Removed | This parameter no longer exists in the current API. |

---

## Appendix: Quick Reference Summary

### Business Types Count
- BusinessConnection: 6 fields
- BusinessBotRights: 14 fields
- BusinessMessagesDeleted: 3 fields
- InputChecklist: (sub-fields vary by API version)

### Business Update Types Count
- 4 update fields on Update object

### Business-Only Methods Count
- 19 methods (require business_connection_id)

### Business-Aware Methods Count
- 19 additional methods (optional business_connection_id)
- Grand total: 38 methods

### Rights-Required Mapping

| Right | Methods Requiring It |
|-------|---------------------|
| `can_reply` | sendMessage, sendPhoto, sendAudio, sendDocument, sendVideo, sendAnimation, sendVoice, sendVideoNote, sendSticker, sendChatAction, sendInvoice (when business_connection_id provided) |
| `can_read_messages` | readBusinessMessage |
| `can_delete_sent_messages` | deleteBusinessMessages (for bot-sent messages) |
| `can_delete_all_messages` | deleteBusinessMessages (for all messages) |
| `can_edit_name` | setBusinessAccountName |
| `can_edit_bio` | setBusinessAccountBio |
| `can_edit_username` | setBusinessAccountUsername |
| `can_edit_profile_photo` | setBusinessAccountProfilePhoto, removeBusinessAccountProfilePhoto |
| `can_change_gift_settings` | setBusinessAccountGiftSettings |
| `can_view_gifts_and_stars` | getBusinessAccountStarBalance, getBusinessAccountGifts |
| `can_convert_gifts_to_stars` | convertGiftToStars |
| `can_transfer_and_upgrade_gifts` | upgradeGift, transferGift |
| `can_transfer_stars` | transferBusinessAccountStars |
| `can_manage_stories` | postStory, editStory, deleteStory, repostStory |

---
*End of reference document*
