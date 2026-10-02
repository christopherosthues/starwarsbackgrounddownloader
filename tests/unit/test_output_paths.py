"""Tests for idempotent re-runs and --overwrite behavior (US2)."""

import tempfile
import unittest
from pathlib import Path

from starwars_backgrounds import (
    BackgroundImage,
    Format,
    ItemStatus,
    derive_filename,
    process_item,
)
from tests.unit.stub_server import JPEG_BYTES, StubServer


class TestIdempotency(unittest.TestCase):
    """Verify skip/overwrite behavior for re-runs."""

    @classmethod
    def setUpClass(cls):
        cls.server = StubServer.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "StarWarsBackground"
        self.output_dir.mkdir(parents=True)

    def _make_item(self, position=1, title="Tatooine"):
        return BackgroundImage(
            position=position,
            title=title,
            source_url=f"{self.server.base_url}/test.jpeg",
        )

    def test_existing_file_skipped_without_overwrite(self):
        """If destination file exists and --overwrite is not given, item is skipped."""
        item = self._make_item()
        filename = derive_filename(item.position, item.title, Format.JPEG)
        dest_path = self.output_dir / filename

        # Pre-create the file (simulating a previous run)
        dest_path.write_bytes(b"existing content")

        result = process_item(item, self.output_dir, total=1, overwrite=False)
        self.assertEqual(result.status, ItemStatus.SKIPPED)
        # File should be unchanged
        self.assertEqual(dest_path.read_bytes(), b"existing content")

    def test_file_replaced_with_overwrite(self):
        """If --overwrite is given, existing file is replaced with fresh download."""
        item = self._make_item()
        filename = derive_filename(item.position, item.title, Format.JPEG)
        dest_path = self.output_dir / filename

        # Pre-create the file
        dest_path.write_bytes(b"old content")

        result = process_item(item, self.output_dir, total=1, overwrite=True)
        self.assertEqual(result.status, ItemStatus.SAVED)
        # File should now contain downloaded JPEG bytes
        self.assertEqual(dest_path.read_bytes(), JPEG_BYTES)

    def test_no_duplicates_created(self):
        """Running twice without --overwrite creates exactly one file."""
        item = self._make_item()

        result1 = process_item(item, self.output_dir, total=1, overwrite=False)
        self.assertEqual(result1.status, ItemStatus.SAVED)

        result2 = process_item(item, self.output_dir, total=1, overwrite=False)
        self.assertEqual(result2.status, ItemStatus.SKIPPED)

        # Only one file should exist in the output directory
        files = list(self.output_dir.iterdir())
        self.assertEqual(len(files), 1)

    def test_unrelated_files_left_untouched(self):
        """Files not matching any item's derived name are left alone."""
        item = self._make_item(position=1, title="Tatooine")

        # Create an unrelated file in the output directory
        unrelated = self.output_dir / "my-own-photo.jpg"
        unrelated.write_bytes(b"user data")

        result = process_item(item, self.output_dir, total=1, overwrite=False)
        self.assertEqual(result.status, ItemStatus.SAVED)

        # Unrelated file should still exist with original content
        self.assertTrue(unrelated.exists())
        self.assertEqual(unrelated.read_bytes(), b"user data")

    def test_multiple_items_no_cross_duplicates(self):
        """Multiple items produce distinct files; re-run skips all."""
        item1 = self._make_item(position=1, title="Tatooine")
        item2 = self._make_item(position=2, title="Hoth")

        process_item(item1, self.output_dir, total=2, overwrite=False)
        process_item(item2, self.output_dir, total=2, overwrite=False)

        files = sorted(self.output_dir.iterdir())
        self.assertEqual(len(files), 2)

        # Re-run: both should be skipped
        r1 = process_item(item1, self.output_dir, total=2, overwrite=False)
        r2 = process_item(item2, self.output_dir, total=2, overwrite=False)
        self.assertEqual(r1.status, ItemStatus.SKIPPED)
        self.assertEqual(r2.status, ItemStatus.SKIPPED)

        # Still only 2 files
        files_after = sorted(self.output_dir.iterdir())
        self.assertEqual(len(files_after), 2)


if __name__ == "__main__":
    unittest.main()
