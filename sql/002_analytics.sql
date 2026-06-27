-- ============================================================================
-- 002_analytics.sql
-- Analytics Layer — flattened, deduplicated, query-ready tables.
-- Run this AFTER 001_raw_landing.sql.
-- ============================================================================

-- 1. Create the analytics schema ----------------------------------------------
CREATE SCHEMA IF NOT EXISTS analytics;

-- 2. Artists table ------------------------------------------------------------
-- One row per unique Spotify artist. Updated (not duplicated) on re-encounter.
CREATE TABLE IF NOT EXISTS analytics.artists (
    artist_id       TEXT PRIMARY KEY,           -- Spotify artist ID
    name            TEXT NOT NULL,
    external_url    TEXT,                       -- Spotify artist link
    genres          TEXT[],                     -- Postgres text array
    followers       INTEGER,                   -- follower count at last fetch
    popularity      INTEGER,                   -- 0-100 artist popularity score
    image_url       TEXT,                       -- largest available artist image
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artists_name
    ON analytics.artists (name);

CREATE INDEX IF NOT EXISTS idx_artists_popularity
    ON analytics.artists (popularity DESC);

-- 3. Tracks table -------------------------------------------------------------
-- One row per unique Spotify track.
CREATE TABLE IF NOT EXISTS analytics.tracks (
    track_id            TEXT PRIMARY KEY,        -- Spotify track ID
    name                TEXT NOT NULL,
    album_name          TEXT,
    album_id            TEXT,
    album_release_date  DATE,
    album_image_url     TEXT,
    duration_ms         INTEGER,
    explicit            BOOLEAN,
    preview_url         TEXT,
    external_url        TEXT,
    isrc                TEXT,                    -- International Standard Recording Code
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tracks_name
    ON analytics.tracks (name);

CREATE INDEX IF NOT EXISTS idx_tracks_isrc
    ON analytics.tracks (isrc);

-- 4. Track-Artist junction ----------------------------------------------------
-- Many-to-many: a track can have multiple artists, an artist can have many tracks.
CREATE TABLE IF NOT EXISTS analytics.track_artists (
    track_id        TEXT NOT NULL REFERENCES analytics.tracks(track_id) ON DELETE CASCADE,
    artist_id       TEXT NOT NULL REFERENCES analytics.artists(artist_id) ON DELETE CASCADE,
    artist_order    INTEGER NOT NULL DEFAULT 0,  -- 0 = primary artist, 1+ = featured
    PRIMARY KEY (track_id, artist_id)
);

CREATE INDEX IF NOT EXISTS idx_track_artists_artist
    ON analytics.track_artists (artist_id);

-- 5. Popularity snapshots -----------------------------------------------------
-- Time-series: one row per track per snapshot_date.
-- This is the core analytics table — tracks popularity changes over time.
CREATE TABLE IF NOT EXISTS analytics.popularity_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    track_id        TEXT NOT NULL REFERENCES analytics.tracks(track_id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL,
    popularity      INTEGER NOT NULL,              -- 0-100 Spotify track popularity
    rank            INTEGER,                       -- position in the fetched chart/playlist
    raw_id          BIGINT REFERENCES raw_landing.spotify_raw(id),  -- trace back to source
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (track_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_pop_track_date
    ON analytics.popularity_snapshots (track_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_pop_date
    ON analytics.popularity_snapshots (snapshot_date DESC);

-- 6. View: daily top tracks ---------------------------------------------------
-- Convenience view joining tracks + artists + latest popularity.
CREATE OR REPLACE VIEW analytics.daily_top_tracks AS
SELECT
    ps.snapshot_date,
    ps.rank,
    ps.popularity,
    t.track_id,
    t.name                                                   AS track_name,
    t.album_name,
    t.album_release_date,
    t.duration_ms,
    t.explicit,
    t.external_url                                           AS track_url,
    t.album_image_url,
    string_agg(a.name, ', ' ORDER BY ta.artist_order ASC)    AS artists,
    string_agg(a.artist_id, ',' ORDER BY ta.artist_order ASC) AS artist_ids
FROM analytics.popularity_snapshots ps
JOIN analytics.tracks t ON ps.track_id = t.track_id
LEFT JOIN analytics.track_artists ta ON t.track_id = ta.track_id
LEFT JOIN analytics.artists a ON ta.artist_id = a.artist_id
GROUP BY
    ps.snapshot_date, ps.rank, ps.popularity,
    t.track_id, t.name, t.album_name, t.album_release_date,
    t.duration_ms, t.explicit, t.external_url, t.album_image_url
ORDER BY ps.snapshot_date DESC, ps.rank ASC;

-- 7. View: popularity deltas --------------------------------------------------
-- Tracks with the biggest popularity change between the two most recent snapshots.
CREATE OR REPLACE VIEW analytics.popularity_movers AS
WITH latest AS (
    SELECT track_id, popularity, snapshot_date, rank
    FROM analytics.popularity_snapshots
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM analytics.popularity_snapshots)
),
previous AS (
    SELECT track_id, popularity
    FROM analytics.popularity_snapshots
    WHERE snapshot_date = (
        SELECT DISTINCT snapshot_date
        FROM analytics.popularity_snapshots
        WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM analytics.popularity_snapshots)
        ORDER BY snapshot_date DESC
        LIMIT 1
    )
)
SELECT
    l.snapshot_date,
    l.rank,
    t.name                                    AS track_name,
    l.popularity                              AS current_popularity,
    COALESCE(p.popularity, l.popularity)      AS previous_popularity,
    l.popularity - COALESCE(p.popularity, l.popularity) AS delta,
    t.album_name,
    string_agg(a.name, ', ' ORDER BY ta.artist_order ASC) AS artists
FROM latest l
JOIN analytics.tracks t ON l.track_id = t.track_id
LEFT JOIN previous p ON l.track_id = p.track_id
LEFT JOIN analytics.track_artists ta ON t.track_id = ta.track_id
LEFT JOIN analytics.artists a ON ta.artist_id = a.artist_id
GROUP BY l.snapshot_date, l.rank, t.name, l.popularity, p.popularity, t.album_name
ORDER BY delta DESC;

-- 8. Grant usage --------------------------------------------------------------
GRANT USAGE ON SCHEMA analytics TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA analytics TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA analytics TO anon, authenticated, service_role;
