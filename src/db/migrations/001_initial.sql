-- Neural Inbox Initial Migration
-- Enables pgvector and creates all tables with tsvector support

-- Enable extensions (Railway PostgreSQL supports these)
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    timezone VARCHAR(50) DEFAULT 'Asia/Almaty',
    language VARCHAR(5) DEFAULT 'ru',
    settings JSONB DEFAULT '{}',
    onboarding_done BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects table (flat, no hierarchy)
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7),
    emoji VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);

-- Items table (main content storage)
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Type and status
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'inbox',

    -- Content
    title VARCHAR(500),
    content TEXT,
    original_input TEXT,
    source VARCHAR(20),

    -- Dates (with hallucination protection - store both raw and normalized)
    due_at TIMESTAMPTZ,
    due_at_raw VARCHAR(100),
    remind_at TIMESTAMPTZ,

    -- Organization
    priority VARCHAR(10),
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    tags JSONB DEFAULT '[]',
    entities JSONB DEFAULT '{}',

    -- Search
    content_tsv TSVECTOR,
    embedding VECTOR(1536),

    -- Metadata for forwards
    origin_user_name VARCHAR(255),
    attachment_file_id VARCHAR(255),
    attachment_type VARCHAR(20),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_type CHECK (type IN ('task', 'idea', 'note', 'resource', 'contact', 'event')),
    CONSTRAINT valid_status CHECK (status IN ('inbox', 'active', 'done', 'archived'))
);

-- Indexes for items
CREATE INDEX IF NOT EXISTS idx_items_user_status ON items(user_id, status);
CREATE INDEX IF NOT EXISTS idx_items_user_type ON items(user_id, type);
CREATE INDEX IF NOT EXISTS idx_items_due_at ON items(due_at) WHERE due_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_items_content_tsv ON items USING GIN(content_tsv);
CREATE INDEX IF NOT EXISTS idx_items_embedding ON items USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_items_tags ON items USING GIN(tags);

-- Item links table (for auto-linking)
CREATE TABLE IF NOT EXISTS item_links (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    related_item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    link_type VARCHAR(20),
    confidence FLOAT,
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(item_id, related_item_id)
);

CREATE INDEX IF NOT EXISTS idx_item_links_item_id ON item_links(item_id);
CREATE INDEX IF NOT EXISTS idx_item_links_related_id ON item_links(related_item_id);

-- Trigger function for auto-updating tsvector
CREATE OR REPLACE FUNCTION update_content_tsv() RETURNS TRIGGER AS $$
BEGIN
    NEW.content_tsv :=
        setweight(to_tsvector('russian', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', COALESCE(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for items table
DROP TRIGGER IF EXISTS items_tsv_trigger ON items;
CREATE TRIGGER items_tsv_trigger
    BEFORE INSERT OR UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION update_content_tsv();

-- Trigger function for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for items updated_at
DROP TRIGGER IF EXISTS items_updated_at_trigger ON items;
CREATE TRIGGER items_updated_at_trigger
    BEFORE UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
