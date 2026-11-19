"""Spotify DJ: a small MCP server that lets Claude control Spotify playback.

Usage:
    python spotify_dj.py --auth              one-time Spotify sign-in
    python spotify_dj.py --test "song name"  play a song without Claude (sanity check)
    python spotify_dj.py                     run as a local (stdio) MCP server
    python spotify_dj.py --http --port 8000  run as an HTTP MCP server (for the VPS later)

Needs Spotify Premium and an open Spotify player (PC app, web player or phone).
Never print to stdout in server mode: stdio MCP uses it for the protocol.
"""
import argparse
import functools
import os
import sys
from pathlib import Path

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth
from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE / ".spotify_token_cache"
SCOPES = (
    "user-modify-playback-state "
    "user-read-playback-state "
    "user-read-currently-playing"
)


def load_env() -> None:
    """Minimal .env loader (KEY=VALUE lines) so no extra dependency is needed."""
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


def _auth(open_browser: bool = True) -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=str(CACHE_PATH),
        open_browser=open_browser,
    )


def _sp() -> spotipy.Spotify:
    auth = _auth()
    if not auth.get_cached_token():
        raise RuntimeError("Not signed in to Spotify yet. Run: python spotify_dj.py --auth")
    return spotipy.Spotify(auth_manager=auth)


def _device(sp: spotipy.Spotify, name: str = "") -> str:
    devices = sp.devices().get("devices", [])
    if not devices:
        raise RuntimeError(
            "No Spotify device found. Open Spotify (PC app, web player or phone) "
            "and play anything for a second so it shows up, then try again."
        )
    if name:
        for d in devices:
            if name.lower() in d["name"].lower():
                return d["id"]
    for d in devices:
        if d.get("is_active"):
            return d["id"]
    return devices[0]["id"]


def _find(sp: spotipy.Spotify, query: str, kind: str) -> dict:
    result = sp.search(q=query, type=kind, limit=1)
    items = (result.get(f"{kind}s") or {}).get("items") or []
    items = [i for i in items if i]
    if not items:
        raise RuntimeError(f"No {kind} found for '{query}'.")
    return items[0]


def _describe(item: dict) -> str:
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    return f"{item['name']} by {artists}" if artists else item["name"]


def safe(fn):
    """Turn errors into readable messages for Claude instead of stack traces."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 403:
                return ("Spotify refused the request (403). Playback control needs Premium "
                        "and the right permissions. Try: python spotify_dj.py --auth")
            if e.http_status == 404:
                return ("Spotify couldn't find an active player. Open Spotify somewhere "
                        "and play anything briefly, then retry.")
            return f"Spotify error {e.http_status}: {e.msg}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

    return wrapper


mcp = FastMCP("spotify-dj")


@mcp.tool()
@safe
def play(query: str, kind: str = "track", device_name: str = "") -> str:
    """Search Spotify and start playing the top match immediately.

    query: what to play, e.g. "Labi Siffre Bless the Telephone".
    kind: track, album, playlist or artist.
    device_name: optional part of a device name to play on (default: active device).
    """
    if kind not in ("track", "album", "playlist", "artist"):
        return "kind must be one of: track, album, playlist, artist"
    sp = _sp()
    item = _find(sp, query, kind)
    device = _device(sp, device_name)
    if kind == "track":
        sp.start_playback(device_id=device, uris=[item["uri"]])
    else:
        sp.start_playback(device_id=device, context_uri=item["uri"])
    return f"Playing {kind}: {_describe(item)}"


@mcp.tool()
@safe
def queue_track(query: str) -> str:
    """Search for a track and add it to the end of the play queue."""
    sp = _sp()
    item = _find(sp, query, "track")
    sp.add_to_queue(item["uri"], device_id=_device(sp))
    return f"Queued: {_describe(item)}"


@mcp.tool()
@safe
def pause() -> str:
    """Pause playback."""
    sp = _sp()
    sp.pause_playback(device_id=_device(sp))
    return "Paused."


@mcp.tool()
@safe
def resume() -> str:
    """Resume playback."""
    sp = _sp()
    sp.start_playback(device_id=_device(sp))
    return "Resumed."


@mcp.tool()
@safe
def next_track() -> str:
    """Skip to the next track."""
    sp = _sp()
    sp.next_track(device_id=_device(sp))
    return "Skipped to next track."


@mcp.tool()
@safe
def previous_track() -> str:
    """Go back to the previous track."""
    sp = _sp()
    sp.previous_track(device_id=_device(sp))
    return "Went back to previous track."


@mcp.tool()
@safe
def set_volume(percent: int) -> str:
    """Set playback volume, 0 to 100."""
    sp = _sp()
    percent = max(0, min(100, int(percent)))
    sp.volume(percent, device_id=_device(sp))
    return f"Volume set to {percent}%."


@mcp.tool()
@safe
def now_playing() -> str:
    """Say what is currently playing and on which device."""
    sp = _sp()
    state = sp.current_playback()
    if not state or not state.get("item"):
        return "Nothing is playing right now."
    status = "Playing" if state.get("is_playing") else "Paused"
    device = (state.get("device") or {}).get("name", "unknown device")
    return f"{status}: {_describe(state['item'])} on {device}"


@mcp.tool()
@safe
def list_devices() -> str:
    """List the Spotify devices that are available to play on."""
    sp = _sp()
    devices = sp.devices().get("devices", [])
    if not devices:
        return "No devices found. Open Spotify somewhere and play anything briefly."
    return "\n".join(
        f"- {d['name']} ({d['type']}){' [active]' if d.get('is_active') else ''}"
        for d in devices
    )


@mcp.tool()
@safe
def switch_device(device_name: str) -> str:
    """Move playback to another device by (part of) its name."""
    sp = _sp()
    device = _device(sp, device_name)
    sp.transfer_playback(device_id=device, force_play=True)
    return f"Moved playback to device matching '{device_name}'."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true", help="one-time Spotify sign-in")
    parser.add_argument("--test", metavar="QUERY", help="play a track directly, no Claude")
    parser.add_argument("--http", action="store_true", help="serve over HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        if var not in os.environ:
            sys.exit(f"Missing {var}. Copy .env.example to .env and fill it in.")

    if args.auth:
        auth = _auth()
        token = auth.get_access_token(as_dict=False)
        who = spotipy.Spotify(auth=token).current_user()
        print(f"Signed in as {who.get('display_name') or who['id']}. Token saved to {CACHE_PATH.name}.")
    elif args.test:
        print(play(args.test))
    elif args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()