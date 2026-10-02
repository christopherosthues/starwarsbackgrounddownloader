"""Tests for gallery extraction from recorded HTML fixture."""

import unittest
from pathlib import Path

from starwars_backgrounds import BackgroundImage, parse_gallery

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "article.html"


class TestParseGallery(unittest.TestCase):
    """Verify parse_gallery extracts correct BackgroundImage items from fixture."""

    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE_PATH.read_text(encoding="utf-8")
        cls.items = parse_gallery(cls.html)

    def test_returns_list_of_background_images(self):
        self.assertIsInstance(self.items, list)
        for item in self.items:
            self.assertIsInstance(item, BackgroundImage)

    def test_count_at_least_50(self):
        """Article advertises more than 50 backgrounds; fixture has 99."""
        self.assertGreaterEqual(len(self.items), 50)

    def test_unique_source_urls(self):
        urls = [item.source_url for item in self.items]
        self.assertEqual(len(urls), len(set(urls)), "Duplicate source URLs found")

    def test_positions_sequential_1_based(self):
        positions = [item.position for item in self.items]
        expected = list(range(1, len(self.items) + 1))
        self.assertEqual(positions, expected)

    def test_source_urls_are_lumiere_cdn_https(self):
        for item in self.items:
            self.assertTrue(
                item.source_url.startswith("https://lumiere-a.akamaihd.net/v1/images/"),
                f"Unexpected URL: {item.source_url}",
            )

    def test_source_urls_have_no_query_string(self):
        """Full-resolution URLs must have query strings stripped."""
        for item in self.items:
            self.assertNotIn("?", item.source_url, f"Query string present: {item.source_url}")

    def test_titles_non_empty(self):
        for item in self.items:
            self.assertTrue(item.title.strip(), f"Empty title at position {item.position}")

    def test_title_fallback_for_empty_alt(self):
        """If alt is empty, title should fall back to background-<position>."""
        html = '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/test_abc.jpeg" alt=""></figure>'
        items = parse_gallery(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "background-1")

    def test_excludes_non_cdn_images(self):
        """Images not on lumiere CDN should be excluded."""
        html = (
            '<figure><img src="https://other-cdn.com/image.png" alt="Not a background"></figure>'
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/valid_abc.jpeg" alt="Valid"></figure>'
        )
        items = parse_gallery(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Valid")

    def test_excludes_non_jpeg_cdn_images(self):
        """Only .jpeg URLs on lumiere CDN are backgrounds."""
        html = (
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/logo_abc.png" alt="Logo"></figure>'
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/bg_abc.jpeg" alt="BG"></figure>'
        )
        items = parse_gallery(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "BG")


if __name__ == "__main__":
    unittest.main()
