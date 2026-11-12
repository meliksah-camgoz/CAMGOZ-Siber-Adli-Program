"""Read-only browser artifact collection for CAMGOZ (Windows)."""
from __future__ import annotations

import os
import json
import configparser
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime, timedelta, timezone


BROWSER_NAMES = {
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "firefox": "Mozilla Firefox",
}


def _windows_epoch(value):
    """Convert Chromium microseconds since 1601-01-01 UTC to ISO text."""
    if value in (None, "", 0):
        return ""
    try:
        dt = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=int(value))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OverflowError):
        return str(value)


def _firefox_epoch(value):
    """Convert Firefox microseconds since Unix epoch to ISO text."""
    if value in (None, "", 0):
        return ""
    try:
        dt = datetime.fromtimestamp(int(value) / 1_000_000, tz=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OverflowError, OSError):
        return str(value)


def _safe_readonly_connection(db_path: Path):
    # mode=ro prevents CAMGOZ from modifying the source browser database.
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    return connection



def _chromium_profile_names(base: Path):
    """Read friendly profile names from Chromium Local State, if available."""
    state_file = base / "Local State"
    if not state_file.is_file():
        return {}
    try:
        with state_file.open("r", encoding="utf-8") as stream:
            state = json.load(stream)
        info_cache = state.get("profile", {}).get("info_cache", {})
        names = {}
        for folder, info in info_cache.items():
            if not isinstance(info, dict):
                continue
            # 'name' is the visible profile label in Chrome/Edge.
            names[folder] = (
                info.get("name")
                or info.get("user_name")
                or folder
            )
        return names
    except (OSError, ValueError, TypeError):
        return {}


def _chromium_profiles(browser_key: str):
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    base = local / ("Google/Chrome/User Data" if browser_key == "chrome"
                    else "Microsoft/Edge/User Data")
    profiles = []
    if not base.is_dir():
        return profiles

    friendly_names = _chromium_profile_names(base)
    for folder in base.iterdir():
        db = folder / "History"
        if folder.is_dir() and db.is_file():
            display_name = friendly_names.get(folder.name, folder.name)
            profiles.append({
                "browser": BROWSER_NAMES[browser_key],
                "profile": folder.name,
                "display_name": display_name,
                "profile_path": str(folder),
                "database": db,
                "engine": "chromium",
            })
    return profiles


def _firefox_profiles():
    roaming = Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox"
    profiles_dir = roaming / "Profiles"
    profiles = []
    if not profiles_dir.is_dir():
        return profiles

    profile_names = {}
    ini_path = roaming / "profiles.ini"
    if ini_path.is_file():
        parser = configparser.ConfigParser()
        try:
            parser.read(ini_path, encoding="utf-8")
            for section in parser.sections():
                if not section.startswith("Profile"):
                    continue
                name = parser.get(section, "Name", fallback="")
                path_value = parser.get(section, "Path", fallback="")
                is_relative = parser.getboolean(section, "IsRelative", fallback=True)
                if path_value:
                    resolved = (roaming / path_value) if is_relative else Path(path_value)
                    profile_names[str(resolved.resolve()).casefold()] = name or Path(path_value).name
        except (OSError, configparser.Error, ValueError):
            pass

    for folder in profiles_dir.iterdir():
        db = folder / "places.sqlite"
        if folder.is_dir() and db.is_file():
            display_name = profile_names.get(str(folder.resolve()).casefold(), folder.name)
            profiles.append({
                "browser": BROWSER_NAMES["firefox"],
                "profile": folder.name,
                "display_name": display_name,
                "profile_path": str(folder),
                "database": db,
                "engine": "firefox",
            })
    return profiles


def detect_profiles():
    """Return discovered browser profiles; no files are created or changed."""
    found = []
    found.extend(_chromium_profiles("chrome"))
    found.extend(_chromium_profiles("edge"))
    found.extend(_firefox_profiles())
    return found


