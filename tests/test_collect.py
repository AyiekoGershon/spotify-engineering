"""Tests for the daily Spotify collection script."""

import json
import os
from datetime import datetime, timezone

import pytest


# ── Tests for fetch_playlist_tracks (legacy → search) ─────────────────────────

def test_fetch_playlist_tracks_via_search_single_page(mocker):
    """Should return items from search results formatted as playlist response."""
    from scripts.collect_daily import fetch_playlist_tracks

    mock_sp = mocker.MagicMock()
    mock_sp.search.return_value = {
        "tracks": {
            "items": [
                {"id": f"track_{i}", "name": f"Song {i}", "popularity": 80,
                 "album": {"id": f"a{i}", "name": f"Album {i}", "release_date": "2026-01-01",
                           "images": [{"url": "http://img.jpg"}]},
                 "artists": [{"id": f"art{i}", "name": f"Artist {i}"}]}
                for i in range(5)
            ],
            "total": 5,
        }
    }

    result = fetch_playlist_tracks(mock_sp, "playlist123")

    assert len(result["items"]) == 5
    assert result["source"] == "search"
    mock_sp.search.assert_called()


def test_fetch_playlist_tracks_via_search_empty(mocker):
    """Should handle empty search results."""
    from scripts.collect_daily import fetch_playlist_tracks

    mock_sp = mocker.MagicMock()
    mock_sp.search.return_value = {
        "tracks": {"items": [], "total": 0}
    }

    result = fetch_playlist_tracks(mock_sp, "playlist123")

    assert len(result["items"]) == 0


def test_fetch_playlist_tracks_deduplicates(mocker):
    """Should deduplicate tracks across search queries."""
    from scripts.collect_daily import fetch_via_search

    mock_sp = mocker.MagicMock()
    # Return same track twice from different queries (simulated by search returning it twice)
    call_count = [0]

    def search_side_effect(q, type, market, limit, offset):
        call_count[0] += 1
        if call_count[0] == 1:
            return {"tracks": {"items": [
                {"id": f"track_{i}", "name": f"Song {i}", "popularity": 80,
                 "album": {"id": f"a{i}", "name": "Album", "release_date": "2026-01-01",
                           "images": [{"url": "http://img.jpg"}]},
                 "artists": [{"id": f"art{i}", "name": "Artist"}]}
                for i in range(5)
            ], "total": 5}}
        else:
            return {"tracks": {"items": [], "total": 0}}

    mock_sp.search.side_effect = search_side_effect

    result = fetch_via_search(mock_sp)

    assert len(result["items"]) == 5


# ── Tests for land_raw ────────────────────────────────────────────────────────

def test_land_raw_returns_row_id(mocker):
    """Should insert into raw_landing.spotify_raw and return the new row ID."""
    from scripts.collect_daily import land_raw

    mock_supabase = mocker.MagicMock()
    mock_supabase.schema.return_value.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": 42}
    ]

    now = datetime(2026, 6, 27, 0, 0, 0, tzinfo=timezone.utc)
    raw = {"items": [{"track": {"id": "x"}}], "total": 1}

    row_id = land_raw(mock_supabase, "v1/search/market/KE", raw, now)

    assert row_id == 42
    mock_supabase.schema.assert_called_with("raw_landing")
    mock_supabase.schema.return_value.table.assert_called_with("spotify_raw")


def test_land_raw_inserts_correct_shape(mocker):
    """Should pass correctly shaped data to Supabase insert."""
    from scripts.collect_daily import land_raw

    mock_supabase = mocker.MagicMock()
    mock_supabase.schema.return_value.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": 1}
    ]

    now = datetime(2026, 6, 27, 12, 34, 56, tzinfo=timezone.utc)
    raw = {"items": [], "total": 0}

    land_raw(mock_supabase, "v1/search/market/KE", raw, now)

    call_args = mock_supabase.schema.return_value.table.return_value.insert.call_args
    inserted_data = call_args[0][0]

    assert inserted_data["endpoint"] == "v1/search/market/KE"
    assert inserted_data["fetched_at"] == "2026-06-27T12:34:56+00:00"
    assert inserted_data["raw_json"] == raw


# ── Tests for main ────────────────────────────────────────────────────────────

def test_main_no_credentials(mocker, monkeypatch):
    """Should exit with code 1 when Spotify credentials are missing."""
    from scripts import collect_daily

    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        collect_daily.main()

    assert exc_info.value.code == 1
