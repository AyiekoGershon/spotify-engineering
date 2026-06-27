# Spotify Data Platform — Complete Setup Guide

This guide walks you through every single step to get the pipeline running, from creating accounts to watching data flow into your database automatically every night.

**Estimated time:** 30–45 minutes  
**Cost:** Free (Spotify free tier + Supabase free tier + GitHub free tier)

---

## Table of Contents

1. [Create a Spotify App](#1-create-a-spotify-app)
2. [Create a Supabase Project](#2-create-a-supabase-project)
3. [Run the Database Migrations](#3-run-the-database-migrations)
4. [Set Up the Project Locally](#4-set-up-the-project-locally)
5. [Test the Pipeline End-to-End](#5-test-the-pipeline-end-to-end)
6. [Push to GitHub & Set Secrets](#6-push-to-github--set-secrets)
7. [Verify the Automation](#7-verify-the-automation)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Create a Spotify App

### 1.1 — Sign up for a Spotify Developer account

1. Go to **[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)**
2. Click **Log In** (top-right corner)
3. Log in with your regular Spotify account (free or premium — either works)
4. If this is your first time, you'll be asked to accept the Developer Terms of Service. Click **Accept**.

### 1.2 — Create a new app

1. From the Dashboard, click the green **Create app** button
2. Fill in the form:

   | Field | What to enter |
   |---|---|
   | **App name** | `Spotify Data Platform` (or anything you like) |
   | **App description** | `Automated music trend analytics pipeline that collects daily top track data` |
   | **Website** | *(optional — leave blank or put `https://github.com/YOUR_USERNAME`)* |
   | **Redirect URI** | `http://127.0.0.1:8080/callback` |

3. **Check the box** confirming you understand the Developer Terms
4. Click **Save**

> **Why `http://127.0.0.1:8080/callback` for the redirect URI?**  
> As of April 2025, Spotify **no longer allows `localhost`** in redirect URIs. You must use an explicit loopback IP like `http://127.0.0.1:PORT` or `http://[::1]:PORT`.  
> This redirect URI **is actively used** — the one-time authorization script (`get_refresh_token.py`) opens your browser, you log in, and Spotify redirects you back to this address with an authorization code. The script reads that code to obtain a permanent refresh token. After that, the daily collection script uses the refresh token to authenticate without a browser.
> **Important:** The redirect URI in your Spotify app settings must **exactly match** what's in the scripts (`http://127.0.0.1:8080/callback`), including the port number.

### 1.3 — Copy your credentials

1. After creating the app, you'll see a screen showing your app details
2. Click **Settings** in the left sidebar (if not already there)
3. You'll see:

   - **Client ID** — a long string like `a1b2c3d4e5f6...`
   - **Client Secret** — click **View client secret** to reveal it

4. **Copy both values** and save them somewhere temporary (Notepad, password manager, etc.). You'll need them in Step 4.

   ```
   SPOTIFY_CLIENT_ID     = a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
   SPOTIFY_CLIENT_SECRET = x1y2z3w4v5u6t7s8r9q0p1o2n3m4l5k6
   ```

---

## 2. Create a Supabase Project

### 2.1 — Sign up for Supabase

1. Go to **[app.supabase.com](https://app.supabase.com)**
2. Click **Start your project** or **Sign in**
3. Sign in with GitHub (recommended — you'll use GitHub for automation anyway)

### 2.2 — Create a new project

1. Click **New project**
2. Fill in:

   | Field | What to enter |
   |---|---|
   | **Name** | `spotify-analytics` |
   | **Database Password** | Generate a strong password and **save it** (e.g. in a password manager) |
   | **Region** | Pick the one closest to you (e.g. `East US (North Virginia)`) |
   | **Pricing Plan** | `Free` ($0/month — 500MB database, 2 projects, plenty for this) |

3. Click **Create new project** — it takes about 1–2 minutes to provision

### 2.3 — Get your API credentials

1. Once your project is ready, click **Settings** (gear icon in the left sidebar)
2. Click **API** in the submenu
3. Copy these two values:

   | Field | Where to find it |
   |---|---|
   | **Project URL** | Under "Project URL" — looks like `https://abcdefghijklm.supabase.co` |
   | **service_role key** | Scroll down to "Project API keys" → `service_role secret` — **NOT the `anon` key** |

   ```
   SUPABASE_URL          = https://abcdefghijklm.supabase.co
   SUPABASE_SERVICE_KEY  = eyJhbGciOi... (very long string)
   ```

> **Why `service_role` and not `anon`?**  
> The `service_role` key bypasses Row Level Security (RLS) and can write to any table. It's meant for backend scripts — exactly what this pipeline is. Never expose it in a browser or frontend app.

---

## 3. Run the Database Migrations

Now you'll create all the tables, indexes, and triggers inside Supabase.

### 3.1 — Open the SQL Editor

1. In your Supabase project dashboard, click **SQL Editor** in the left sidebar
2. Click **New query**

### 3.2 — Run migration #1 (Raw Landing Layer)

1. Open the file `sql/001_raw_landing.sql` from this project (on your computer)
2. Copy all of its contents (Ctrl+A → Ctrl+C)
3. Paste into the Supabase SQL Editor
4. Click the green **Run** button (or press Ctrl+Enter)
5. You should see: `Success. No rows returned`

### 3.3 — Run migration #2 (Analytics Tables)

1. Click **New query** again
2. Copy all of `sql/002_analytics.sql`
3. Paste and click **Run**
4. You should see: `Success. No rows returned`

### 3.4 — Run migration #3 (Auto-Processing Trigger)

1. Click **New query** again
2. Copy all of `sql/003_triggers.sql`
3. Paste and click **Run**
4. You should see: `Success. No rows returned`

### 3.5 — Verify the tables were created

1. Click **Table Editor** in the left sidebar
2. You should see two schemas in the dropdown at the top:
   - `raw_landing` — contains table `spotify_raw`
   - `analytics` — contains tables `artists`, `tracks`, `track_artists`, `popularity_snapshots`
3. Click into each table — they should all be empty with 0 rows

> If you only see the `public` schema, click the schema dropdown at the top of the Table Editor and select `raw_landing` or `analytics`.

---

## 4. Set Up the Project Locally

### 4.1 — Get the project files

If you cloned this repo from GitHub:

```bash
git clone https://github.com/YOUR_USERNAME/spotify-engineering.git
cd spotify-engineering
```

If the files are on your computer (e.g. Desktop):

```bash
cd "C:\Users\Admin\Desktop\spotify engineering"
```

### 4.2 — Create a Python virtual environment

```bash
# Windows
python -m venv .venv
source .venv/Scripts/activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4.3 — Install dependencies

```bash
pip install -r requirements.txt
```

You should see `spotipy`, `supabase`, `python-dotenv`, and `pytest` install successfully.

### 4.4 — Create your .env file

```bash
cp .env.example .env
```

Now open `.env` in any text editor and fill in the 4 values you saved earlier:

```env
SPOTIFY_CLIENT_ID=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
SPOTIFY_CLIENT_SECRET=x1y2z3w4v5u6t7s8r9q0p1o2n3m4l5k6
SUPABASE_URL=https://abcdefghijklm.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

> **Important:** Never commit `.env` to GitHub. It's already in `.gitignore`.

---

## 5. Test the Pipeline End-to-End

### 5.1 — Run the collection script once

```bash
python scripts/collect_daily.py
```

If everything is set up correctly, you'll see output like:

```
2026-06-27T14:30:00 [INFO] Fetching: Global Top 50 (37i9dQZEVXbMDoHDwVN2tF)
2026-06-27T14:30:02 [INFO]   Landed → raw row 1 | 50 tracks | Global Top 50
2026-06-27T14:30:02 [INFO] Done: 1 playlist(s), 50 tracks, 1 raw rows inserted
```

### 5.2 — Check your data in Supabase

Go back to your Supabase project → **Table Editor**:

| Table | What you should see |
|---|---|
| `raw_landing.spotify_raw` | 1 row — the full raw JSON response from Spotify |
| `analytics.artists` | Dozens of artists extracted automatically |
| `analytics.tracks` | 50 tracks with album info, ISRC codes, etc. |
| `analytics.track_artists` | Track-to-artist mappings |
| `analytics.popularity_snapshots` | 50 rows — one per track with popularity score and chart rank |

> **If `analytics` tables are still empty:** the trigger might not have processed yet. Wait 5 seconds and refresh. If still empty, re-run `sql/003_triggers.sql` in the SQL Editor.

### 5.3 — Run the test suite

```bash
python -m pytest tests/ -v
```

All 8 tests should pass:

```
tests/test_collect.py::test_fetch_playlist_tracks_single_page PASSED
tests/test_collect.py::test_fetch_playlist_tracks_multi_page PASSED
tests/test_collect.py::test_fetch_playlist_tracks_empty PASSED
tests/test_collect.py::test_land_raw_returns_row_id PASSED
tests/test_collect.py::test_land_raw_inserts_correct_shape PASSED
tests/test_collect.py::test_main_success PASSED
tests/test_collect.py::test_main_no_credentials PASSED
tests/test_collect.py::test_main_spotify_api_error_graceful PASSED
```

---

## 6. Push to GitHub & Set Secrets

### 6.1 — Initialize a Git repo (if not already one)

```bash
git init
git add .
git commit -m "Initial commit: Spotify data platform with GitHub Actions automation"
```

### 6.2 — Create a GitHub repository

1. Go to **[github.com/new](https://github.com/new)**
2. Name it `spotify-engineering` (or anything you like)
3. Leave it **Public** (required for free GitHub Actions minutes) or **Private** (limited free minutes)
4. Do NOT check "Add a README", ".gitignore", or "license" — your project already has these
5. Click **Create repository**

### 6.3 — Push your code

```bash
git remote add origin https://github.com/YOUR_USERNAME/spotify-engineering.git
git branch -M main
git push -u origin main
```

### 6.4 — Set GitHub Secrets

Your `.env` file contains sensitive keys. You need to add them as GitHub Secrets so the Actions workflow can use them without exposing them in code.

1. Go to your GitHub repo → **Settings** (tab at the top)
2. Click **Secrets and variables** → **Actions** (left sidebar)
3. Click the green **New repository secret** button
4. Add each secret **one at a time**:

   | Name | Value (from your `.env`) |
   |---|---|
   | `SPOTIFY_CLIENT_ID` | Your Spotify Client ID |
   | `SPOTIFY_CLIENT_SECRET` | Your Spotify Client Secret |
   | `SUPABASE_URL` | Your Supabase Project URL (e.g. `https://abcdefg.supabase.co`) |
   | `SUPABASE_SERVICE_KEY` | Your Supabase `service_role` key |

   After adding all 4, your secrets page should look like:

   ```
   SPOTIFY_CLIENT_ID       ***
   SPOTIFY_CLIENT_SECRET   ***
   SUPABASE_URL            ***
   SUPABASE_SERVICE_KEY    ***
   ```

### 6.5 — Manually trigger the workflow to test

1. Go to your GitHub repo → **Actions** tab
2. Click **Spotify Daily Data Collection** in the left sidebar
3. Click the **Run workflow** dropdown → **Run workflow**
4. Click the green **Run workflow** button
5. The workflow will appear — click it to watch the logs

You should see:
- `Set up job` → green check
- `Checkout repository` → green check
- `Set up Python` → green check
- `Install dependencies` → green check
- `Run daily collection` → green check (with the same output you saw locally)

> **If it fails**, click on the failed step to see the error logs. Most common issue: wrong secret values. Double-check your GitHub Secrets match your `.env` file exactly (no extra spaces, no missing characters).

---

## 7. Verify the Automation

### 7.1 — Check that the schedule is active

The workflow file (`.github/workflows/collect-daily.yml`) has:

```yaml
on:
  schedule:
    - cron: "0 0 * * *"    # midnight UTC every day
```

GitHub will run this automatically at midnight UTC. Depending on your timezone:

| Your timezone | When it runs |
|---|---|
| US Eastern (ET) | 8:00 PM |
| US Pacific (PT) | 5:00 PM |
| UK (BST) | 1:00 AM |
| Central Europe (CET) | 2:00 AM |
| Japan (JST) | 9:00 AM |

### 7.2 — Check after the first automated run

The next morning, check your Supabase Table Editor:

- `raw_landing.spotify_raw` — should now have **2 rows** (your manual test + the automated midnight run)
- `analytics.popularity_snapshots` — should have **100 rows** (50 tracks × 2 days)

If you see 2 rows in `spotify_raw`, the pipeline is working fully autonomously. 🎉

### 7.3 — Try some queries

Head to Supabase SQL Editor and explore:

```sql
-- See all collection runs
SELECT id, fetched_at, endpoint FROM raw_landing.spotify_raw ORDER BY fetched_at DESC;

-- Today's top 10
SELECT * FROM analytics.daily_top_tracks
WHERE snapshot_date = CURRENT_DATE
LIMIT 10;

-- Biggest popularity movers
SELECT * FROM analytics.popularity_movers;

-- Which artists appear most often
SELECT
    a.name,
    COUNT(DISTINCT ps.snapshot_date) AS days_on_chart
FROM analytics.track_artists ta
JOIN analytics.artists a ON ta.artist_id = a.artist_id
JOIN analytics.popularity_snapshots ps ON ta.track_id = ps.track_id
WHERE ta.artist_order = 0
GROUP BY a.name
ORDER BY days_on_chart DESC
LIMIT 20;
```

---

## 8. Troubleshooting

### "ModuleNotFoundError: No module named 'spotipy'"

You forgot to activate the virtual environment:

```bash
source .venv/Scripts/activate   # Windows
source .venv/bin/activate       # macOS/Linux
```

Then re-run `pip install -r requirements.txt`.

### "Spotify API error: 401 Unauthorized"

Your `SPOTIFY_CLIENT_ID` or `SPOTIFY_CLIENT_SECRET` is wrong. Double-check them in the **[Spotify Dashboard](https://developer.spotify.com/dashboard)** → your app → Settings. The Client Secret is NOT the same as the Client ID — make sure you clicked "View client secret."

### "Supabase insert error"

Your `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` is wrong:
- **URL:** Check it ends with `.supabase.co` and has no trailing slash
- **Key:** Make sure it's the `service_role` key, not the `anon` key
- Both are in Supabase → Settings → API

### "Analytics tables are empty after running collect_daily.py"

The trigger might not have been created. Re-run `sql/003_triggers.sql` in the Supabase SQL Editor. If it says the trigger already exists, that's fine — the `DROP TRIGGER IF EXISTS` line handles that.

### "GitHub Actions: workflow not showing up"

Make sure your workflow file is exactly at `.github/workflows/collect-daily.yml` (note the `.github` starts with a dot). Push it to the `main` branch.

### "GitHub Actions: schedule not running"

GitHub Actions schedules can drift by up to 30 minutes during high load. Also, scheduled workflows only run on the default branch, and only if the repo has been active recently. Manually triggering once counts as "active."

### "Supabase free tier limits"

The free tier gives you 500MB of database and pauses after 1 week of inactivity. Since this pipeline writes daily, it will never go inactive. 500MB is enough for roughly **2–3 years** of daily Global Top 50 snapshots.

---

## Quick Reference: All Your Credentials

| Service | Where to get them | Variable name |
|---|---|---|
| Spotify | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → App → Settings | `SPOTIFY_CLIENT_ID` |
| Spotify | Same page → "View client secret" | `SPOTIFY_CLIENT_SECRET` |
| Supabase | [app.supabase.com](https://app.supabase.com) → Project → Settings → API | `SUPABASE_URL` |
| Supabase | Same page → `service_role` key | `SUPABASE_SERVICE_KEY` |
| GitHub | [github.com/settings/tokens](https://github.com/settings/tokens) | *(not needed — push via HTTPS with username + token)* |

---

## What's Next?

Once the pipeline has been running for a week or two, you'll have enough data to:

- **Visualize trends** — Connect [Metabase](https://metabase.com) (free, open-source) directly to your Supabase Postgres URL
- **Track genre explosions** — Add a second playlist like "Viral 50" to `scripts/collect_daily.py`
- **Set up alerts** — Write a SQL query that detects tracks jumping 10+ ranks in one day
- **Build a dashboard** — Use Supabase's built-in charts or any BI tool

The analytics schema is designed to be BI-friendly — the views `daily_top_tracks` and `popularity_movers` work directly with any tool that speaks SQL.
