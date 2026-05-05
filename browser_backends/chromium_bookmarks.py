from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DEFAULT_CHROMIUM_BOOKMARKS: tuple[tuple[str, str], ...] = (
    ("BrowserLeaks", "https://browserleaks.com"),
    ("HTTPBin IP", "https://httpbin.org/ip"),
    (
        "Chrome Headless Test",
        "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
    ),
)

BOOKMARK_URL_REPLACEMENTS = {
    "https://browserleaks.com/tls": "https://browserleaks.com",
    "http://browserleaks.com/tls": "https://browserleaks.com",
}


def ensure_chromium_default_bookmarks(profile_dir: Path) -> None:
    bookmarks_path = profile_dir / "Default" / "Bookmarks"
    bookmarks_path.parent.mkdir(parents=True, exist_ok=True)

    data = _read_bookmarks(bookmarks_path)
    bookmark_bar = data["roots"]["bookmark_bar"]
    children = bookmark_bar.setdefault("children", [])
    if not isinstance(children, list):
        children = []
        bookmark_bar["children"] = children

    _replace_bookmark_urls(children)
    existing_urls = _collect_bookmark_urls(children)
    for name, url in DEFAULT_CHROMIUM_BOOKMARKS:
        if url in existing_urls:
            continue
        children.append(_bookmark_entry(name, url, _next_bookmark_id(data)))
        existing_urls.add(url)

    _write_bookmarks(bookmarks_path, data)
    _ensure_chromium_ntp_shortcuts(profile_dir)
    _ensure_chromium_top_sites(profile_dir)


def _ensure_chromium_ntp_shortcuts(profile_dir: Path) -> None:
    preferences_path = profile_dir / "Default" / "Preferences"
    preferences_path.parent.mkdir(parents=True, exist_ok=True)

    preferences = _read_preferences(preferences_path)
    custom_links = preferences.setdefault("custom_links", {})
    if not isinstance(custom_links, dict):
        custom_links = {}
        preferences["custom_links"] = custom_links

    custom_links["initialized"] = True
    custom_links["list"] = [
        {
            "title": name,
            "url": BOOKMARK_URL_REPLACEMENTS.get(url, url),
        }
        for name, url in DEFAULT_CHROMIUM_BOOKMARKS
    ]
    custom_links["preinstalledremoved"] = True

    ntp = preferences.setdefault("ntp", {})
    if not isinstance(ntp, dict):
        ntp = {}
        preferences["ntp"] = ntp

    ntp["num_personal_suggestions"] = len(DEFAULT_CHROMIUM_BOOKMARKS)
    ntp["shortcuts_auto_removal_disabled"] = True
    ntp["shortcuts_visible"] = True
    ntp.pop("custom_links", None)
    ntp.pop("custom_links_initialized", None)

    _write_preferences(preferences_path, preferences)


