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
import queue
import threading
import webbrowser
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
        default=".",
        help=(
            "Subdirectory inside the script's exports folder "
            "(default: current exports root)."
        ),
    )
    parser.add_argument(
        "--auth-timeout",
        type=int,
        default=180,
        help="Seconds to wait for pasted Spotify callback URL (default: 180). Use 0 to disable timeout.",
    )
    parser.add_argument(
        "--playlist",
        action="append",
        default=[],
        help=(
            "Playlist selector (can be repeated). Matches by playlist ID, exact name, "
            "or case-insensitive name substring."
        ),
    )
    parser.add_argument(
        "--interactive-playlist",
        action="store_true",
        help="Choose playlist(s) interactively from a numbered list.",
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


def read_input_with_timeout(prompt: str, timeout_seconds: int) -> str:
    if timeout_seconds <= 0:
        return input(prompt).strip()

    result_queue: queue.Queue[str] = queue.Queue()

    def _reader() -> None:
        try:
            result_queue.put(input(prompt))
        except EOFError:
            result_queue.put("")

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        raise TimeoutError(
            f"Timed out waiting for input after {timeout_seconds} seconds."
        )
    return result_queue.get().strip()


def authenticate_spotify(auth_manager: SpotifyOAuth, timeout_seconds: int) -> None:
    # Fast path: skip auth prompt when a cached token already exists.
    token_info = auth_manager.validate_token(auth_manager.cache_handler.get_cached_token())
    if token_info:
        return

    auth_url = auth_manager.get_authorize_url()
    print("Opening Spotify login in your browser...")
    print("After approval, copy the FULL redirected URL and paste it here.")
    print(f"If no response is received in {timeout_seconds}s, auth will time out.")
    print(f"\nAuth URL (fallback):\n{auth_url}\n")
    webbrowser.open(auth_url)

    redirected_url = read_input_with_timeout(
        "Paste redirected URL here: ",
        timeout_seconds=timeout_seconds,
    )
    code = auth_manager.parse_response_code(redirected_url)
    if not code:
        raise RuntimeError(
            "Could not parse auth code from redirected URL. "
            "Make sure you paste the full callback URL from the browser."
        )
    auth_manager.get_access_token(code=code, as_dict=False, check_cache=False)


def get_spotify_client(auth_timeout: int) -> spotipy.Spotify:
    ensure_spotify_credentials()
    auth_manager = SpotifyOAuth(scope=SCOPE, open_browser=False)
    authenticate_spotify(auth_manager=auth_manager, timeout_seconds=auth_timeout)
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


def flatten_terms(values: list[str]) -> list[str]:
    terms: list[str] = []
    for value in values:
        terms.extend(part.strip() for part in value.split(",") if part.strip())
    return terms


def filter_playlists_by_terms(
    playlists: list[dict[str, Any]], raw_terms: list[str]
) -> list[dict[str, Any]]:
    terms = flatten_terms(raw_terms)
    if not terms:
        return playlists

    by_id = {playlist.get("id"): playlist for playlist in playlists if playlist.get("id")}
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    for term in terms:
        term_lower = term.lower()
        matches: list[dict[str, Any]] = []

        # First, try direct ID match for precise selection.
        if term in by_id:
            matches = [by_id[term]]
        else:
            exact_name_matches = [
                playlist
                for playlist in playlists
                if (playlist.get("name") or "").strip().lower() == term_lower
            ]
            if exact_name_matches:
                matches = exact_name_matches
            else:
                matches = [
                    playlist
                    for playlist in playlists
                    if term_lower in (playlist.get("name") or "").lower()
                ]

        if not matches:
            print(f"Warning: no playlists matched selector '{term}'.")
            continue

        for playlist in matches:
            playlist_id = playlist.get("id")
            if playlist_id and playlist_id not in selected_ids:
                selected.append(playlist)
                selected_ids.add(playlist_id)

    return selected


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    if not selection or selection.lower() == "all":
        return list(range(1, max_index + 1))

    indexes: set[int] = set()
    tokens = [token.strip() for token in selection.split(",") if token.strip()]
    for token in tokens:
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            indexes.update(range(start, end + 1))
        else:
            indexes.add(int(token))

    invalid = [idx for idx in indexes if idx < 1 or idx > max_index]
    if invalid:
        raise ValueError(f"Selection out of range: {invalid}")
    return sorted(indexes)


def choose_playlists_interactively(playlists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not playlists:
        return []

    print("\nAvailable playlists:")
    for idx, playlist in enumerate(playlists, start=1):
        name = playlist.get("name", "Untitled playlist")
        owner = (playlist.get("owner") or {}).get("display_name", "Unknown owner")
        total = (playlist.get("tracks") or {}).get("total")
        print(f"  {idx:>3}. {name} ({owner}) - {total} tracks")

    while True:
        raw = input("\nChoose playlist numbers (e.g. 1,3-5) or 'all': ").strip()
        try:
            chosen_indexes = parse_index_selection(raw, len(playlists))
            return [playlists[idx - 1] for idx in chosen_indexes]
        except ValueError as err:
            print(f"Invalid selection: {err}")


def select_playlists(
    playlists: list[dict[str, Any]],
    selectors: list[str],
    interactive: bool,
) -> list[dict[str, Any]]:
    selected = filter_playlists_by_terms(playlists, selectors)
    if interactive:
        selected = choose_playlists_interactively(selected)
    return selected


def normalize_track(item: dict[str, Any]) -> dict[str, Any] | None:
    # Skip entries where Spotify returns a removed/unavailable track.
    track = item.get("track")
    if not track:
        return None

    # Spotify can occasionally return null artist names; keep only non-empty strings.
    artists = [
        str(name).strip()
        for artist in track.get("artists", [])
        if artist and (name := artist.get("name")) is not None and str(name).strip()
    ]
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


def build_export_payload(sp: spotipy.Spotify, playlists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Build one normalized structure that all exporters can reuse.
    payload: list[dict[str, Any]] = []

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
                        "track_artists": ", ".join(track["artists"]) if track["artists"] else "Unknown artist",
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


def resolve_output_dir(output_subdir: str) -> Path:
    script_dir = Path(__file__).resolve().parent
    exports_root = script_dir / "exports"

    # Always keep exports under the script directory.
    subdir = Path(output_subdir)
    if output_subdir in {"", "."}:
        return exports_root

    # Use only path parts so absolute paths cannot escape exports_root.
    safe_parts = [part for part in subdir.parts if part not in {"", ".", ".."}]
    return exports_root.joinpath(*safe_parts)


def main() -> None:
    args = parse_args()
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sp = get_spotify_client(auth_timeout=args.auth_timeout)
    playlists = fetch_all_playlists(sp)
    selected_playlists = select_playlists(
        playlists=playlists,
        selectors=args.playlist,
        interactive=args.interactive_playlist,
    )
    if not selected_playlists:
        print("No playlists selected. Nothing to export.")
        return

    playlists_payload = build_export_payload(sp, selected_playlists)

    written_files: list[Path] = []
    requested = set(args.formats)
    if "json" in requested:
        written_files.append(write_json(output_dir, playlists_payload))
    if "csv" in requested:
        written_files.append(write_csv(output_dir, playlists_payload))
    if "txt" in requested:
        written_files.append(write_txt(output_dir, playlists_payload))

    print(f"Exported {len(playlists_payload)} playlists.")
    for file in written_files:
        print(f"- {file}")


if __name__ == "__main__":
    main()
