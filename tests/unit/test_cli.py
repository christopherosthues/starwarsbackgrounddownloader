"""Tests for CLI exit codes, stderr error format, and usage errors (US3)."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import starwars_backgrounds as swb
from starwars_backgrounds import Format, derive_filename, main

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
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
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
            code, _, stderr = self._run_main([])

        self.assertEqual(code, 1)
        self.assertIn("ERROR", stderr)
        self.assertIn("No backgrounds found", stderr)

    def test_exit_1_on_fetch_failure(self):
        """Exit 1 when article page fetch fails after retries."""
        with patch.object(
            swb, "fetch_article_html",
            side_effect=RuntimeError("page unreachable"),
        ):
            code, _, stderr = self._run_main([])

        self.assertEqual(code, 1)
        self.assertIn("ERROR", stderr)

    def test_exit_2_on_usage_error(self):
        """Exit 2 for unrecognized flags (argparse convention)."""
        with patch.object(swb, "fetch_article_html"):
            code, _, _ = self._run_main(["--nonexistent-flag"])

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
                code, _, stderr = self._run_main([])

        self.assertEqual(code, 1)
        error_lines = [line for line in stderr.splitlines() if line.startswith("ERROR")]
        self.assertTrue(len(error_lines) >= 1, f"No ERROR lines: {stderr!r}")
        self.assertIn("test.jpeg", stderr)

    def test_stderr_error_line_format_zero_found(self):
        """Zero backgrounds found produces an ERROR line on stderr."""
        with patch.object(swb, "fetch_article_html", return_value=EMPTY_HTML):
            code, _, stderr = self._run_main([])

        self.assertEqual(code, 1)
        error_lines = [line for line in stderr.splitlines() if line.startswith("ERROR")]
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
                error_lines = [
                    line for line in stderr_buf.getvalue().splitlines()
                    if line.startswith("ERROR")
                ]
                self.assertTrue(
                    len(error_lines) >= 1,
                    f"Non-zero exit {code} without ERROR line. stderr={stderr_buf.getvalue()!r}",
                )


class TestDefaultBehaviorUnchanged(unittest.TestCase):
    """US2: invocations without --output-dir behave exactly as before."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
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

    def test_no_option_uses_default_resolution(self):
        """Without --output-dir the default Pictures-based folder is used."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with patch.object(
            swb, "resolve_output_root", return_value=self.output_dir
        ) as mock_resolve:
            with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
                with patch.object(
                    swb, "download_image",
                    return_value=(Format.JPEG, 1024),
                ):
                    with patch("sys.argv", ["starwars_backgrounds.py"]):
                        with patch("sys.stdout", stdout_buf):
                            with patch("sys.stderr", stderr_buf):
                                code = main()

        self.assertEqual(code, 0)
        mock_resolve.assert_called_once()

    def test_re_run_without_options_is_idempotent(self):
        """A second run without options skips existing files and exits 0."""
        filename = derive_filename(1, "Test BG", Format.JPEG)
        (self.output_dir / filename).write_bytes(b"existing")

        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            code_first, _, _ = self._run_main([])
            code_second, stdout_second, _ = self._run_main([])

        self.assertEqual(code_first, 0)
        self.assertEqual(code_second, 0)
        self.assertIn("1 skipped", stdout_second)


class TestOutputDirOption(unittest.TestCase):
    """US1: --output-dir directs all images into the specified directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.custom_dir = Path(self._tmp.name) / "custom"
        self.custom_dir.mkdir()

    def _run_main(self, argv: list[str]) -> tuple[int, str, str]:
        """Run main() with given args; return (exit_code, stdout, stderr)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with patch("sys.argv", ["starwars_backgrounds.py"] + argv):
                with patch("sys.stdout", stdout_buf):
                    with patch("sys.stderr", stderr_buf):
                        code = main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_all_images_saved_in_custom_dir(self):
        """Every download targets the custom directory; default folder untouched."""
        dest_dirs: list[Path] = []

        def fake_download(url, dest_dir, position=0, total=0, title=""):
            dest_dirs.append(Path(dest_dir))
            return (Format.JPEG, 1024)

        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(swb, "download_image", side_effect=fake_download):
                with patch.object(swb, "resolve_output_root") as mock_default:
                    code, stdout, _ = self._run_main(
                        ["--output-dir", str(self.custom_dir)]
                    )

        self.assertEqual(code, 0)
        self.assertTrue(dest_dirs, "No downloads were performed")
        for dest in dest_dirs:
            self.assertEqual(dest, self.custom_dir)
        mock_default.assert_not_called()

    def test_progress_and_summary_report_custom_dir_paths(self):
        """Progress lines and the summary report paths inside the custom dir."""
        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(
                swb, "download_image",
                return_value=(Format.JPEG, 1024),
            ):
                code, stdout, _ = self._run_main(
                    ["--output-dir", str(self.custom_dir)]
                )

        self.assertEqual(code, 0)
        self.assertIn(str(self.custom_dir), stdout)
        self.assertIn(f"Output folder: {self.custom_dir}", stdout)


class TestOutputDirErrors(unittest.TestCase):
    """US3: blank values, path-is-file targets, and creation failures."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

    def _run_main(self, argv: list[str]) -> tuple[int, str, str]:
        """Run main() with given args; return (exit_code, stdout, stderr)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with patch("sys.argv", ["starwars_backgrounds.py"] + argv):
                with patch("sys.stdout", stdout_buf):
                    with patch("sys.stderr", stderr_buf):
                        code = main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_blank_value_rejected_with_usage_error(self):
        """Blank --output-dir value exits 2 without falling back to default."""
        with patch.object(swb, "resolve_output_root") as mock_default:
            code, _, stderr = self._run_main(["--output-dir", ""])

        self.assertEqual(code, 2)
        self.assertIn("error", stderr.lower())
        mock_default.assert_not_called()

    def test_whitespace_only_value_rejected_with_usage_error(self):
        """Whitespace-only --output-dir value exits 2."""
        code, _, _ = self._run_main(["--output-dir", "   "])

        self.assertEqual(code, 2)

    def test_path_is_file_errors_and_starts_no_downloads(self):
        """Path-is-file target: ERROR naming the path, exit 1, file untouched."""
        blocker = self.tmp_root / "not-a-dir.txt"
        blocker.write_bytes(b"file")

        with patch.object(swb, "fetch_article_html") as mock_fetch:
            code, _, stderr = self._run_main(["--output-dir", str(blocker)])

        self.assertEqual(code, 1)
        error_lines = [line for line in stderr.splitlines() if line.startswith("ERROR")]
        self.assertTrue(len(error_lines) >= 1, f"No ERROR lines: {stderr!r}")
        self.assertIn(str(blocker), stderr)
        self.assertIn("not a directory", stderr)
        mock_fetch.assert_not_called()
        self.assertEqual(blocker.read_bytes(), b"file")

    def test_creation_failure_errors_with_exit_1(self):
        """A creation failure (parent is a file) errors and exits 1."""
        blocker = self.tmp_root / "not-a-dir.txt"
        blocker.write_bytes(b"file")
        target = str(blocker) + r"\nested"

        code, _, stderr = self._run_main(["--output-dir", target])

        self.assertEqual(code, 1)
        error_lines = [line for line in stderr.splitlines() if line.startswith("ERROR")]
        self.assertTrue(len(error_lines) >= 1, f"No ERROR lines: {stderr!r}")


if __name__ == "__main__":
    unittest.main()
