"""Tests for gallery extraction from recorded HTML fixture."""

import unittest
from pathlib import Path

from starwars_backgrounds import (
    BackgroundImage,
    Format,
    derive_filename,
    derive_filename_from_url,
    parse_gallery,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "article.html"


class TestParseGallery(unittest.TestCase):
    """Verify parse_gallery extracts correct BackgroundImage items from fixture."""

    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE_PATH.read_text(encoding="utf-8")
        cls.items = parse_gallery(cls.html)

    def test_returns_list_of_background_images(self):
        """parse_gallery returns a list of BackgroundImage items."""
        self.assertIsInstance(self.items, list)
        for item in self.items:
            self.assertIsInstance(item, BackgroundImage)

    def test_count_at_least_50(self):
        """Article advertises more than 50 backgrounds; fixture has 99."""
        self.assertGreaterEqual(len(self.items), 50)

    def test_unique_source_urls(self):
        """All source URLs are unique."""
        urls = [item.source_url for item in self.items]
        self.assertEqual(len(urls), len(set(urls)), "Duplicate source URLs found")

    def test_positions_sequential_1_based(self):
        """Positions are sequential, starting at 1."""
        positions = [item.position for item in self.items]
        expected = list(range(1, len(self.items) + 1))
        self.assertEqual(positions, expected)

    def test_source_urls_are_lumiere_cdn_https(self):
        """Every source URL is an HTTPS lumiere CDN URL."""
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
        """Titles are non-empty after stripping whitespace."""
        for item in self.items:
            self.assertTrue(item.title.strip(), f"Empty title at position {item.position}")

    def test_title_fallback_for_empty_alt(self):
        """If alt is empty, title should fall back to background-<position>."""
        html = (
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/'
            'test_abc.jpeg" alt=""></figure>'
        )
        items = parse_gallery(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "background-1")

    def test_excludes_non_cdn_images(self):
        """Images not on lumiere CDN should be excluded."""
        html = (
            '<figure><img src="https://other-cdn.com/image.png"'
            ' alt="Not a background"></figure>'
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/'
            'valid_abc.jpeg" alt="Valid"></figure>'
        )
        items = parse_gallery(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Valid")

    def test_excludes_non_jpeg_cdn_images(self):
        """Only .jpeg URLs on lumiere CDN are backgrounds."""
        html = (
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/'
            'logo_abc.png" alt="Logo"></figure>'
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/'
            'bg_abc.jpeg" alt="BG"></figure>'
        )
        items = parse_gallery(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "BG")


class TestUrlDerivedNaming(unittest.TestCase):
    """US2 (feature 004 T007): file names derived from the source URL base name."""

    def test_basename_of_url_path_is_used(self):
        """Base name is the basename of urlparse(source_url).path."""
        url = "https://lumiere-a.akamaihd.net/v1/images/tatooine_abc.jpeg"
        self.assertEqual(
            derive_filename_from_url(url, Format.JPEG),
            "tatooine_abc.jpg",
        )

    def test_query_and_fragment_stripped(self):
        """Query strings and fragments do not affect the derived name."""
        plain = "https://lumiere-a.akamaihd.net/v1/images/tatooine_abc.jpeg"
        decorated = (
            "https://lumiere-a.akamaihd.net/v1/images/tatooine_abc.jpeg"
            "?width=1920#gallery-7"
        )
        self.assertEqual(
            derive_filename_from_url(decorated, Format.JPEG),
            derive_filename_from_url(plain, Format.JPEG),
        )

    def test_extension_matches_detected_format(self):
        """The on-disk extension is the detected format's, not the URL's."""
        url = "https://lumiere-a.akamaihd.net/v1/images/tatooine_abc.jpeg"
        self.assertEqual(
            derive_filename_from_url(url, Format.PNG),
            "tatooine_abc.png",
        )

    def test_empty_path_falls_back_to_position_title(self):
        """A URL path with no base name falls back to <NNN>-<title> derivation."""
        url = "https://lumiere-a.akamaihd.net/v1/images/"
        self.assertEqual(
            derive_filename_from_url(url, Format.JPEG, position=7, title="Tatooine"),
            derive_filename(7, "Tatooine", Format.JPEG),
        )

    def test_extension_less_path_falls_back(self):
        """A base name without an extension falls back to <NNN>-<title>."""
        url = "https://lumiere-a.akamaihd.net/v1/images/noext"
        self.assertEqual(
            derive_filename_from_url(url, Format.PNG, position=3, title="Hoth"),
            derive_filename(3, "Hoth", Format.PNG),
        )

    def test_windows_illegal_characters_replaced(self):
        """<>:"\\|?* and control characters are replaced with '-'."""
        url = r'https://lumiere-a.akamaihd.net/v1/images/a<b>c"d|e\f*g.jpeg'
        self.assertEqual(
            derive_filename_from_url(url, Format.JPEG),
            "a-b-c-d-e-f-g.jpg",
        )

    def test_control_characters_replaced(self):
        """ASCII control characters in the base name are replaced with '-'."""
        url = "https://lumiere-a.akamaihd.net/v1/images/a\x01b.jpeg"
        self.assertEqual(derive_filename_from_url(url, Format.JPEG), "a-b.jpg")

    def test_trailing_dots_and_spaces_stripped(self):
        """Trailing dots and spaces in the base name are stripped."""
        dotted = "https://lumiere-a.akamaihd.net/v1/images/tatooine...jpeg"
        self.assertEqual(derive_filename_from_url(dotted, Format.JPEG), "tatooine.jpg")
        spaced = "https://lumiere-a.akamaihd.net/v1/images/tatooine .jpeg"
        self.assertEqual(derive_filename_from_url(spaced, Format.JPEG), "tatooine.jpg")


if __name__ == "__main__":
    unittest.main()
