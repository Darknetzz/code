# pyspotify

Export your Spotify playlists (including tracks) to `txt`, `json`, and `csv`.

## Features

- Exports all playlists from your Spotify account
- Handles Spotify pagination for playlists and tracks
- Writes multiple output formats in one run:
  - `spotify_playlists.txt`
  - `spotify_playlists.json`
  - `spotify_playlists.csv`
- Prompts for missing Spotify credentials
- Can save prompted credentials to a local `.env` file

## Requirements

- Python 3.10+
- A Spotify Developer app (Client ID + Client Secret)
- `spotipy`

## Setup

1. Install dependency:

```powershell
python -m pip install spotipy
```

2. Create a Spotify app:
   - Go to Spotify Developer Dashboard
   - Create an app
   - Copy `Client ID` and `Client Secret`
   - Add redirect URI: `http://127.0.0.1:8888/callback`

## Usage

Run from repository root:

```powershell
python .\Python\pyspotify\pyspotify.py
```

Optional arguments:

```powershell
python .\Python\pyspotify\pyspotify.py --formats txt json csv --output-dir exports
```

- `--formats`: one or more of `txt`, `json`, `csv`
- `--output-dir`: output folder (default: `exports`)

## Credentials

The script checks credentials in this order:

1. Current environment variables
2. `Python/pyspotify/.env`
3. Interactive prompt for missing values

Required keys:

- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`
- `SPOTIPY_REDIRECT_URI`

If prompted, you can choose to save values to:

- `Python/pyspotify/.env`

Example `.env`:

```dotenv
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Output Files

By default, files are written to `exports/`:

- `spotify_playlists.txt`: human-readable playlist + track list
- `spotify_playlists.json`: nested structured export
- `spotify_playlists.csv`: one row per track with playlist metadata

## Troubleshooting

- `ModuleNotFoundError: No module named 'spotipy'`
  - Install with: `python -m pip install spotipy`
- `No client_id` or auth errors
  - Verify your credentials and redirect URI
  - Ensure redirect URI matches exactly in Spotify app settings
