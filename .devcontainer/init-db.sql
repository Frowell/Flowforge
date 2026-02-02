-- FlowForge: Initial database setup
-- This runs on first container creation only

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- fuzzy text search for workflow names

-- Create a test database for pytest
CREATE DATABASE flowforge_test;
GRANT ALL PRIVILEGES ON DATABASE flowforge_test TO flowforge;
