"""Tests for temp-staged hash deduplication (feature 004, US1).

Covers: streaming SHA-256 computation, run-start baseline hashing of the
target directory, and the move-phase duplicate pass that discards staged
files whose content hash is already known (FR-001, FR-007, SC-001).
"""

import hashlib
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import starwars_backgrounds as swb
from tests.unit.stub_server import JPEG_BYTES, StubServer


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class TestHashFile(unittest.TestCase):
    """Streaming SHA-256 via chunked reads (research.md R2)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

    def test_matches_hashlib_reference(self):
        """hash_file equals hashlib.sha256 over the same bytes."""
        content = b"hello star wars"
        path = self.tmp_root / "a.jpg"
        path.write_bytes(content)
        self.assertEqual(swb.hash_file(path), _sha(content))

    def test_empty_file(self):
        """An empty file hashes to the SHA-256 of the empty string."""
        path = self.tmp_root / "empty.jpg"
        path.write_bytes(b"")
        self.assertEqual(
            swb.hash_file(path),
            hashlib.sha256(b"").hexdigest(),
        )

    def test_large_content_chunked(self):
        """Content larger than the chunk size is hashed correctly."""
        content = (b"0123456789abcdef" * 4) * 60_000  # ~3 MiB, > HASH_CHUNK_SIZE
        path = self.tmp_root / "big.jpg"
        path.write_bytes(content)
        self.assertEqual(swb.hash_file(path), _sha(content))


class TestBuildBaselineHashes(unittest.TestCase):
    """Run-start baseline hashing of the target directory (research.md R2)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.target_dir = Path(self._tmp.name) / "target"
        self.target_dir.mkdir()

    def test_hashes_all_existing_files(self):
        """Every existing file's hash is in the baseline set."""
        (self.target_dir / "a.jpg").write_bytes(b"content-a")
        (self.target_dir / "b.png").write_bytes(b"content-b")
        self.assertEqual(
            swb.build_baseline_hashes(self.target_dir),
            {_sha(b"content-a"), _sha(b"content-b")},
        )

    def test_ignores_subdirectories(self):
        """Subdirectories are not treated as files and cause no error."""
        (self.target_dir / "a.jpg").write_bytes(b"content-a")
        sub = self.target_dir / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_bytes(b"nested")
        self.assertEqual(
            swb.build_baseline_hashes(self.target_dir),
            {_sha(b"content-a")},
        )

    def test_unreadable_file_logs_error_and_continues(self):
        """An unreadable file produces an ERROR line naming the path and
        contributes no hash; other files are still hashed."""
        good = self.target_dir / "good.jpg"
        good.write_bytes(b"content-good")
        bad = self.target_dir / "bad.jpg"
        bad.write_bytes(b"unreadable")

        original_hash = swb.hash_file

        def _side_effect(path: Path) -> str:
            if path.name == "bad.jpg":
                raise OSError("simulated read failure")
            return original_hash(path)

        stderr = io.StringIO()
        with patch.object(swb, "hash_file", side_effect=_side_effect):
            with redirect_stderr(stderr):
                result = swb.build_baseline_hashes(self.target_dir)

        self.assertEqual(result, {_sha(b"content-good")})
        output = stderr.getvalue()
        self.assertIn("ERROR", output)
        self.assertIn("bad.jpg", output)


