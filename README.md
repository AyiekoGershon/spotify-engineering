# Spotify Music Trend Data Platform 🎵

An automated end-to-end data engineering pipeline designed to collect, archive, and analyze daily music charts. It connects the **Spotify Web API** to a **Supabase** (PostgreSQL) database, runs daily snapshots automatically via **GitHub Actions**, and processes nested payloads in real time using PostgreSQL triggers.

---

## 📐 Architecture Overview

```
                     [ EXTRACT & LOAD ]                             [ TRANSFORM ]
                                                                     
 ┌──────────────┐          ┌────────────────┐          ┌───────────────────────────┐
 │ Spotify API  │ ──(1)──▶ │ GitHub Actions │ ──(2)──▶ │ raw_landing.spotify_raw   │
 │ (Top Charts) │          │  (Daily Cron)  │          │ (Immutable JSONB Archive) │
 └──────────────┘          └────────────────┘          └─────────────┬─────────────┘
                                                                     │
                                                       (3) Postgres Trigger fires
                                                                     │
                                                                     ▼
                                                       ┌───────────────────────────┐
                                                       │ analytics schema          │
                                                       │  ├── tracks               │
                                                       │  ├── artists              │
                                                       │  ├── track_artists (M2M)  │
                                                       │  └── popularity_snapshots │
                                                       └───────────────────────────┘
```

1. **Extract**: A Python script authenticates with Spotify and fetches the target chart tracks.
2. **Load (Immutable Landing)**: The script inserts the raw, unmodified JSON response into `raw_landing.spotify_raw`.
3. **Transform (Real-Time)**: A PostgreSQL `AFTER INSERT` trigger parses the nested JSON payload, normalizing it and upserting data into the `analytics` schema tables.

---

## 🛠️ Repository Directory Structure

This project maintains clean separation between ETL scripting, SQL migrations, configuration, and unit tests:

