-- ============================================================================
-- 001_raw_landing.sql
-- Raw Landing Layer — immutable storage of Spotify API responses.
-- Run this in Supabase SQL Editor:
--   https://app.supabase.com → your project → SQL Editor
-- ============================================================================

-- 1. Create the raw landing schema --------------------------------------------
CREATE SCHEMA IF NOT EXISTS raw_landing;

-- 2. Create the spotify_raw table ---------------------------------------------
-- Each row = one API call's complete, unmodified response.
CREATE TABLE IF NOT EXISTS raw_landing.spotify_raw (
    id              BIGSERIAL PRIMARY KEY,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    endpoint        TEXT NOT NULL,              -- e.g. 'v1/playlists/{id}/tracks'
    raw_json        JSONB NOT NULL,             -- exact Spotify API response body
    snapshot_date   DATE NOT NULL               -- calendar date of fetch (set by trigger)
);

-- 3. Indexes ------------------------------------------------------------------
-- Fast lookups by time
CREATE INDEX IF NOT EXISTS idx_raw_fetched_at
    ON raw_landing.spotify_raw (fetched_at DESC);

-- Fast lookups by endpoint
CREATE INDEX IF NOT EXISTS idx_raw_endpoint
    ON raw_landing.spotify_raw (endpoint);

-- Enforce ONE snapshot per endpoint per calendar day (no duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_snapshot_per_day
    ON raw_landing.spotify_raw (snapshot_date, endpoint);

-- 4. Grant usage --------------------------------------------------------------
GRANT USAGE ON SCHEMA raw_landing TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA raw_landing TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA raw_landing TO anon, authenticated, service_role;
