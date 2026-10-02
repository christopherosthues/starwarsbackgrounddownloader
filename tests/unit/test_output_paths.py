"""Tests for idempotent re-runs and --overwrite behavior (US2)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starwars_backgrounds import (
    BackgroundImage,
    Format,
    ItemStatus,
    OutputDirectoryError,
    derive_filename,
    process_item,
    resolve_output_dir,
)
from tests.unit.stub_server import JPEG_BYTES, StubServer


class TestOutputDirResolution(unittest.TestCase):
    """US1: --output-dir resolution semantics (research.md R2)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

    def test_existing_directory_used_as_effective_dir(self):
        """An existing directory becomes the effective output directory."""
        target = self.tmp_root / "custom"
        target.mkdir()

        resolved = resolve_output_dir(str(target))

        self.assertEqual(resolved, target)
        self.assertTrue(resolved.is_dir())

    def test_relative_value_resolves_against_cwd(self):
        """Relative values resolve against the current working directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.tmp_root)
            resolved = resolve_output_dir("custom")
        finally:
            os.chdir(original_cwd)

        self.assertEqual(resolved, (self.tmp_root / "custom").absolute())

    def test_absolute_value_used_as_given(self):
        """Absolute values are used as given."""
        target = self.tmp_root / "abs"
        target.mkdir()

        resolved = resolve_output_dir(str(target))

        self.assertEqual(resolved, target)

    def test_tilde_is_expanded(self):
        """A leading ~ is expanded before resolution."""
        home_target = self.tmp_root / "home-bg"
        with patch(
            "os.path.expanduser",
            side_effect=lambda p: str(home_target),
        ):
            resolved = resolve_output_dir("~/bg")

        self.assertEqual(resolved, home_target)

    def test_effective_path_is_absolute(self):
        """The effective path is normalized to an absolute path."""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.tmp_root)
            resolved = resolve_output_dir("custom")
        finally:
            os.chdir(original_cwd)

        self.assertTrue(resolved.is_absolute())


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


class TestCustomDirectorySafeWrites(unittest.TestCase):
    """US2: safe-write rules apply identically inside custom directories."""

    @classmethod
    def setUpClass(cls):
        cls.server = StubServer.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.custom_dir = Path(self._tmp.name) / "custom"
        self.custom_dir.mkdir()

    def _make_item(self, position=1, title="Tatooine"):
        return BackgroundImage(
            position=position,
            title=title,
            source_url=f"{self.server.base_url}/test.jpeg",
        )

    def test_re_run_in_custom_dir_skips_existing_files(self):
        """Re-running against a custom directory skips existing files."""
        effective = resolve_output_dir(str(self.custom_dir))
        item = self._make_item()

        first = process_item(item, effective, total=1)
        second = process_item(item, effective, total=1)

        self.assertEqual(first.status, ItemStatus.SAVED)
        self.assertEqual(second.status, ItemStatus.SKIPPED)

    def test_unrelated_files_in_custom_dir_untouched(self):
        """Pre-existing unrelated files in a custom directory are left alone."""
        effective = resolve_output_dir(str(self.custom_dir))
        item = self._make_item()
        unrelated = self.custom_dir / "my-own-photo.jpg"
        unrelated.write_bytes(b"user data")

        result = process_item(item, effective, total=1)

        self.assertEqual(result.status, ItemStatus.SAVED)
        self.assertTrue(unrelated.exists())
        self.assertEqual(unrelated.read_bytes(), b"user data")

    def test_overwrite_re_downloads_into_custom_dir_only(self):
        """--overwrite re-downloads into the custom directory only."""
        effective = resolve_output_dir(str(self.custom_dir))
        item = self._make_item()
        filename = derive_filename(item.position, item.title, Format.JPEG)
        (self.custom_dir / filename).write_bytes(b"old content")

        result = process_item(item, effective, total=1, overwrite=True)

        self.assertEqual(result.status, ItemStatus.SAVED)
        files = list(Path(self._tmp.name).iterdir())
        # Only the custom directory exists in the tree; nothing written outside it.
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], self.custom_dir)


class TestOutputDirValidation(unittest.TestCase):
    """US3: safe handling of new or invalid target locations."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

    def test_missing_nested_directory_created_with_parents(self):
        """A missing specified directory (including parents) is created."""
        target = self.tmp_root / "a" / "b" / "c"

        resolved = resolve_output_dir(str(target))

        self.assertEqual(resolved, target.absolute())
        self.assertTrue(resolved.is_dir())
        self.assertTrue((self.tmp_root / "a" / "b").is_dir())

    def test_existing_file_target_raises_naming_path(self):
        """A value naming an existing file raises with the path named."""
        blocker = self.tmp_root / "not-a-dir.txt"
        blocker.write_bytes(b"file")

        with self.assertRaises(OutputDirectoryError) as ctx:
            resolve_output_dir(str(blocker))

        self.assertIn(str(blocker), str(ctx.exception))
        self.assertIn("not a directory", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
