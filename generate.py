#!/usr/bin/env python3
"""
Generate apps.json from source-config.json + GitHub Releases API.

Reads static app metadata from source-config.json, fetches the latest
release from each app's GitHub repo, and writes a complete AltStore-
compatible apps.json.
"""

import json
import fnmatch
import os
import re
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _api_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "app-source-generator"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_latest_release(repo: str) -> dict | None:
    """Fetch the latest GitHub release for a repo."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = Request(url, headers=_api_headers())
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        print(f"  ✗ Failed to fetch {repo}: {e.code} {e.reason}")
        return None


def fetch_all_releases(repo: str) -> list[dict]:
    """Fetch all GitHub releases for a repo (newest first)."""
    url = f"https://api.github.com/repos/{repo}/releases?per_page=50"
    req = Request(url, headers=_api_headers())
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        print(f"  ✗ Failed to fetch {repo} releases: {e.code} {e.reason}")
        return []


def find_asset(release: dict, pattern: str) -> dict | None:
    """Find first release asset matching a glob pattern."""
    for asset in release.get("assets", []):
        if fnmatch.fnmatch(asset["name"], pattern):
            return asset
    return None


def clean_description(body: str) -> str:
    """Strip markdown formatting for AltStore display."""
    if not body:
        return ""
    import re
    text = re.sub(r"<[^>]+>", "", body)       # HTML tags
    text = re.sub(r"#{1,6}\s*", "", text)      # Markdown headers
    text = text.replace("**", "").replace("`", '"')
    text = re.sub(r"^- ", "• ", text, flags=re.MULTILINE)
    return text.strip()


def extract_version(release: dict, version_regex: str | None = None) -> str:
    """Extract version string from tag name, or from release body via regex."""
    tag = release["tag_name"].lstrip("v")
    # If the tag looks like a semver, use it directly
    if re.match(r"^\d+\.\d+", tag):
        return tag
    # Otherwise try to extract from release body using a regex
    if version_regex and release.get("body"):
        m = re.search(version_regex, release["body"])
        if m:
            return m.group(1)
    # Fallback to tag
    return tag


def build_app_entry(app_cfg: dict) -> dict | None:
    """Build one AltStore app entry from config + GitHub releases."""
    repo = app_cfg["repo"]
    pattern = app_cfg.get("assetPattern", "*.ipa")
    include_pre = app_cfg.get("includePrerelease", False)
    version_regex = app_cfg.get("versionRegex")
    print(f"  Fetching releases for {repo}...")

    releases = fetch_all_releases(repo)
    if not releases:
        return None

    # Build versions array (newest first, as AltStore expects)
    versions = []
    latest_entry = None
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not include_pre:
            continue
        asset = find_asset(release, pattern)
        if not asset:
            continue
        entry = {
            "version": extract_version(release, version_regex),
            "date": release["published_at"],
            "localizedDescription": clean_description(release.get("body", "")),
            "downloadURL": asset["browser_download_url"],
            "size": asset["size"],
        }
        versions.append(entry)
        if latest_entry is None:
            latest_entry = entry

    if not versions:
        print(f"  ✗ No releases with matching IPA for {repo}")
        return None

    latest = latest_entry
    return {
        "name": app_cfg["name"],
        "bundleIdentifier": app_cfg["bundleIdentifier"],
        "developerName": app_cfg.get("developerName", ""),
        "subtitle": app_cfg.get("subtitle", ""),
        "version": latest["version"],
        "versionDate": latest["date"],
        "versionDescription": latest["localizedDescription"],
        "downloadURL": latest["downloadURL"],
        "localizedDescription": app_cfg.get("localizedDescription", ""),
        "iconURL": app_cfg.get("iconURL", ""),
        "tintColor": app_cfg.get("tintColor", ""),
        "category": app_cfg.get("category", ""),
        "size": latest["size"],
        "screenshotURLs": app_cfg.get("screenshotURLs", []),
        "versions": versions,
    }


def main():
    config_path = Path(__file__).parent / "source-config.json"
    output_path = Path(__file__).parent / "apps.json"

    with open(config_path) as f:
        config = json.load(f)

    print("Generating apps.json...")
    source = config["source"]
    apps = []

    for app_cfg in config["apps"]:
        entry = build_app_entry(app_cfg)
        if entry:
            apps.append(entry)
            print(f"  ✓ {entry['name']} v{entry['version']} ({len(entry['versions'])} releases)")

    output = {
        "name": source["name"],
        "identifier": source["identifier"],
        "website": source.get("website", ""),
        "subtitle": source.get("subtitle", ""),
        "description": source.get("description", ""),
        "apps": apps,
        "news": [],
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n✓ Wrote {output_path} with {len(apps)} app(s)")
    return 0 if apps else 1


if __name__ == "__main__":
    sys.exit(main())