def _extract_search(url: str):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        params = parse_qs(parsed.query)
        candidates = {
            "google.com": ("q", "Google"),
            "www.google.com": ("q", "Google"),
            "bing.com": ("q", "Bing"),
            "www.bing.com": ("q", "Bing"),
            "duckduckgo.com": ("q", "DuckDuckGo"),
            "www.duckduckgo.com": ("q", "DuckDuckGo"),
            "yandex.com": ("text", "Yandex"),
            "www.yandex.com": ("text", "Yandex"),
        }
        for domain, (key, label) in candidates.items():
            if host == domain or host.endswith("." + domain):
                query = params.get(key, [""])[0].strip()
                if query:
                    return label, unquote(query)
    except Exception:
        pass
    return "", ""


def collect_profile_artifacts(profile):
    """Collect history and download rows from one detected profile."""
    db_path = Path(profile["database"])
    if not db_path.is_file():
        raise FileNotFoundError(str(db_path))

    results = []
    connection = _safe_readonly_connection(db_path)
    try:
        if profile["engine"] == "chromium":
            tables = {row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "urls" in tables:
                query = """
                    SELECT u.url, u.title, u.visit_count, u.last_visit_time
                    FROM urls u
                    ORDER BY u.last_visit_time DESC
                    LIMIT 10000
                """
                for row in connection.execute(query):
                    search_engine, search_query = _extract_search(row["url"] or "")
                    results.append({
                        "type": "Search" if search_query else "History",
                        "browser": profile["browser"],
                        "profile": profile["profile"],
                        "date": _windows_epoch(row["last_visit_time"]),
                        "title": row["title"] or "",
                        "url": row["url"] or "",
                        "details": (f"{search_engine}: {search_query}" if search_query
                                    else f"Visit count: {row['visit_count'] or 0}"),
                    })

            if "downloads" in tables:
                query = """
                    SELECT target_path, tab_url, start_time, end_time,
                           received_bytes, total_bytes, state
                    FROM downloads
                    ORDER BY start_time DESC
                    LIMIT 5000
                """
                for row in connection.execute(query):
                    results.append({
                        "type": "Download",
                        "browser": profile["browser"],
                        "profile": profile["profile"],
                        "date": _windows_epoch(row["start_time"]),
                        "title": Path(row["target_path"] or "").name,
                        "url": row["tab_url"] or "",
                        "details": (
                            f"Path: {row['target_path'] or '-'} | "
                            f"Received: {row['received_bytes'] or 0} bytes | "
                            f"State: {row['state']}"
                        ),
                    })
        else:
            tables = {row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "moz_places" in tables and "moz_historyvisits" in tables:
                query = """
                    SELECT p.url, p.title, p.visit_count, h.visit_date
                    FROM moz_historyvisits h
                    JOIN moz_places p ON p.id = h.place_id
                    ORDER BY h.visit_date DESC
                    LIMIT 10000
                """
                for row in connection.execute(query):
                    search_engine, search_query = _extract_search(row["url"] or "")
                    results.append({
                        "type": "Search" if search_query else "History",
                        "browser": profile["browser"],
                        "profile": profile["profile"],
                        "date": _firefox_epoch(row["visit_date"]),
                        "title": row["title"] or "",
                        "url": row["url"] or "",
                        "details": (f"{search_engine}: {search_query}" if search_query
                                    else f"Visit count: {row['visit_count'] or 0}"),
                    })

            # Firefox download metadata is version-dependent. moz_annos is
            # used by older profiles; newer profiles may not expose downloads here.
            if "moz_annos" in tables and "moz_anno_attributes" in tables:
                query = """
                    SELECT p.url, a.content, a.dateAdded
                    FROM moz_annos a
                    JOIN moz_anno_attributes n ON n.id = a.anno_attribute_id
                    LEFT JOIN moz_places p ON p.id = a.place_id
                    WHERE n.name LIKE '%downloads%'
                    ORDER BY a.dateAdded DESC
                    LIMIT 5000
                """
                for row in connection.execute(query):
                    results.append({
                        "type": "Download",
                        "browser": profile["browser"],
                        "profile": profile["profile"],
                        "date": _firefox_epoch(row["dateAdded"]),
                        "title": str(row["content"] or "")[:250],
                        "url": row["url"] or "",
                        "details": "Legacy Firefox download annotation",
                    })
    finally:
        connection.close()

    results.sort(key=lambda item: item.get("date", ""), reverse=True)
    return results
