"""Tests for CLI exit codes, stderr error format, and usage errors (US3)."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import starwars_backgrounds as swb
from starwars_backgrounds import main

# Fixture HTML with one gallery image using a lumiere CDN URL
FIXTURE_HTML = """\
<html><body>
<figure><img src="https://lumiere-a.akamaihd.net/v1/images/test.jpeg" alt="Test BG"></figure>
</body></html>
"""

# Fixture HTML with no gallery images (zero backgrounds)
EMPTY_HTML = """\
<html><body><p>No images here.</p></body></html>
"""


class TestCLIExitCodes(unittest.TestCase):
    """Verify exit codes per contracts/cli.md."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "StarWarsBackground"
        self.output_dir.mkdir(parents=True)

    def _run_main(self, argv: list[str]) -> tuple[int, str, str]:
        """Run main() with given args; return (exit_code, stdout, stderr)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with patch.object(swb, "resolve_output_root", return_value=self.output_dir):
                with patch("sys.argv", ["starwars_backgrounds.py"] + argv):
                    with patch("sys.stdout", stdout_buf):
                        with patch("sys.stderr", stderr_buf):
                            code = main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_exit_0_on_all_success(self):
        """Exit 0 when all items download successfully."""
        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(
                swb, "download_image",
                return_value=(swb.Format.JPEG, 1024),
            ):
                code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 0)
        self.assertIn("Summary:", stdout)
        self.assertIn("1 downloaded", stdout)
        self.assertNotIn("ERROR", stderr)

    def test_exit_0_on_all_skipped(self):
        """Exit 0 when all items are skipped (already exist)."""
        from starwars_backgrounds import derive_filename, Format
        filename = derive_filename(1, "Test BG", Format.JPEG)
        (self.output_dir / filename).write_bytes(b"existing")

        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 0)
        self.assertIn("1 skipped", stdout)
        self.assertNotIn("ERROR", stderr)

    def test_exit_1_on_download_failure(self):
        """Exit 1 when one or more items fail to download."""
        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(
                swb, "download_image",
                side_effect=RuntimeError("connection refused"),
            ):
                code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 1)
        self.assertIn("ERROR", stderr)
        self.assertIn("1 failed", stdout)

    def test_exit_1_on_zero_backgrounds_found(self):
        """Exit 1 when the article contains no backgrounds."""
        with patch.object(swb, "fetch_article_html", return_value=EMPTY_HTML):
            code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 1)
        self.assertIn("ERROR", stderr)
        self.assertIn("No backgrounds found", stderr)

    def test_exit_1_on_fetch_failure(self):
        """Exit 1 when article page fetch fails after retries."""
        with patch.object(
            swb, "fetch_article_html",
            side_effect=RuntimeError("page unreachable"),
        ):
            code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 1)
        self.assertIn("ERROR", stderr)

    def test_exit_2_on_usage_error(self):
        """Exit 2 for unrecognized flags (argparse convention)."""
        with patch.object(swb, "fetch_article_html"):
            code, stdout, stderr = self._run_main(["--nonexistent-flag"])

        self.assertEqual(code, 2)

    def test_argparse_usage_error(self):
        """argparse exits with code 2 for invalid arguments."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with patch("sys.argv", ["starwars_backgrounds.py", "--invalid"]):
            with patch("sys.stdout", stdout_buf):
                with patch("sys.stderr", stderr_buf):
                    try:
                        main()
                        self.fail("Expected SystemExit for invalid arg")
                    except SystemExit as e:
                        self.assertEqual(e.code, 2)

    def test_stderr_error_line_format_network(self):
        """Network failure ERROR line includes URL and attempt context."""
        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            err_msg = (
                "attempt 3/3 https://lumiere-a.akamaihd.net/v1/images/test.jpeg: "
                "HTTPError after retries"
            )
            with patch.object(
                swb, "download_image",
                side_effect=RuntimeError(err_msg),
            ):
                code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 1)
        error_lines = [l for l in stderr.splitlines() if l.startswith("ERROR")]
        self.assertTrue(len(error_lines) >= 1, f"No ERROR lines: {stderr!r}")
        self.assertIn("test.jpeg", stderr)

    def test_stderr_error_line_format_zero_found(self):
        """Zero backgrounds found produces an ERROR line on stderr."""
        with patch.object(swb, "fetch_article_html", return_value=EMPTY_HTML):
            code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 1)
        error_lines = [l for l in stderr.splitlines() if l.startswith("ERROR")]
        self.assertTrue(len(error_lines) >= 1, f"No ERROR lines: {stderr!r}")

    def test_nonzero_exit_always_has_error_line(self):
        """Final non-zero exit is always preceded by at least one ERROR line."""
        scenarios = [
            ("fail", None),           # fetch fails
            (EMPTY_HTML, None),       # zero backgrounds
            (FIXTURE_HTML, "exception"),  # download fails
        ]

        for fetch_val, dl_err in scenarios:
            with self.subTest(fetch=fetch_val, dl=dl_err):
                stdout_buf = io.StringIO()
                stderr_buf = io.StringIO()

                if fetch_val == "fail":
                    fetch_mock = patch.object(
                        swb, "fetch_article_html",
                        side_effect=RuntimeError("unreachable"),
                    )
                else:
                    fetch_mock = patch.object(
                        swb, "fetch_article_html", return_value=fetch_val
                    )

                if dl_err == "exception":
                    dl_mock = patch.object(
                        swb, "download_image",
                        side_effect=RuntimeError("boom"),
                    )
                else:
                    dl_mock = patch.object(swb, "download_image")

                try:
                    with fetch_mock, dl_mock:
                        with patch.object(swb, "resolve_output_root", return_value=self.output_dir):
                            with patch("sys.argv", ["starwars_backgrounds.py"]):
                                with patch("sys.stdout", stdout_buf):
                                    with patch("sys.stderr", stderr_buf):
                                        code = main()
                except SystemExit as e:
                    code = e.code if isinstance(e.code, int) else 1

                self.assertEqual(code, 1)
                error_lines = [l for l in stderr_buf.getvalue().splitlines() if l.startswith("ERROR")]
                self.assertTrue(
                    len(error_lines) >= 1,
                    f"Non-zero exit {code} without ERROR line. stderr={stderr_buf.getvalue()!r}",
                )


if __name__ == "__main__":
    unittest.main()