def _ensure_chromium_top_sites(profile_dir: Path) -> None:
    top_sites_path = profile_dir / "Default" / "Top Sites"
    top_sites_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(top_sites_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY,
                value LONGVARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS top_sites (
                url LONGVARCHAR NOT NULL PRIMARY KEY,
                url_rank INTEGER,
                title LONGVARCHAR
            )
            """
        )
        for key, value in (
            ("mmap_status", "-1"),
            ("version", "5"),
            ("last_compatible_version", "5"),
        ):
            connection.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                (key, value),
            )

        desired_urls = {url for _, url in DEFAULT_CHROMIUM_BOOKMARKS}
        obsolete_urls = set(BOOKMARK_URL_REPLACEMENTS)
        existing_rows = connection.execute(
            "SELECT url, url_rank, title FROM top_sites ORDER BY url_rank ASC"
        ).fetchall()

        rows: list[tuple[str, int, str]] = []
        seen_urls: set[str] = set()
        for rank, (title, url) in enumerate(DEFAULT_CHROMIUM_BOOKMARKS):
            rows.append((url, rank, title))
            seen_urls.add(url)

        next_rank = len(rows)
        for url, _, title in existing_rows:
            normalized_url = BOOKMARK_URL_REPLACEMENTS.get(str(url), str(url))
            should_skip = (
                normalized_url in desired_urls
                or normalized_url in obsolete_urls
                or normalized_url in seen_urls
            )
            if should_skip:
                continue
            rows.append((normalized_url, next_rank, str(title or normalized_url)))
            seen_urls.add(normalized_url)
            next_rank += 1

        connection.execute("DELETE FROM top_sites")
        connection.executemany(
            "INSERT OR REPLACE INTO top_sites(url, url_rank, title) VALUES(?, ?, ?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def _read_bookmarks(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = _empty_bookmarks()
    else:
        data = _empty_bookmarks()

    if not isinstance(data, dict):
        data = _empty_bookmarks()
    data.setdefault("checksum", "")
    data.setdefault("version", 1)
    roots = data.setdefault("roots", {})
    if not isinstance(roots, dict):
        data["roots"] = roots = {}

    for key, name in (
        ("bookmark_bar", "Bookmarks bar"),
        ("other", "Other bookmarks"),
        ("synced", "Mobile bookmarks"),
    ):
        root = roots.setdefault(key, _folder_entry(name, "1"))
        if not isinstance(root, dict):
            roots[key] = root = _folder_entry(name, "1")
        root.setdefault("children", [])
        root.setdefault("type", "folder")
        root.setdefault("name", name)

    return data


def _empty_bookmarks() -> dict[str, Any]:
    return {
        "checksum": "",
        "roots": {
            "bookmark_bar": _folder_entry("Bookmarks bar", "1"),
            "other": _folder_entry("Other bookmarks", "2"),
            "synced": _folder_entry("Mobile bookmarks", "3"),
        },
        "version": 1,
    }


def _folder_entry(name: str, bookmark_id: str) -> dict[str, Any]:
    return {
        "children": [],
        "date_added": _chrome_timestamp(),
        "date_last_used": "0",
        "date_modified": _chrome_timestamp(),
        "guid": "",
        "id": bookmark_id,
        "name": name,
        "type": "folder",
    }


def _bookmark_entry(name: str, url: str, bookmark_id: str) -> dict[str, Any]:
    return {
        "date_added": _chrome_timestamp(),
        "date_last_used": "0",
        "guid": "",
        "id": bookmark_id,
        "name": name,
        "type": "url",
        "url": url,
    }


def _replace_bookmark_urls(children: list[Any]) -> None:
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("type") == "url":
            url = str(child.get("url", ""))
            replacement = BOOKMARK_URL_REPLACEMENTS.get(url)
            if replacement:
                child["url"] = replacement
                if child.get("name") in {"BrowserLeaks TLS", "TLS"}:
                    child["name"] = "BrowserLeaks"
        nested_children = child.get("children")
        if isinstance(nested_children, list):
            _replace_bookmark_urls(nested_children)


def _collect_bookmark_urls(children: list[Any]) -> set[str]:
    urls: set[str] = set()
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("type") == "url" and child.get("url"):
            urls.add(str(child["url"]))
        nested_children = child.get("children")
        if isinstance(nested_children, list):
            urls.update(_collect_bookmark_urls(nested_children))
    return urls


def _next_bookmark_id(data: dict[str, Any]) -> str:
    max_id = 0

    def visit(node: object) -> None:
        nonlocal max_id
        if isinstance(node, dict):
            try:
                max_id = max(max_id, int(str(node.get("id", "0"))))
            except ValueError:
                pass
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(data.get("roots"))
    return str(max_id + 1)


def _write_bookmarks(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=3), encoding="utf-8")


def _read_preferences(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    else:
        data = {}

    if not isinstance(data, dict):
        return {}
    return data


def _write_preferences(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=3), encoding="utf-8")


def _chrome_timestamp() -> str:
    return str(int(time.time() * 1_000_000) + 11_644_473_600_000_000)
