-- Add reason column to item_links table
-- This column stores the agent-generated reason for the link

ALTER TABLE item_links ADD COLUMN IF NOT EXISTS reason VARCHAR(200);
