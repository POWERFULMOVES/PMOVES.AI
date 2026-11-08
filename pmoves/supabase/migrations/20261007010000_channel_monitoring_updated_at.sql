-- pmoves.channel_monitoring carries the update_channel_monitoring_updated_at
-- touch-trigger (pmoves.update_updated_at()) but the table never gained the
-- updated_at column — every UPDATE failed with:
--   record "new" has no field "updated_at"
-- blocking the SoundCloud channel check in channel-monitor (discovered videos
-- could never transition to "processing").
--
-- Idempotent; verified it is the only table in the database with a
-- update_updated_at()-trigger and no updated_at column.

ALTER TABLE pmoves.channel_monitoring
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
