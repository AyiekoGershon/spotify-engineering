-- ============================================================================
-- 003_triggers.sql
-- Auto-processing: when raw JSON lands, parse it into analytics tables.
-- Run this AFTER 001_raw_landing.sql and 002_analytics.sql.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Trigger 1: BEFORE INSERT — auto-set snapshot_date from fetched_at
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION raw_landing.set_snapshot_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.snapshot_date := NEW.fetched_at::date;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_snapshot_date ON raw_landing.spotify_raw;

CREATE TRIGGER trg_set_snapshot_date
    BEFORE INSERT ON raw_landing.spotify_raw
    FOR EACH ROW
    EXECUTE FUNCTION raw_landing.set_snapshot_date();

-- ----------------------------------------------------------------------------
-- Trigger 2: AFTER INSERT — parse raw JSON into analytics tables
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION raw_landing.process_spotify_playlist_tracks()
RETURNS TRIGGER AS $$
DECLARE
    item        JSONB;
    track       JSONB;
    artist_obj  JSONB;
    trk_id      TEXT;
    art_id      TEXT;
    rank_pos    INTEGER := 0;
    art_order   INTEGER;
BEGIN
    -- Process playlist tracks AND search results
    IF NEW.endpoint NOT LIKE '%playlists%tracks%'
       AND NEW.endpoint NOT LIKE '%search%' THEN
        RETURN NEW;
    END IF;

    -- Iterate over items in the Spotify response
    FOR item IN SELECT * FROM jsonb_array_elements(NEW.raw_json -> 'items')
    LOOP
        track := item -> 'track';

        -- Skip null tracks (deleted/removed from Spotify)
        IF track IS NULL OR track = 'null'::jsonb THEN
            CONTINUE;
        END IF;

        trk_id := track ->> 'id';
        IF trk_id IS NULL THEN
            CONTINUE;
        END IF;

        rank_pos := rank_pos + 1;

        -- ==================================================================
        -- UPSERT Track
        -- ==================================================================
        INSERT INTO analytics.tracks (
            track_id, name, album_name, album_id, album_release_date,
            album_image_url, duration_ms, explicit, preview_url,
            external_url, isrc, first_seen, last_seen, updated_at
        ) VALUES (
            trk_id,
            track ->> 'name',
            track -> 'album' ->> 'name',
            track -> 'album' ->> 'id',
            (track -> 'album' ->> 'release_date')::DATE,
            CASE
                WHEN track -> 'album' -> 'images' IS NOT NULL
                     AND jsonb_array_length(track -> 'album' -> 'images') > 0
                THEN track -> 'album' -> 'images' -> 0 ->> 'url'
                ELSE NULL
            END,
            (track ->> 'duration_ms')::INTEGER,
            (track ->> 'explicit')::BOOLEAN,
            track ->> 'preview_url',
            track -> 'external_urls' ->> 'spotify',
            track -> 'external_ids' ->> 'isrc',
            NEW.fetched_at,   -- first_seen
            NEW.fetched_at,   -- last_seen
            NEW.fetched_at    -- updated_at
        )
        ON CONFLICT (track_id) DO UPDATE SET
            name                = EXCLUDED.name,
            album_name          = EXCLUDED.album_name,
            album_id            = EXCLUDED.album_id,
            album_release_date  = EXCLUDED.album_release_date,
            album_image_url     = COALESCE(EXCLUDED.album_image_url, analytics.tracks.album_image_url),
            duration_ms         = EXCLUDED.duration_ms,
            explicit            = EXCLUDED.explicit,
            preview_url         = COALESCE(EXCLUDED.preview_url, analytics.tracks.preview_url),
            external_url        = EXCLUDED.external_url,
            isrc                = COALESCE(EXCLUDED.isrc, analytics.tracks.isrc),
            last_seen           = EXCLUDED.last_seen,
            updated_at          = EXCLUDED.updated_at;

        -- ==================================================================
        -- UPSERT Artists
        -- ==================================================================
        art_order := 0;
        FOR artist_obj IN SELECT * FROM jsonb_array_elements(track -> 'artists')
        LOOP
            art_id := artist_obj ->> 'id';
            IF art_id IS NULL THEN
                CONTINUE;
            END IF;

            INSERT INTO analytics.artists (
                artist_id, name, external_url, genres, followers,
                popularity, image_url, first_seen, last_seen, updated_at
            ) VALUES (
                art_id,
                artist_obj ->> 'name',
                artist_obj -> 'external_urls' ->> 'spotify',
                '{}',   -- genres not available from playlist tracks endpoint
                NULL,   -- followers not available from playlist tracks endpoint
                NULL,   -- artist popularity not available from playlist tracks endpoint
                NULL,   -- image not available from playlist tracks endpoint
                NEW.fetched_at,
                NEW.fetched_at,
                NEW.fetched_at
            )
            ON CONFLICT (artist_id) DO UPDATE SET
                name       = EXCLUDED.name,
                external_url = COALESCE(EXCLUDED.external_url, analytics.artists.external_url),
                last_seen  = EXCLUDED.last_seen,
                updated_at = EXCLUDED.updated_at;

            -- ==============================================================
            -- Track-Artist junction
            -- ==============================================================
            INSERT INTO analytics.track_artists (track_id, artist_id, artist_order)
            VALUES (
                trk_id,
                art_id,
                art_order
            )
            ON CONFLICT (track_id, artist_id) DO UPDATE SET
                artist_order = EXCLUDED.artist_order;

            art_order := art_order + 1;
        END LOOP;

        -- ==================================================================
        -- Popularity snapshot
        -- ==================================================================
        INSERT INTO analytics.popularity_snapshots (
            track_id, snapshot_date, popularity, rank, raw_id, captured_at
        ) VALUES (
            trk_id,
            NEW.snapshot_date,
            COALESCE((track ->> 'popularity')::INTEGER, 0),
            rank_pos,
            NEW.id,
            NEW.fetched_at
        )
        ON CONFLICT (track_id, snapshot_date) DO UPDATE SET
            popularity  = EXCLUDED.popularity,
            rank        = EXCLUDED.rank,
            raw_id      = EXCLUDED.raw_id,
            captured_at = EXCLUDED.captured_at;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- Trigger: fires AFTER INSERT on raw_landing.spotify_raw
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_process_spotify_raw ON raw_landing.spotify_raw;

CREATE TRIGGER trg_process_spotify_raw
    AFTER INSERT ON raw_landing.spotify_raw
    FOR EACH ROW
    EXECUTE FUNCTION raw_landing.process_spotify_playlist_tracks();