class TestDedupStagedFiles(unittest.TestCase):
    """Move-phase duplicate pass: hash matches are discarded (FR-001)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.target_dir = self.root / "target"
        self.staged_dir = self.root / "staged"
        self.target_dir.mkdir()
        self.staged_dir.mkdir()

    def test_idempotent_rerun_discards_all(self):
        """A second run against an unchanged target discards every staged
        file as a hash match and leaves the target byte-for-byte identical."""
        contents = {f"img-{i}.jpg": f"content-{i}".encode() for i in range(3)}
        for name, content in contents.items():
            (self.target_dir / name).write_bytes(content)

        baseline_before = swb.build_baseline_hashes(self.target_dir)
        staged_paths = []
        for name, content in contents.items():
            staged_path = self.staged_dir / name
            staged_path.write_bytes(content)
            staged_paths.append(staged_path)

        seen = swb.build_baseline_hashes(self.target_dir)
        kept, discarded = swb.dedup_staged_files(staged_paths, seen)

        self.assertEqual(kept, [])
        self.assertEqual(discarded, len(contents))
        for staged_path in staged_paths:
            self.assertFalse(staged_path.exists())
        # Target untouched: same hashes as before the pass.
        self.assertEqual(swb.build_baseline_hashes(self.target_dir), baseline_before)

    def test_new_content_is_kept_and_hash_recorded(self):
        """A staged file with a novel hash is kept and its hash joins the
        seen set so later runs discard it."""
        (self.target_dir / "existing.jpg").write_bytes(b"existing")
        staged = self.staged_dir / "new.jpg"
        staged.write_bytes(b"brand-new-content")

        seen = swb.build_baseline_hashes(self.target_dir)
        kept, discarded = swb.dedup_staged_files([staged], seen)

        self.assertEqual(kept, [(staged, _sha(b"brand-new-content"))])
        self.assertEqual(discarded, 0)
        self.assertTrue(staged.exists())
        self.assertIn(_sha(b"brand-new-content"), seen)

    def test_same_hash_different_names_first_wins(self):
        """Two staged files with identical content but different names: the
        first occurrence is kept under its original name; the second is
        discarded (spec edge case)."""
        content = b"duplicate-content"
        first = self.staged_dir / "first.jpg"
        second = self.staged_dir / "second.jpg"
        first.write_bytes(content)
        second.write_bytes(content)

        seen: set[str] = set()
        kept, discarded = swb.dedup_staged_files([first, second], seen)

        self.assertEqual(kept, [(first, _sha(content))])
        self.assertEqual(discarded, 1)
        self.assertTrue(first.exists())
        self.assertFalse(second.exists())


class TestBestEffortMove(unittest.TestCase):
    """US3 (T010): best-effort move semantics against stub server."""

    @classmethod
    def setUpClass(cls):
        cls.server = StubServer.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.target_dir = self.root / "target"
        self.staged_dir = self.root / "staged"
        self.target_dir.mkdir()
        self.staged_dir.mkdir()

    @patch("starwars_backgrounds.tempfile.gettempdir")
    def test_one_fail_others_succeed(self, mock_gettempdir):
        """One staged file fails to move; others are moved successfully."""
        mock_gettempdir.return_value = str(self.root)

        # Create 3 staged files
        for i in range(3):
            (self.staged_dir / f"img-{i}.jpg").write_bytes(JPEG_BYTES[:10] + bytes([i]) * 90)

        # Simulate: first two move OK, third fails with OSError
        moved_paths: list[Path] = []
        fail_count = 0

        def fake_move(src, dst):
            nonlocal fail_count
            src_path = Path(src)
            if src_path.name == "img-2.jpg":
                fail_count += 1
                raise OSError("simulated move failure")
            # Manual copy: do NOT re-invoke the patched shutil.move.
            dst_path = Path(dst)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_bytes(src_path.read_bytes())
            src_path.unlink()
            moved_paths.append(dst_path)

        kept = [(self.staged_dir / f"img-{i}.jpg", _sha(JPEG_BYTES[:10] + bytes([i]) * 90))
                for i in range(3)]
        seen: set[str] = set()

        stderr_buf = io.StringIO()
        with patch("shutil.move", side_effect=fake_move):
            with redirect_stderr(stderr_buf):
                results = swb.move_staged_files(kept, self.target_dir, seen)

        # 2 moved successfully
        self.assertEqual(len(moved_paths), 2)
        for i in range(2):
            self.assertTrue((self.target_dir / f"img-{i}.jpg").exists())

        # 1 failed with ERROR on stderr
        output = stderr_buf.getvalue()
        self.assertIn("ERROR", output)
        self.assertIn("img-2.jpg", output)

        # Results reflect the split
        moved, failed = results
        self.assertEqual(len(moved), 2)
        self.assertEqual(len(failed), 1)

    def test_missing_staged_file_reported_and_skipped(self):
        """A staged file deleted before move yields a clear ERROR, not a crash."""
        (self.staged_dir / "ok.jpg").write_bytes(JPEG_BYTES)
        kept = [
            (self.staged_dir / "gone.jpg", _sha(b"never written")),
            (self.staged_dir / "ok.jpg", _sha(JPEG_BYTES)),
        ]
        seen: set[str] = set()

        stderr_buf = io.StringIO()
        with redirect_stderr(stderr_buf):
            moved, failed = swb.move_staged_files(kept, self.target_dir, seen)

        # The vanished file is counted as failed with a clear diagnostic.
        self.assertEqual(len(moved), 1)
        self.assertEqual(len(failed), 1)
        output = stderr_buf.getvalue()
        self.assertIn("gone.jpg", output)
        self.assertIn("staging file missing at move time", output)


class TestPostfixCollision(unittest.TestCase):
    """US4 (T014/T015): sequential postfix for name conflicts."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.target_dir = self.root / "target"
        self.staged_dir = self.root / "staged"
        self.target_dir.mkdir()
        self.staged_dir.mkdir()

    def test_existing_name_gets_postfix_1(self):
        """Pre-existing name.jpg yields name-1.jpg."""
        (self.target_dir / "name.jpg").write_bytes(b"existing")
        dest = swb.resolve_dest_path("name.jpg", self.target_dir)
        self.assertEqual(dest, self.target_dir / "name-1.jpg")

    def test_skips_existing_postfixes(self):
        """Pre-existing name.jpg, name-1.jpg, name-2.jpg yields name-3.jpg."""
        for name in ("name.jpg", "name-1.jpg", "name-2.jpg"):
            (self.target_dir / name).write_bytes(b"x")
        dest = swb.resolve_dest_path("name.jpg", self.target_dir)
        self.assertEqual(dest, self.target_dir / "name-3.jpg")

    def test_free_name_unchanged(self):
        """A non-colliding derived name is returned as-is."""
        dest = swb.resolve_dest_path("fresh.jpg", self.target_dir)
        self.assertEqual(dest, self.target_dir / "fresh.jpg")

    def test_overwrite_returns_existing_path(self):
        """With overwrite=True the existing path is returned for replacement."""
        (self.target_dir / "name.jpg").write_bytes(b"existing")
        dest = swb.resolve_dest_path("name.jpg", self.target_dir, overwrite=True)
        self.assertEqual(dest, self.target_dir / "name.jpg")

    def test_move_resolves_against_live_state_including_earlier_moves(self):
        """Numbering continues to the next free slot against live target state;
        existing colliding files are never overwritten."""
        (self.target_dir / "name.jpg").write_bytes(b"existing")
        (self.target_dir / "name-1.jpg").write_bytes(b"existing-1")

        first = self.staged_dir / "name.jpg"
        first.write_bytes(b"a")
        moved, failed = swb.move_staged_files(
            [(first, _sha(b"a"))], self.target_dir, set()
        )
        self.assertEqual(failed, [])
        self.assertEqual(moved[0].name, "name-2.jpg")

        second = self.staged_dir / "name.jpg"
        second.write_bytes(b"b")
        moved2, failed2 = swb.move_staged_files(
            [(second, _sha(b"b"))], self.target_dir, set()
        )
        self.assertEqual(failed2, [])
        self.assertEqual(moved2[0].name, "name-3.jpg")

        # Existing colliding files are untouched.
        self.assertEqual((self.target_dir / "name.jpg").read_bytes(), b"existing")
        self.assertEqual(
            (self.target_dir / "name-1.jpg").read_bytes(), b"existing-1"
        )

    def test_overwrite_replaces_existing(self):
        """With overwrite=True a staged file replaces the existing target file."""
        (self.target_dir / "name.jpg").write_bytes(b"old")
        staged = self.staged_dir / "name.jpg"
        staged.write_bytes(b"new")

        moved, failed = swb.move_staged_files(
            [(staged, _sha(b"new"))], self.target_dir, set(), overwrite=True
        )
        self.assertEqual(failed, [])
        self.assertEqual(moved[0].name, "name.jpg")
        self.assertEqual((self.target_dir / "name.jpg").read_bytes(), b"new")


if __name__ == "__main__":
    unittest.main()