* 📁 **[scripts](file:///c:/Users/Admin/Desktop/spotify%20engineering/scripts)**
  * 📄 **[collect_daily.py](file:///c:/Users/Admin/Desktop/spotify%20engineering/scripts/collect_daily.py)**: The main entrypoint pipeline that handles authentication, calls Spotify APIs, and pushes payload to Supabase.
  * 📄 **[get_refresh_token.py](file:///c:/Users/Admin/Desktop/spotify%20engineering/scripts/get_refresh_token.py)**: Helper script to execute a one-time OAuth authorization code exchange locally to get a persistent offline refresh token.
* 📁 **[sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql)**
  * 📄 **[001_raw_landing.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/001_raw_landing.sql)**: Database schema migration setting up the raw landing layer table and indexes.
  * 📄 **[002_analytics.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/002_analytics.sql)**: Database schema migration building structured tables and analytical views.
  * 📄 **[003_triggers.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/003_triggers.sql)**: Contains PL/pgSQL trigger procedures that extract and upsert structured data from raw JSON.
* 📁 **[tests](file:///c:/Users/Admin/Desktop/spotify%20engineering/tests)**
  * 📄 **[test_collect.py](file:///c:/Users/Admin/Desktop/spotify%20engineering/tests/test_collect.py)**: Python unit test suite checking mocking, search fallbacks, and DB insertions.
  * 📄 **[verify.py](file:///c:/Users/Admin/Desktop/spotify%20engineering/tests/verify.py)**: A canonical validation harness confirming file integrity, package imports, and SQL constraints.
* 📁 **.github/workflows**
  * 📄 **[collect-daily.yml](file:///c:/Users/Admin/Desktop/spotify%20engineering/.github/workflows/collect-daily.yml)**: The GitHub Actions YAML workflow automating the script runs daily at midnight UTC.
* 📄 **[SETUP.md](file:///c:/Users/Admin/Desktop/spotify%20engineering/SETUP.md)**: Detailed step-by-step setup guide with screenshots and credentials workflow.
* 📄 **[requirements.txt](file:///c:/Users/Admin/Desktop/spotify%20engineering/requirements.txt)**: List of Python dependencies.
* 📄 **[pyproject.toml](file:///c:/Users/Admin/Desktop/spotify%20engineering/pyproject.toml)**: Project configuration.
* 📄 **[.env.example](file:///c:/Users/Admin/Desktop/spotify%20engineering/.env.example)**: Environment credential template.

---

## ⚡ Quick Start

For detailed step-by-step instructions, see the complete **[SETUP.md Guide](file:///c:/Users/Admin/Desktop/spotify%20engineering/SETUP.md)**. Below is a quick setup summary:

### 1. Local Environment Configuration
```bash
# Clone the repository and navigate to the directory
cd "spotify engineering"

# Create and activate a Python virtual environment
python -m venv .venv
source .venv/Scripts/activate # Windows
# source .venv/bin/activate   # macOS / Linux

# Install required dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```
Fill in the credentials in `.env` with your Spotify Client details and your Supabase Database keys.

### 2. Database Migrations
Go to your **Supabase Dashboard ➔ SQL Editor** and execute the migration scripts in order:
1. **[001_raw_landing.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/001_raw_landing.sql)**
2. **[002_analytics.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/002_analytics.sql)**
3. **[003_triggers.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/003_triggers.sql)**

### 3. Pipeline Testing
Verify the pipeline by executing the automated test suite and running the collector locally:
```bash
# Run pytest tests
python -m pytest tests/ -v

# Run the verification script
python tests/verify.py

# Run collection script locally
python scripts/collect_daily.py
```

---

## 🧠 Difficulties Faced During Implementation

Building this pipeline involved overcoming several distinct integration, security, and schema modeling challenges. The details below outline the specific difficulties encountered and their resolutions:

### 1. Spotify's Redirect URI Policy
* **The Problem**: Spotify updated its OAuth policies (as of April 2025) and no longer accepts standard `localhost` domains for Redirect URIs in API settings.
* **The Resolution**: Setting up the callback loopback forced the explicit use of the IP address `http://127.0.0.1:8080/callback` (or `http://[::1]:PORT` for IPv6) in both the Spotify Developer Dashboard settings and our scripts.

### 2. Spotify App Developer Mode Restrictions
* **The Problem**: Newly created Spotify Developer apps start in "Developer Mode", which blocks accessing public playlists or other users' private profiles without specific user authorization, and limits the app to explicitly registered users. This resulted in `403 Forbidden` API exceptions when attempting to use default playlist endpoints.
* **The Resolution**: A hybrid data-collection system was introduced in **[collect_daily.py](file:///c:/Users/Admin/Desktop/spotify%20engineering/scripts/collect_daily.py)**. The script tries to fetch a target chart playlist (`fetch_via_playlist`) using the playlist endpoint; if that fails or is unauthorized, it falls back seamlessly to the **Spotify Search API** (`fetch_via_search`). It queries popular tracks in specific markets for recent years (e.g. `year:2026`, `year:2025`) and builds a playlist-like JSON payload structured dynamically so the downstream database trigger can process both payloads identically.

### 3. Extraction & Schema Mappings in Database Triggers
* **The Problem**: Parsing complex nested JSON payloads inside database code can be slow and error-prone. In addition, the Spotify Playlist Tracks endpoint does not return comprehensive artist information (such as artist genres, images, or follower count). Querying a separate endpoint for each artist in Python would exceed API rate limits and drastically slow down performance.
* **The Resolution**: 
  * Handled raw schema transformations entirely within PostgreSQL via **[003_triggers.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/003_triggers.sql)** triggers using Postgres `JSONB` path operators.
  * Extracted primary and secondary artist relationships inside loops while preserving `artist_order`.
  * Set missing fields (e.g. artist genres and followers) to standard SQL defaults (`'{}'` text arrays and `NULL`). Upon re-encountering the same artist, the trigger performs a non-destructive upsert (`ON CONFLICT (artist_id) DO UPDATE`), keeping existing metadata intact.
  * Resolved track availability differences (e.g., when a track is deleted or disabled in a target market) by skipping null objects in loop items.

### 4. Supabase Row Level Security (RLS) Write Restrictions
* **The Problem**: Executing the collection script originally threw database access errors. By default, Supabase applies strict Row Level Security (RLS) rules to any new tables, preventing anonymous writes.
* **The Resolution**: The pipeline was configured to authenticate using the project's secret **`service_role` key** (`SUPABASE_SERVICE_KEY`) instead of the public anonymous key (`anon`). The `service_role` key bypasses RLS constraints, making it suitable for secure backend pipelines running in automated environments.

### 5. Automated Pipeline Authentication & Secrets Management
* **The Problem**: Maintaining standard API keys inside automated GitHub Actions workflows is simple, but Spotify's OAuth tokens expire after 1 hour. Storing access tokens in configurations would cause daily automated jobs to fail due to expired credentials.
* **The Resolution**: Designed a two-tiered auth mechanism.
  1. A one-time setup script, **[get_refresh_token.py](file:///c:/Users/Admin/Desktop/spotify%20engineering/scripts/get_refresh_token.py)**, runs locally to generate a persistent **Refresh Token** via browser redirection.
  2. This token is saved to the **GitHub Actions secrets** repository (`SPOTIFY_REFRESH_TOKEN`). 
  3. Every night, the GitHub runner pulls the refresh token, requests a fresh, short-lived Access Token programmatically, and runs the collector hands-free without browser interaction.

### 6. Ensuring Collection Idempotency
* **The Problem**: If the collection script ran multiple times a day (either due to manual workflow triggers or pipeline retries), it would insert duplicate raw records, which in turn would insert duplicate records in `analytics.popularity_snapshots`, corrupting daily ranking records.
* **The Resolution**: Added a database constraint in **[001_raw_landing.sql](file:///c:/Users/Admin/Desktop/spotify%20engineering/sql/001_raw_landing.sql)**: a unique index on `(snapshot_date, endpoint)` on the raw landing table. The triggers handle updates using `ON CONFLICT (track_id, snapshot_date) DO UPDATE` to overwrite rank and popularity scores, making the landing process completely idempotent.

---

## 📈 Query Examples & Analytics Recipes

Here are some SQL recipes to run inside the Supabase SQL Editor once your data starts accumulating:

### 1. Analyze Popularity Over Time for a Track
```sql
SELECT snapshot_date, popularity, rank
FROM analytics.popularity_snapshots
WHERE track_id = 'INSERT_SPOTIFY_TRACK_ID'
ORDER BY snapshot_date DESC;
```

### 2. Retrieve Today's Top 10 Chart
```sql
SELECT rank, track_name, artists, popularity
FROM analytics.daily_top_tracks
WHERE snapshot_date = CURRENT_DATE
ORDER BY rank ASC
LIMIT 10;
```

### 3. Track the Biggest Chart Movers (Rising / Falling Tracks)
```sql
SELECT track_name, artists, current_popularity, previous_popularity, delta
FROM analytics.popularity_movers
ORDER BY delta DESC
LIMIT 10;
```

### 4. Identify Top Performing Artists
```sql
SELECT 
    a.name AS artist_name, 
    COUNT(DISTINCT ps.snapshot_date) AS total_days_on_chart,
    AVG(ps.popularity) AS average_track_popularity
FROM analytics.track_artists ta
JOIN analytics.artists a ON ta.artist_id = a.artist_id
JOIN analytics.popularity_snapshots ps ON ta.track_id = ps.track_id
WHERE ta.artist_order = 0  -- Filter for primary artist only
GROUP BY a.name
ORDER BY total_days_on_chart DESC, average_track_popularity DESC
LIMIT 15;
```

---

## 🧪 Running Automated Tests

A comprehensive test suite validates the endpoints, JSON mocks, and database integrations.

To execute tests locally:
```bash
# Run tests with details
python -m pytest tests/ -v
```

This tests:
* `fetch_playlist_tracks` mocking behavior for single, multi-page, and empty API results.
* Fallback mechanics matching the Search API.
* Exact payload shapes for the Supabase `raw_landing` insertion.
* Failure state testing (invalid credentials, API timeout handling).
