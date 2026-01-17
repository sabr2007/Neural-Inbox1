-- Add attachment_name column to items table for storing original filename
-- This column stores the original filename of the uploaded file

ALTER TABLE items ADD COLUMN IF NOT EXISTS attachment_name VARCHAR(255);
