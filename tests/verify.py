"""Canonical verification script for the Spotify Data Platform project."""
import os, sys, subprocess, ast

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(PROJECT, ".venv", "Scripts", "python.exe")
ok = fail = 0

def chk(desc, passed, detail=""):
    global ok, fail
    (ok := ok + 1) if passed else (fail := fail + 1)
    print(f"  {'PASS' if passed else 'FAIL'}  {desc}" + (f"  — {detail}" if not passed else ""))

# 1. Tests
r = subprocess.run([VENV, "-m", "pytest", "tests/", "-q", "--tb=line"],
                   capture_output=True, text=True, timeout=60, cwd=PROJECT)
chk("pytest suite passes", r.returncode == 0, r.stdout.splitlines()[-2:])

# 2. Script structure
with open(os.path.join(PROJECT, "scripts", "collect_daily.py")) as f:
    c = f.read()
for fn in ["get_spotify_client", "get_supabase_client", "fetch_playlist_tracks",
           "fetch_via_search", "fetch_via_playlist", "land_raw", "main"]:
    chk(f"fn {fn}", f"def {fn}" in c)
chk("search fallback", "Falling back to Search" in c)
chk("market=KE", "MARKET" in c and "KE" in c)
chk("syntax valid", bool(ast.parse(c)))

# 3. Trigger SQL
with open(os.path.join(PROJECT, "sql", "003_triggers.sql")) as f:
    t = f.read()
chk("trigger: search endpoints", "%search%" in t)
chk("trigger: playlist endpoints", "%playlists%tracks%" in t)

# 4. Imports
r = subprocess.run([VENV, "-c", "from spotipy.oauth2 import SpotifyOAuth; print('ok')"],
                   capture_output=True, text=True, timeout=30)
chk("SpotifyOAuth importable", r.returncode == 0)

# 5. All SQL + source files exist
for f in ["sql/001_raw_landing.sql", "sql/002_analytics.sql", "sql/003_triggers.sql",
          "scripts/collect_daily.py", "scripts/get_refresh_token.py",
          ".github/workflows/collect-daily.yml", ".env.example", "README.md", "SETUP.md"]:
    chk(f"file: {f}", os.path.isfile(os.path.join(PROJECT, f)))

print(f"\n{'='*50}\n{ok} passed, {fail} failed\n{'='*50}")
sys.exit(0 if fail == 0 else 1)
