# Telegram Bot API Stories — Complete Raw Extraction
Source: https://core.telegram.org/bots/api (verified 2026-04-25)

---

## CORRECTIONS TO COMMON ASSUMPTIONS

- Method is `postStory`, NOT `sendStory`
- Position type is `StoryAreaPosition`, NOT `StoryAreaPositioned`
- Area types use `StoryAreaType*` prefix (e.g., `StoryAreaTypeSuggestedReaction`), NOT `StoryArea*`
- There is NO `StoryContent`, `StoryContentPhoto`, `StoryContentVideo`, `StoryContentUnsupported` output type
- Input types are `InputStoryContentPhoto` and `InputStoryContentVideo` (not `StoryContent*`)
- There is NO `StoryInteractionType` enum in the Bot API
- There is NO `StoryAreaVenue` type — location areas use `StoryAreaTypeLocation`
- There is NO `StoryAreaCustomEmoji` type
- There are NO story-related Update types (no StorySent, StoryEdited, StoryDeleted, StoryViewed, etc.)
- A 4th method exists: `repostStory`

---

## METHOD: postStory

Posts a story on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| business_connection_id | String | Yes | Unique identifier of the business connection |
| content | InputStoryContent | Yes | Content of the story |
| active_period | Integer | Yes | Period after which the story is moved to the archive, in seconds; must be one of 6 * 3600, 12 * 3600, 86400, or 2 * 86400 |
| caption | String | Optional | Caption of the story, 0-2048 characters after entities parsing |
| parse_mode | String | Optional | Mode for parsing entities in the story caption. See formatting options for more details. |
| caption_entities | Array of MessageEntity | Optional | A JSON-serialized list of special entities that appear in the caption, which can be specified instead of parse_mode |
| areas | Array of StoryArea | Optional | A JSON-serialized list of clickable areas to be shown on the story |
| post_to_chat_page | Boolean | Optional | Pass True to keep the story accessible after it expires |
| protect_content | Boolean | Optional | Pass True if the content of the story must be protected from forwarding and screenshotting |

---

## METHOD: editStory

Edits a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns Story on success.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| business_connection_id | String | Yes | Unique identifier of the business connection |
| story_id | Integer | Yes | Unique identifier of the story to edit |
| content | InputStoryContent | Yes | Content of the story |
| caption | String | Optional | Caption of the story, 0-2048 characters after entities parsing |
| parse_mode | String | Optional | Mode for parsing entities in the story caption. See formatting options for more details. |
| caption_entities | Array of MessageEntity | Optional | A JSON-serialized list of special entities that appear in the caption, which can be specified instead of parse_mode |
| areas | Array of StoryArea | Optional | A JSON-serialized list of clickable areas to be shown on the story |

---

## METHOD: deleteStory

Deletes a story previously posted by the bot on behalf of a managed business account. Requires the can_manage_stories business bot right. Returns True on success.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| business_connection_id | String | Yes | Unique identifier of the business connection |
| story_id | Integer | Yes | Unique identifier of the story to delete |

---

## METHOD: repostStory

Reposts a story on behalf of a business account from another business account. Both business accounts must be managed by the same bot, and the story on the source account must have been posted (or reposted) by the bot. Requires the can_manage_stories business bot right for both business accounts. Returns Story on success.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| business_connection_id | String | Yes | Unique identifier of the business connection |
| from_chat_id | Integer | Yes | Unique identifier of the chat which posted the story that should be reposted |
| from_story_id | Integer | Yes | Unique identifier of the story that should be reposted |
| active_period | Integer | Yes | Period after which the story is moved to the archive, in seconds; must be one of 6 * 3600, 12 * 3600, 86400, or 2 * 86400 |
| post_to_chat_page | Boolean | Optional | Pass True to keep the story accessible after it expires |
| protect_content | Boolean | Optional | Pass True if the content of the story must be protected from forwarding and screenshotting |

---

## TYPE: Story

This object represents a story.

| Field | Type | Description |
| --- | --- | --- |
| chat | Chat | Chat that posted the story |
| id | Integer | Unique identifier for the story in the chat |

NOTE: The Story type has only 2 fields. No content, caption, areas, or timestamp are exposed via the Bot API.

---

## TYPE: InputStoryContent

This object describes the content of a story to post. Currently, it can be one of:
- InputStoryContentPhoto
- InputStoryContentVideo

---

## TYPE: InputStoryContentPhoto

Describes a photo to post as a story.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the content, must be "photo" |
| photo | String | The photo to post as a story. The photo must be of the size 1080x1920 and must not exceed 10 MB. The photo can't be reused and can only be uploaded as a new file, so you can pass "attach://<file_attach_name>" if the photo was uploaded using multipart/form-data under <file_attach_name>. More information on Sending Files. |

---

## TYPE: InputStoryContentVideo

Describes a video to post as a story.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the content, must be "video" |
| video | String | The video to post as a story. The video must be of the size 720x1280, streamable, encoded with H.265 codec, with key frames added each second in the MPEG4 format, and must not exceed 30 MB. The video can't be reused and can only be uploaded as a new file, so you can pass "attach://<file_attach_name>" if the video was uploaded using multipart/form-data under <file_attach_name>. More information on Sending Files. |
| duration | Float | Optional. Precise duration of the video in seconds; 0-60 |
| cover_frame_timestamp | Float | Optional. Timestamp in seconds of the frame that will be used as the static cover for the story. Defaults to 0.0. |
| is_animation | Boolean | Optional. Pass True if the video has no sound |

