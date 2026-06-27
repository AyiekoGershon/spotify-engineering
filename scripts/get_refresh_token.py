"""
One-time script to get a Spotify refresh token via Authorization Code flow.

Run this ONCE to authorize your app, then save the refresh token to .env.
After that, the daily collection script uses the refresh token (no browser needed).

Usage:
    python scripts/get_refresh_token.py

You'll be prompted to:
    1. Open a URL in your browser
    2. Log in to Spotify
    3. Copy the URL you're redirected to
    4. Paste it here

The refresh token is printed and also saved to .env automatically.
"""

import os
import sys
from dotenv import load_dotenv, set_key
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8080/callback"

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env")
    sys.exit(1)

# Scopes needed: playlist-read-private for owned playlists,
# playlist-read-collaborative for collaborative playlists,
# but for public playlists like Global Top 50, user-read-private is enough
SCOPE = "playlist-read-private playlist-read-collaborative user-read-private"

sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    cache_path=None,  # don't cache — we want the raw refresh token
    show_dialog=True,
)

# Step 1: Get authorization URL
auth_url = sp_oauth.get_authorize_url()
print("=" * 70)
print("  SPOTIFY REFRESH TOKEN SETUP")
print("=" * 70)
print()
print("1. Open this URL in your browser:")
print()
print(f"   {auth_url}")
print()
print("2. Log in to Spotify and click 'Agree' to authorize the app")
print("3. After authorizing, you'll be redirected to a URL that looks like:")
print()
print("   http://127.0.0.1:8080/callback?code=AQB...xyz")
print()
print("   (The page might not load — that's fine. Just copy the ENTIRE URL")
print("    from the address bar and paste it below.)")
print()

# Step 2: Get the redirect URL from user
redirect_url = input("Paste the redirect URL here: ").strip()

if not redirect_url or "code=" not in redirect_url:
    print("\n❌ Invalid redirect URL. Make sure you paste the full URL including '?code=...'")
    sys.exit(1)

# Step 3: Exchange code for tokens
try:
    code = sp_oauth.parse_auth_response_url(redirect_url)
    token_info = sp_oauth.get_access_token(code, check_cache=False)
except Exception as e:
    print(f"\n❌ Failed to get token: {e}")
    print("   Make sure the redirect URL in your Spotify app settings is:")
    print(f"   {REDIRECT_URI}")
    print("   Go to https://developer.spotify.com/dashboard → your app → Edit Settings")
    sys.exit(1)

refresh_token = token_info.get("refresh_token")
access_token = token_info.get("access_token")

if not refresh_token:
    print("\n❌ No refresh token returned. Try again and make sure to click 'Agree'.")
    sys.exit(1)

print(f"\n✅ Authorization successful!")
print(f"   Access token: {access_token[:20]}...")
print(f"   Refresh token: {refresh_token}")

# Step 4: Save to .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
set_key(env_path, "SPOTIFY_REFRESH_TOKEN", refresh_token)
print(f"\n✅ Refresh token saved to .env as SPOTIFY_REFRESH_TOKEN")

# Step 5: Verify it works
print("\n=== Verifying refresh token works ===")
try:
    from spotipy.oauth2 import SpotifyOAuth
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=None,
    ))
    # Try the playlist
    result = sp.playlist_tracks("37i9dQZEVXbMDoHDwVN2tF", limit=3)
    count = len(result.get("items", []))
    print(f"✅ Playlist access works! Fetched {count} tracks.")
except Exception as e:
    print(f"⚠️  Verification failed: {e}")
    print("   The refresh token is saved but may need different scopes.")

print("\nDone! You can now run: python scripts/collect_daily.py")
