from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from browser_backends.chromium_bookmarks import ensure_chromium_default_bookmarks


class ChromiumBookmarksTest(unittest.TestCase):
    def test_default_bookmarks_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as profile_dir:
            ensure_chromium_default_bookmarks(Path(profile_dir))

            data = json.loads((Path(profile_dir) / "Default" / "Bookmarks").read_text())
            preferences = json.loads((Path(profile_dir) / "Default" / "Preferences").read_text())
            top_sites = _read_top_sites(Path(profile_dir))

        urls = {
            child["url"]
            for child in data["roots"]["bookmark_bar"]["children"]
            if child.get("type") == "url"
        }
        self.assertIn("https://browserleaks.com", urls)
        self.assertIn("https://httpbin.org/ip", urls)
        self.assertIn(
            "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
            urls,
        )
        self.assertEqual(len(urls), 3)
        shortcut_urls = {shortcut["url"] for shortcut in preferences["custom_links"]["list"]}
        self.assertEqual(shortcut_urls, urls)
        self.assertTrue(preferences["custom_links"]["initialized"])
        self.assertTrue(preferences["custom_links"]["preinstalledremoved"])
        self.assertTrue(preferences["ntp"]["shortcuts_visible"])
        self.assertEqual(
            top_sites[:3],
            [
                ("https://browserleaks.com", 0, "BrowserLeaks"),
                ("https://httpbin.org/ip", 1, "HTTPBin IP"),
                (
                    "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
                    2,
                    "Chrome Headless Test",
                ),
            ],
        )

    def test_browserleaks_tls_bookmark_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as profile_dir:
            bookmarks_path = Path(profile_dir) / "Default" / "Bookmarks"
            bookmarks_path.parent.mkdir(parents=True)
            bookmarks_path.write_text(
                json.dumps(
                    {
                        "roots": {
                            "bookmark_bar": {
                                "children": [
                                    {
                                        "id": "4",
                                        "name": "BrowserLeaks TLS",
                                        "type": "url",
                                        "url": "https://browserleaks.com/tls",
                                    }
                                ],
                                "id": "1",
                                "name": "Bookmarks bar",
                                "type": "folder",
                            },
                            "other": {"children": [], "id": "2", "name": "Other", "type": "folder"},
                            "synced": {"children": [], "id": "3", "name": "Mobile", "type": "folder"},
                        },
                        "version": 1,
                    }
                ),
                encoding="utf-8",
            )

            ensure_chromium_default_bookmarks(Path(profile_dir))
            data = json.loads(bookmarks_path.read_text())

        children = data["roots"]["bookmark_bar"]["children"]
        urls = {child["url"] for child in children if child.get("type") == "url"}
        self.assertIn("https://browserleaks.com", urls)
        self.assertNotIn("https://browserleaks.com/tls", urls)

    def test_new_tab_shortcuts_are_written_to_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as profile_dir:
            preferences_path = Path(profile_dir) / "Default" / "Preferences"
            preferences_path.parent.mkdir(parents=True)
            preferences_path.write_text(
                json.dumps(
                    {
                        "homepage": "about:blank",
                        "custom_links": {
                            "initialized": True,
                            "list": [
                                {
                                    "title": "BrowserLeaks TLS",
                                    "url": "https://browserleaks.com/tls",
                                }
                            ],
                        },
                        "ntp": {
                            "custom_links": [
                                {
                                    "isMostVisited": False,
                                    "title": "BrowserLeaks TLS",
                                    "url": "https://browserleaks.com/tls",
                                }
                            ],
                            "custom_links_initialized": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            ensure_chromium_default_bookmarks(Path(profile_dir))
            preferences = json.loads(preferences_path.read_text())

        shortcuts = preferences["custom_links"]["list"]
        self.assertEqual(
            [shortcut["url"] for shortcut in shortcuts],
            [
                "https://browserleaks.com",
                "https://httpbin.org/ip",
                "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
            ],
        )
        self.assertTrue(preferences["custom_links"]["initialized"])
        self.assertTrue(preferences["custom_links"]["preinstalledremoved"])
        self.assertNotIn("custom_links", preferences["ntp"])
        self.assertNotIn("custom_links_initialized", preferences["ntp"])
        self.assertEqual(preferences["ntp"]["num_personal_suggestions"], 3)
        self.assertTrue(preferences["ntp"]["shortcuts_auto_removal_disabled"])
        self.assertTrue(preferences["ntp"]["shortcuts_visible"])
        self.assertEqual(preferences["homepage"], "about:blank")

    def test_top_sites_shortcuts_are_written_first(self) -> None:
        with tempfile.TemporaryDirectory() as profile_dir:
            top_sites_path = Path(profile_dir) / "Default" / "Top Sites"
            top_sites_path.parent.mkdir(parents=True)
            connection = sqlite3.connect(top_sites_path)
            try:
                connection.execute(
                    "CREATE TABLE meta (key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY, value LONGVARCHAR)"
                )
                connection.execute(
                    "CREATE TABLE top_sites (url LONGVARCHAR NOT NULL PRIMARY KEY, url_rank INTEGER, title LONGVARCHAR)"
                )
                connection.executemany(
                    "INSERT INTO top_sites(url, url_rank, title) VALUES(?, ?, ?)",
                    [
                        (
                            "https://browserleaks.com/tls",
                            0,
                            "TLS Client Test - TLS Fingerprinting - BrowserLeaks",
                        ),
                        ("https://chrome.google.com/webstore?hl=en", 1, "Web Store"),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            ensure_chromium_default_bookmarks(Path(profile_dir))
            top_sites = _read_top_sites(Path(profile_dir))

        self.assertEqual(
            top_sites[:4],
            [
                ("https://browserleaks.com", 0, "BrowserLeaks"),
                ("https://httpbin.org/ip", 1, "HTTPBin IP"),
                (
                    "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
                    2,
                    "Chrome Headless Test",
                ),
                ("https://chrome.google.com/webstore?hl=en", 3, "Web Store"),
            ],
        )


def _read_top_sites(profile_dir: Path) -> list[tuple[str, int, str]]:
    connection = sqlite3.connect(profile_dir / "Default" / "Top Sites")
    try:
        return connection.execute(
            "SELECT url, url_rank, title FROM top_sites ORDER BY url_rank ASC"
        ).fetchall()
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
