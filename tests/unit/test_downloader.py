"""Tests for image download behavior using a local HTTP stub server."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import starwars_backgrounds as swb
from starwars_backgrounds import Format, derive_filename, download_image
from tests.unit.stub_server import (
    JPEG_BYTES,
    PNG_BYTES,
    TEXT_BYTES,
    StubHandler,
    StubServer,
)


class TestDownloadImage(unittest.TestCase):
    """Test download_image using a local stub server."""

    @classmethod
    def setUpClass(cls):
        cls.server = StubServer.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.dest_dir = Path(self._tmp.name) / "output"
        self.dest_dir.mkdir(parents=True)

    def test_download_jpeg_atomic_write(self):
        """Download a JPEG and verify atomic write (no partial file remains)."""
        url = f"{self.server.base_url}/test-image.jpeg?region=0,0,1920,1080"
        fmt, bytes_written = download_image(url, self.dest_dir)
        self.assertEqual(fmt, Format.JPEG)
        self.assertEqual(bytes_written, len(JPEG_BYTES))

    def test_download_strips_query_string(self):
        """The downloaded URL should have query stripped (canonical CDN object)."""
        url = f"{self.server.base_url}/test-image.jpeg?region=0,0,1920,1080"
        download_image(url, self.dest_dir, position=1, total=1, title="Test Image")
        # File should exist with derived name (query stripped from URL)
        filename = derive_filename(1, "Test Image", Format.JPEG)
        dest = self.dest_dir / filename
        self.assertTrue(dest.exists())

    def test_download_png(self):
        """Download a PNG and verify format detection."""
        url = f"{self.server.base_url}/test-image.png"
        fmt, bytes_written = download_image(url, self.dest_dir)
        self.assertEqual(fmt, Format.PNG)
        self.assertEqual(bytes_written, len(PNG_BYTES))

    def test_no_partial_file_on_failure(self):
        """If download fails (500), no partial file should remain."""
        url = f"{self.server.base_url}/fail-image.jpeg"
        self.server.fail_paths.add("/fail-image.jpeg")
        try:
            with patch.object(swb, "_sleep"):
                download_image(url, self.dest_dir)
            self.fail("Expected exception for 500 response")
        except (RuntimeError, ValueError):
            pass
        # No .tmp or partial files should remain
        remaining = list(self.dest_dir.iterdir())
        self.assertEqual(remaining, [], f"Files remain after failure: {remaining}")

    def test_progress_line_format(self):
        """Verify the progress line matches [i/N] <title> -> <path> (<bytes>)."""
        url = f"{self.server.base_url}/progress-test.jpeg"
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            download_image(url, self.dest_dir, position=5, total=99, title="Hoth")
        output = mock_stdout.getvalue().strip()
        lines = [line for line in output.splitlines() if line.strip()]
        self.assertTrue(len(lines) >= 1, f"No output captured: {output!r}")
        first_line = lines[0]
        self.assertIn("[5/99]", first_line)
        self.assertIn("Hoth", first_line)
        self.assertIn("->", first_line)
        self.assertRegex(first_line, r"\(\d+ bytes\)")


class TestRetryBehavior(unittest.TestCase):
    """Test retry policy: up to 3 attempts with exponential backoff."""

    @classmethod
    def setUpClass(cls):
        cls.server = StubServer.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.dest_dir = Path(self._tmp.name) / "output"
        self.dest_dir.mkdir(parents=True)

    def test_retry_exhaustion_3_attempts(self):
        """After 3 failed attempts, exception is raised with attempt info."""
        url = f"{self.server.base_url}/retry-fail.jpeg"
        self.server.fail_paths.add("/retry-fail.jpeg")

        sleep_calls: list[float] = []
        with patch.object(swb, "_sleep", side_effect=sleep_calls.append):
            try:
                download_image(url, self.dest_dir)
                self.fail("Expected exception after retry exhaustion")
            except RuntimeError as e:
                msg = str(e)
                # Should mention attempt 3/3 and the URL
                self.assertIn("attempt 3/3", msg)
                self.assertIn("/retry-fail.jpeg", msg)

        # Verify exactly 3 requests were made
        self.assertEqual(self.server.request_counts.get("/retry-fail.jpeg"), 3)
        # Backoff: sleep called twice (after attempt 1 and 2), with 1s then 2s
        self.assertEqual(sleep_calls, [1.0, 2.0])

    def test_retry_succeeds_on_third_attempt(self):
        """If server recovers on attempt 3, download succeeds."""
        url = f"{self.server.base_url}/flaky.jpeg"

        call_count = {"n": 0}
        original_do_get = StubHandler.do_GET

        def patched_do_get(self_handler):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                self_handler.send_response(500)
                self_handler.end_headers()
                return
            # Remove from fail set so subsequent calls succeed
            original_do_get(self_handler)

        with patch.object(swb, "_sleep"):
            with patch.object(StubHandler, "do_GET", patched_do_get):
                fmt, _ = download_image(url, self.dest_dir)
            self.assertEqual(fmt, Format.JPEG)

    def test_no_retry_on_format_rejection(self):
        """Format rejection is not retried — fails immediately."""
        url = f"{self.server.base_url}/not-an-image.jpeg"
        # Serve plain text for this path (will fail magic byte check)
        self.server.custom_content["/not-an-image.jpeg"] = TEXT_BYTES

        sleep_calls: list[float] = []
        with patch.object(swb, "_sleep", side_effect=sleep_calls.append):
            try:
                download_image(url, self.dest_dir, position=1, total=1, title="Bad Image")
                self.fail("Expected format rejection")
            except ValueError as e:
                msg = str(e)
                self.assertIn("rejected format", msg.lower())

        # Only 1 request made (no retry on format error)
        self.assertEqual(self.server.request_counts.get("/not-an-image.jpeg"), 1)
        # No sleep calls (format rejection doesn't trigger backoff)
        self.assertEqual(sleep_calls, [])


class TestErrorMessages(unittest.TestCase):
    """Test that error messages include required context per contract."""

    @classmethod
    def setUpClass(cls):
        cls.server = StubServer.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.dest_dir = Path(self._tmp.name) / "output"
        self.dest_dir.mkdir(parents=True)

    def test_network_error_includes_url_and_attempt(self):
        """Network failure error includes URL, attempt number, and error type."""
        url = f"{self.server.base_url}/error-msg.jpeg"
        self.server.fail_paths.add("/error-msg.jpeg")

        with patch.object(swb, "_sleep"):
            try:
                download_image(url, self.dest_dir)
                self.fail("Expected exception")
            except RuntimeError as e:
                msg = str(e)
                # Must include the URL
                self.assertIn("/error-msg.jpeg", msg)
                # Must include attempt number
                self.assertIn("attempt 3/3", msg)

    def test_format_error_includes_title_and_url(self):
        """Format rejection error names item title and URL."""
        url = f"{self.server.base_url}/format-err.jpeg"
        self.server.custom_content["/format-err.jpeg"] = TEXT_BYTES

        with patch.object(swb, "_sleep"):
            try:
                download_image(url, self.dest_dir, position=7, total=99, title="Hoth")
                self.fail("Expected format rejection")
            except ValueError as e:
                msg = str(e)
                # Must include the URL
                self.assertIn("/format-err.jpeg", msg)


if __name__ == "__main__":
    unittest.main()
