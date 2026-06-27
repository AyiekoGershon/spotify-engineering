"""
Daily Spotify data collection script — works with both Search API and Playlist API.

Fetches popular/top tracks from Spotify and lands raw JSON in Supabase.
Uses Search API by default (works in Developer Mode without playlist access).
Falls back to Playlist API when available.

Usage:
    python scripts/collect_daily.py

Environment variables:
    SPOTIFY_CLIENT_ID       — Spotify Web API client ID
    SPOTIFY_CLIENT_SECRET   — Spotify Web API client secret
    SPOTIFY_REFRESH_TOKEN   — obtained via scripts/get_refresh_token.py (one-time)
    SUPABASE_URL            — Supabase project URL
    SUPABASE_SERVICE_KEY    — Supabase service_role key (bypasses RLS)
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from supabase import create_client

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
# Market for regional track availability (KE = Kenya)
MARKET = os.environ.get("SPOTIFY_MARKET", "KE")

# Number of tracks to collect per run
TRACKS_TO_COLLECT = 50

# Playlist mode (requires app to be out of Developer Mode)
PLAYLIST_ID = os.environ.get("SPOTIFY_PLAYLIST_ID", "7bIhC6dGYVQOFuEG2ym7Rz")  # Top 50 - Kenya

# Search queries for search mode (used when playlist access is unavailable)
SEARCH_QUERIES = [
    "year:2026",          # Recent tracks
    "year:2025",          # Last year
    "genre:afrobeats",   # Popular genre in KE
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("spotify-collect")


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_spotify_client() -> spotipy.Spotify:
    """Authenticate with Spotify."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "").strip()

    if not client_id or not client_secret:
        log.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        sys.exit(1)
    # Authorization Code flow (with refresh token) — required for playlist access
    if refresh_token:
        log.info("Using Authorization Code flow (refresh token)")
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://127.0.0.1:8080/callback",
            scope="playlist-read-private playlist-read-collaborative user-read-private",
        )
        # Get a fresh access token from the refresh token
        try:
            token_info = auth_manager.refresh_access_token(refresh_token)
            access_token = token_info["access_token"]
            log.info("Access token obtained (expires in %ds)", token_info.get("expires_in", 0))
            return spotipy.Spotify(auth=access_token)
        except Exception as e:
            log.error("Failed to refresh access token: %s", e)
            log.error("Try re-running: python scripts/get_refresh_token.py")
            sys.exit(1)
    log.warning("No SPOTIFY_REFRESH_TOKEN — using Client Credentials (limited access)")
    log.warning("Run: python scripts/get_refresh_token.py to authorize")
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret,
    ))


def get_supabase_client():
    """Connect to Supabase with service_role key."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


# ── Data Collection ──────────────────────────────────────────────────────────

# Legacy aliases for backward compatibility with tests
def fetch_playlist_tracks(sp, playlist_id, market="KE"):
    """Legacy wrapper — use fetch_via_search or fetch_via_playlist directly."""
    return fetch_via_search(sp)


def fetch_via_search(sp: spotipy.Spotify) -> dict:
    """
    Fetch popular tracks using Spotify Search API.
    Works in Developer Mode without playlist access.
    Returns data in playlist-like format for the processing trigger.
    """
    all_tracks = {}
    rank = 0

    for query in SEARCH_QUERIES:
        offset = 0
        while len(all_tracks) < TRACKS_TO_COLLECT and offset < 100:
            try:
                results = sp.search(
                    q=query,
                    type="track",
                    market=MARKET,
                    limit=min(10, TRACKS_TO_COLLECT - len(all_tracks)),
                    offset=offset,
                )
            except Exception as e:
                log.warning("Search '%s' offset %d failed: %s", query, offset, e)
                break

            items = results.get("tracks", {}).get("items", [])
            if not items:
                break

            for track in items:
                tid = track.get("id")
                if tid and tid not in all_tracks:
                    rank += 1
                    if "popularity" not in track or track["popularity"] is None:
                        track["popularity"] = 0
                    # Enrich with full track details for album images etc.
                    all_tracks[tid] = {
                        "track": track,
                        "rank": rank,
                    }

            offset += len(items)

    # Format as playlist-like response
    items = [
        {"track": v["track"]}
        for v in sorted(all_tracks.values(), key=lambda x: x["rank"])
    ]

    log.info("Search collected %d unique tracks across %d queries", len(items), len(SEARCH_QUERIES))

    return {
        "items": items[:TRACKS_TO_COLLECT],
        "total": len(items[:TRACKS_TO_COLLECT]),
        "source": "search",
        "queries": SEARCH_QUERIES,
        "market": MARKET,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_via_playlist(sp: spotipy.Spotify) -> dict:
    """Fetch tracks from a Spotify playlist (requires app out of Developer Mode)."""
    all_items = []
    offset = 0
    limit = 100

    while True:
        try:
            results = sp.playlist_tracks(
                PLAYLIST_ID,
                limit=limit,
                offset=offset,
                market=MARKET,
                fields="items(track(id,name,popularity,duration_ms,explicit,"
                       "preview_url,external_urls,external_ids,"
                       "album(id,name,release_date,images),"
                       "artists(id,name,external_urls))),"
                       "total,limit,offset,next",
            )
        except Exception:
            raise

        items = results.get("items", [])
        all_items.extend(items)

        if not results.get("next") or len(items) < limit:
            break
        offset += limit

    return {
        "items": all_items,
        "total": len(all_items),
        "source": "playlist",
        "playlist_id": PLAYLIST_ID,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def land_raw(supabase, endpoint: str, raw_json: dict, fetched_at: datetime) -> int:
    """Insert raw JSON into raw_landing.spotify_raw. Returns the new row ID."""
    data = {
        "endpoint": endpoint,
        "raw_json": raw_json,
        "fetched_at": fetched_at.isoformat(),
    }
    resp = supabase.schema("raw_landing").table("spotify_raw").insert(data).execute()
    return resp.data[0]["id"]


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    now = datetime.now(timezone.utc)
    sp = get_spotify_client()
    supabase = get_supabase_client()

    # Try playlist mode first, fall back to search
    raw_json = None
    endpoint = None
    source = "unknown"

    # Attempt 1: Playlist API
    try:
        log.info("Attempting playlist fetch: %s", PLAYLIST_ID)
        raw_json = fetch_via_playlist(sp)
        endpoint = f"v1/playlists/{PLAYLIST_ID}/tracks"
        source = "playlist"
        log.info("Playlist mode: %d tracks", len(raw_json.get("items", [])))
    except Exception as e:
        log.warning("Playlist API unavailable (Developer Mode?): %s", e)

    # Attempt 2: Search API (fallback)
    if raw_json is None:
        log.info("Falling back to Search API...")
        try:
            raw_json = fetch_via_search(sp)
            endpoint = f"v1/search/market/{MARKET}"
            source = "search"
        except Exception as e:
            log.error("Search API also failed: %s", e)
            return 1

    if not raw_json or not raw_json.get("items"):
        log.error("No tracks collected from any source")
        return 1

    track_count = len(raw_json["items"])

    # Land in Supabase
    try:
        row_id = land_raw(supabase, endpoint, raw_json, now)
    except Exception as e:
        log.error("Supabase insert error: %s", e)
        return 1

    log.info("Landed → raw row %d | %d tracks | source=%s", row_id, track_count, source)
    log.info("Done: %d tracks, 1 raw row inserted", track_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
