# Plex Intro/Credits to IntroDB Uploader

Small Python GUI tool for exporting skip-intro / credits markers from a Plex SQLite DB and submitting them to IntroDB.

## Features

- Windows-friendly file picker to select the Plex DB file.
- Options for:
  - Dry run (no network calls).
  - Limit submissions (default 10).
  - Include intro and/or credits markers.
- Configurable IntroDB API base URL + endpoint path.
- Bearer token authentication.

## Run

```bash
python plex_introdb_uploader.py
```

> Uses only Python standard library (`tkinter`, `sqlite3`, `urllib`), so no dependency install is required.

## Typical Plex DB location on Windows

`%LOCALAPPDATA%\Plex Media Server\Plug-in Support\Databases\com.plexapp.plugins.library.db`

## Notes

- The script detects marker rows by looking for `intro`/`credit` text in marker/tag fields.
- Because Plex database schemas can vary by version, run in **dry run** first to confirm payloads.
- API payload format may evolve; if IntroDB requires additional fields, update `Marker.to_payload()`.