---

## TYPE: StoryArea

Describes a clickable area on a story media.

| Field | Type | Description |
| --- | --- | --- |
| position | StoryAreaPosition | Position of the area |
| type | StoryAreaType | Type of the area |

---

## TYPE: StoryAreaType

Describes the type of a clickable area on a story. Currently, it can be one of:
- StoryAreaTypeLocation
- StoryAreaTypeSuggestedReaction
- StoryAreaTypeLink
- StoryAreaTypeWeather
- StoryAreaTypeUniqueGift

---

## TYPE: StoryAreaPosition

Describes the position of a clickable area within a story.

| Field | Type | Description |
| --- | --- | --- |
| x_percentage | Float | The abscissa of the area's center, as a percentage of the media width |
| y_percentage | Float | The ordinate of the area's center, as a percentage of the media height |
| width_percentage | Float | The width of the area's rectangle, as a percentage of the media width |
| height_percentage | Float | The height of the area's rectangle, as a percentage of the media height |
| rotation_angle | Float | The clockwise rotation angle of the rectangle, in degrees; 0-360 |
| corner_radius_percentage | Float | The radius of the rectangle corner rounding, as a percentage of the media width |

---

## TYPE: StoryAreaTypeLocation

Describes a story area pointing to a location. Currently, a story can have up to 10 location areas.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the area, always "location" |
| latitude | Float | Location latitude in degrees |
| longitude | Float | Location longitude in degrees |
| address | LocationAddress | Optional. Address of the location |

---

## TYPE: StoryAreaTypeSuggestedReaction

Describes a story area pointing to a suggested reaction. Currently, a story can have up to 5 suggested reaction areas.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the area, always "suggested_reaction" |
| reaction_type | ReactionType | Type of the reaction |
| is_dark | Boolean | Optional. Pass True if the reaction area has a dark background |
| is_flipped | Boolean | Optional. Pass True if reaction area corner is flipped |

---

## TYPE: StoryAreaTypeLink

Describes a story area pointing to an HTTP or tg:// link. Currently, a story can have up to 3 link areas.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the area, always "link" |
| url | String | HTTP or tg:// URL to be opened when the area is clicked |

---

## TYPE: StoryAreaTypeWeather

Describes a story area containing weather information. Currently, a story can have up to 3 weather areas.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the area, always "weather" |
| temperature | Float | Temperature, in degree Celsius |
| emoji | String | Emoji representing the weather |
| background_color | Integer | A color of the area background in the ARGB format |

---

## TYPE: StoryAreaTypeUniqueGift

Describes a story area pointing to a unique gift. Currently, a story can have at most 1 unique gift area.

| Field | Type | Description |
| --- | --- | --- |
| type | String | Type of the area, always "unique_gift" |
| name | String | Unique name of the gift |

---

## STORY FIELDS IN OTHER TYPES

### Message type — story field
| Field | Type | Description |
| --- | --- | --- |
| story | Story | Optional. Message is a forwarded story |

### Message type — reply_to_story field
| Field | Type | Description |
| --- | --- | --- |
| reply_to_story | Story | Optional. For replies to a story, the original story |

### ChatAdministratorRights — story-related fields
| Field | Type | Description |
| --- | --- | --- |
| can_delete_stories | Boolean | True, if the administrator can delete stories posted by other users |

---

## STORY POSTING RESTRICTIONS

1. Regular bots CANNOT post stories. No method exists for non-business bots.
2. Business account bots ONLY. All four methods require business_connection_id and can_manage_stories right.
3. No Premium requirement stated in Bot API docs. Restriction is business account, not Premium.
4. active_period must be exactly one of: 6*3600 (6h), 12*3600 (12h), 86400 (24h), 2*86400 (48h).
5. Photo: 1080x1920, max 10 MB. Cannot reuse — must upload as new file.
6. Video: 720x1280, streamable, H.265 codec, key frames each second, MPEG4, max 30 MB. Cannot reuse. Duration 0-60s.
7. Caption: 0-2048 characters after entities parsing.
8. Repost: Both accounts managed by same bot. Source story must have been posted/reposted by bot. can_manage_stories required for BOTH accounts.
9. NO story Update types exist. Bots cannot receive story events.
10. NO StoryInteractionType enum exists in Bot API.
11. Story object returned contains only chat and id — no content fields exposed.

---

## AREA COUNT LIMITS PER STORY

| Area Type | Max Count |
| --- | --- |
| StoryAreaTypeLocation | 10 |
| StoryAreaTypeSuggestedReaction | 5 |
| StoryAreaTypeLink | 3 |
| StoryAreaTypeWeather | 3 |
| StoryAreaTypeUniqueGift | 1 |

---

## TYPES THAT DO NOT EXIST IN BOT API

These may exist in MTProto/client API but are NOT in Bot API:
- sendStory (method)
- StoryContent (base type)
- StoryContentPhoto
- StoryContentVideo
- StoryContentUnsupported
- StoryAreaPositioned
- StoryAreaSuggestedReaction
- StoryAreaWeather
- StoryAreaVenue
- StoryAreaCustomEmoji
- StoryInteractionType
- StoryInteraction
- StoryClosed
- StoryOpened
- StoryViewed
- Any story-related Update subtypes
