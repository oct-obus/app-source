# App Source

AltStore/LiveContainer compatible source for sideloaded apps.

## Add to LiveContainer

Use this URL as a source in LiveContainer:

```
https://raw.githubusercontent.com/oct-obus/app-source/main/apps.json
```

## Apps

- **Tidal Downloader** — Flutter iOS app with embedded CPython for Tidal music downloads and playback

## How it works

`source-config.json` defines static app metadata (name, icon, description) and which GitHub repos to pull from. `generate.py` fetches the latest releases via the GitHub API and builds `apps.json`.

A GitHub Actions workflow runs every 6 hours to keep the source updated. You can also trigger it manually or add new apps by editing `source-config.json`.
