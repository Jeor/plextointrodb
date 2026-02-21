# Plex Intro/Credits to IntroDB Uploader

Small Python GUI tool for exporting Plex skip-intro / credits markers from a Plex SQLite DB and submitting them to IntroDB.

## Features

- Windows-friendly file picker to select the Plex DB file.
- Options for:
  - Dry run (no network calls).
  - Limit submissions (default 10).
  - Include intro and/or credits markers.
  - Auto-try fallback API endpoints if the first endpoint returns 404.
- Defaults to IntroDB endpoint `/api/submissions`.
- Bearer token authentication.

## Run

```bash
python plex_introdb_uploader.py
```

> Uses only Python standard library (`tkinter`, `sqlite3`, `urllib`), so no dependency install is required.

## Typical Plex DB location on Windows

`%LOCALAPPDATA%\Plex Media Server\Plug-in Support\Databases\com.plexapp.plugins.library.db`

## Notes

- The query now pulls only marker tags of `intro` and `credits`, instead of scanning all taggings.
- Run in **dry run** first to verify payload fields and marker counts.
- If your IntroDB deployment uses a different route, change the endpoint field in the GUI.
