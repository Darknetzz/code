"""
Export Spotify playlists to TXT / JSON / CSV.

Usage:
    pip install spotipy
    python pyspotify.py --formats txt json csv --output-dir exports

Notes:
    - If credentials are missing, the script prompts for them interactively.
    - If you choose to save prompted credentials, they are stored at:
      Python/pyspotify/.env (same folder as this script).
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
from pathlib import Path
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth


SCOPE = "playlist-read-private playlist-read-collaborative"
REQUIRED_ENV_VARS = (
    "SPOTIPY_CLIENT_ID",
    "SPOTIPY_CLIENT_SECRET",
    "SPOTIPY_REDIRECT_URI",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Spotify playlists to TXT / JSON / CSV."
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["txt", "json", "csv"],
        default=["txt", "json", "csv"],
        help="One or more formats to export (default: txt json csv).",
    )
    parser.add_argument(
        "--output-dir",
        default="exports",
        help="Directory where exported files are written (default: exports).",
    )
    return parser.parse_args()


def load_env_file(env_path: Path) -> dict[str, str]:
    # Minimal .env reader: supports KEY=VALUE lines and ignores comments/blank lines.
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def save_env_file(env_path: Path, values: dict[str, str]) -> None:
    # Merge new values with existing keys so we do not lose unrelated entries.
    existing = load_env_file(env_path)
    existing.update(values)

    lines = [f"{key}={value}" for key, value in sorted(existing.items())]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_spotify_credentials() -> None:
    # Keep credentials local to this script directory for predictable behavior.
    env_path = Path(__file__).resolve().parent / ".env"
    file_values = load_env_file(env_path)

    # Environment variables take precedence; .env only fills missing values.
    for key in REQUIRED_ENV_VARS:
        if not os.environ.get(key) and file_values.get(key):
            os.environ[key] = file_values[key]

    # Prompt only for values still missing.
    prompted_values: dict[str, str] = {}
    for key in REQUIRED_ENV_VARS:
        if os.environ.get(key):
            continue
        prompt = f"{key}: "
        if key == "SPOTIPY_CLIENT_SECRET":
            value = getpass.getpass(prompt)
        else:
            value = input(prompt).strip()
        if value:
            os.environ[key] = value
            prompted_values[key] = value

    missing = [key for key in REQUIRED_ENV_VARS if not os.environ.get(key)]
    if missing:
        missing_csv = ", ".join(missing)
        raise RuntimeError(
            f"Missing required Spotify credentials: {missing_csv}. "
            "Set them as environment variables or provide them when prompted."
        )

    if prompted_values:
        choice = input("Save entered credentials to .env for next time? [y/N]: ").strip().lower()
        if choice in {"y", "yes"}:
            save_env_file(env_path, prompted_values)
            print(f"Saved credentials to {env_path}")


def get_spotify_client() -> spotipy.Spotify:
    ensure_spotify_credentials()
    auth_manager = SpotifyOAuth(scope=SCOPE, open_browser=True)
    return spotipy.Spotify(auth_manager=auth_manager)


def iter_paginated(fetch_page) -> list[dict[str, Any]]:
    # Reusable pagination helper for Spotify endpoints that support limit/offset.
    items: list[dict[str, Any]] = []
    offset = 0
    limit = 50

    while True:
        page = fetch_page(limit=limit, offset=offset)
        page_items = page.get("items", [])
        items.extend(page_items)
        if len(page_items) < limit:
            break
        offset += limit

    return items


def fetch_all_playlists(sp: spotipy.Spotify) -> list[dict[str, Any]]:
    return iter_paginated(lambda limit, offset: sp.current_user_playlists(limit=limit, offset=offset))


def fetch_all_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[dict[str, Any]]:
    return iter_paginated(
        lambda limit, offset: sp.playlist_items(
            playlist_id=playlist_id,
            limit=limit,
            offset=offset,
            additional_types=("track",),
        )
    )


def normalize_track(item: dict[str, Any]) -> dict[str, Any] | None:
    # Skip entries where Spotify returns a removed/unavailable track.
    track = item.get("track")
    if not track:
        return None

    artists = [artist.get("name", "") for artist in track.get("artists", []) if artist]
    album = track.get("album", {}).get("name", "") if track.get("album") else ""
    return {
        "id": track.get("id"),
        "name": track.get("name"),
        "artists": artists,
        "album": album,
        "duration_ms": track.get("duration_ms"),
        "explicit": track.get("explicit"),
        "track_number": track.get("track_number"),
        "disc_number": track.get("disc_number"),
        "added_at": item.get("added_at"),
        "added_by": (item.get("added_by") or {}).get("id"),
        "is_local": item.get("is_local", False),
        "uri": track.get("uri"),
        "external_url": (track.get("external_urls") or {}).get("spotify"),
    }


def build_export_payload(sp: spotipy.Spotify) -> list[dict[str, Any]]:
    # Build one normalized structure that all exporters can reuse.
    payload: list[dict[str, Any]] = []
    playlists = fetch_all_playlists(sp)

    for playlist in playlists:
        playlist_id = playlist.get("id")
        if not playlist_id:
            continue

        raw_tracks = fetch_all_playlist_tracks(sp, playlist_id)
        tracks = [normalized for item in raw_tracks if (normalized := normalize_track(item))]

        payload.append(
            {
                "id": playlist_id,
                "name": playlist.get("name", ""),
                "description": playlist.get("description", ""),
                "owner": (playlist.get("owner") or {}).get("display_name", ""),
                "owner_id": (playlist.get("owner") or {}).get("id", ""),
                "public": playlist.get("public"),
                "collaborative": playlist.get("collaborative"),
                "snapshot_id": playlist.get("snapshot_id"),
                "external_url": (playlist.get("external_urls") or {}).get("spotify"),
                "total_tracks_reported": (playlist.get("tracks") or {}).get("total"),
                "tracks_exported": len(tracks),
                "tracks": tracks,
            }
        )

    return payload


def write_json(output_dir: Path, playlists: list[dict[str, Any]]) -> Path:
    out_file = output_dir / "spotify_playlists.json"
    out_file.write_text(json.dumps(playlists, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_file


def write_csv(output_dir: Path, playlists: list[dict[str, Any]]) -> Path:
    out_file = output_dir / "spotify_playlists.csv"
    fieldnames = [
        "playlist_id",
        "playlist_name",
        "playlist_owner",
        "playlist_public",
        "playlist_external_url",
        "track_id",
        "track_name",
        "track_artists",
        "track_album",
        "duration_ms",
        "explicit",
        "track_number",
        "disc_number",
        "added_at",
        "added_by",
        "is_local",
        "track_uri",
        "track_external_url",
    ]

    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # Flatten playlist + track data into one row per track.
        for playlist in playlists:
            for track in playlist["tracks"]:
                writer.writerow(
                    {
                        "playlist_id": playlist["id"],
                        "playlist_name": playlist["name"],
                        "playlist_owner": playlist["owner"],
                        "playlist_public": playlist["public"],
                        "playlist_external_url": playlist["external_url"],
                        "track_id": track["id"],
                        "track_name": track["name"],
                        "track_artists": ", ".join(track["artists"]),
                        "track_album": track["album"],
                        "duration_ms": track["duration_ms"],
                        "explicit": track["explicit"],
                        "track_number": track["track_number"],
                        "disc_number": track["disc_number"],
                        "added_at": track["added_at"],
                        "added_by": track["added_by"],
                        "is_local": track["is_local"],
                        "track_uri": track["uri"],
                        "track_external_url": track["external_url"],
                    }
                )
    return out_file


def write_txt(output_dir: Path, playlists: list[dict[str, Any]]) -> Path:
    out_file = output_dir / "spotify_playlists.txt"
    lines: list[str] = []

    for playlist in playlists:
        # Human-readable section per playlist.
        lines.append(f"# {playlist['name']}")
        lines.append(f"Owner: {playlist['owner']} ({playlist['owner_id']})")
        lines.append(f"Public: {playlist['public']} | Collaborative: {playlist['collaborative']}")
        lines.append(f"URL: {playlist['external_url'] or 'N/A'}")
        lines.append(f"Tracks: {playlist['tracks_exported']}")
        if playlist["description"]:
            lines.append(f"Description: {playlist['description']}")
        lines.append("")

        for idx, track in enumerate(playlist["tracks"], start=1):
            artists = ", ".join(track["artists"]) if track["artists"] else "Unknown artist"
            lines.append(f"{idx:03d}. {track['name']} - {artists}")
        lines.append("")
        lines.append("-" * 80)
        lines.append("")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sp = get_spotify_client()
    playlists = build_export_payload(sp)

    written_files: list[Path] = []
    requested = set(args.formats)
    if "json" in requested:
        written_files.append(write_json(output_dir, playlists))
    if "csv" in requested:
        written_files.append(write_csv(output_dir, playlists))
    if "txt" in requested:
        written_files.append(write_txt(output_dir, playlists))

    print(f"Exported {len(playlists)} playlists.")
    for file in written_files:
        print(f"- {file}")


if __name__ == "__main__":
    main()
