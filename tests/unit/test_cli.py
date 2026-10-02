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

        def fake_download(url, dest_dir, position=0, total=0, title=""):  # pylint: disable=unused-argument
            dest_dirs.append(Path(dest_dir))
            return (Format.JPEG, 1024)

        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(swb, "download_image", side_effect=fake_download):
                with patch.object(swb, "resolve_output_root") as mock_default:
                    code, _, _ = self._run_main(
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


class TestHelpFlag(unittest.TestCase):
    """US1/US2/US3: -h/--help displays comprehensive usage information."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

    def _run_main(
        self, argv: list[str]
    ) -> tuple[int, str, str]:
        """Run main() with given args; return (exit_code, stdout, stderr)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with patch.object(
                swb, "fetch_article_html",
                side_effect=AssertionError("network attempted"),
            ):
                with patch.object(
                    swb, "resolve_output_root",
                    return_value=self.tmp_root / "StarWarsBackground",
                ):
                    with patch("sys.argv", ["starwars_backgrounds.py"] + argv):
                        with patch("sys.stdout", stdout_buf):
                            with patch("sys.stderr", stderr_buf):
                                code = main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_help_exit_0_with_comprehensive_output(self):
        """--help exits 0 and prints description, all options with defaults."""
        code, stdout, stderr = self._run_main(["--help"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        lower = stdout.lower()
        # One-line description of what the tool does (FR-002a)
        self.assertIn("star wars", lower)
        self.assertIn("download", lower)
        # Every public option is documented (FR-002b)
        for flag in ("--help", "-h", "--overwrite", "--output-dir"):
            self.assertIn(flag, stdout)

    def test_help_documents_defaults_matching_runtime(self):
        """Documented defaults match runtime defaults (FR-005)."""
        code, stdout, _ = self._run_main(["--help"])

        self.assertEqual(code, 0)
        # Default output location is documented
        self.assertIn("<Pictures>/StarWarsBackground", stdout)
        # Overwrite-off-by-default is documented on the --overwrite line
        overwrite_lines = [
            line for line in stdout.splitlines() if "--overwrite" in line
        ]
        self.assertTrue(overwrite_lines, "No --overwrite documentation found")
        self.assertIn("default", " ".join(overwrite_lines).lower())

    def test_help_includes_example_per_behavior(self):
        """At least one example invocation per supported behavior (FR-002c)."""
        code, stdout, _ = self._run_main(["--help"])

        self.assertEqual(code, 0)
        example_lines = [
            line.strip()
            for line in stdout.splitlines()
            if "starwars_backgrounds.py" in line
            and not line.lstrip().startswith("Usage")
        ]
        default_runs = [l for l in example_lines if "--" not in l]
        self.assertTrue(default_runs, "No default-run example found")
        custom_dir_examples = [l for l in example_lines if "--output-dir" in l]
        self.assertTrue(custom_dir_examples, "No custom-directory example found")
        overwrite_examples = [l for l in example_lines if "--overwrite" in l]
        self.assertTrue(
            overwrite_examples, "No forced re-download example found"
        )

    def test_help_performs_no_side_effects(self):
        """--help exits 0 without network requests or filesystem writes."""
        with patch.object(swb, "resolve_output_root") as mock_resolve:
            code, _, stderr = self._run_main(["--help"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        mock_resolve.assert_not_called()
        # No files or directories created anywhere under the temp root
        self.assertEqual(list(self.tmp_root.iterdir()), [])

    def test_help_output_is_ascii_only(self):
        """Help text is plain ASCII (clarification Q1; FR-006 edge case)."""
        code, stdout, _ = self._run_main(["--help"])

        self.assertEqual(code, 0)
        non_ascii = [c for c in stdout if ord(c) >= 128]
        self.assertEqual(non_ascii, [], "Help output must be ASCII-only")

    def test_short_form_identical_to_long_form(self):
        """-h produces byte-identical stdout and exit status to --help."""
        code_long, out_long, err_long = self._run_main(["--help"])
        code_short, out_short, err_short = self._run_main(["-h"])

        self.assertEqual(code_long, 0)
        self.assertEqual(code_short, 0)
        self.assertEqual(out_short, out_long)
        self.assertEqual(err_long, "")
        self.assertEqual(err_short, "")


class TestHelpPrecedence(unittest.TestCase):
    """US3: help wins over valid options; invalid input still errors."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)

    def _run_main(
        self, argv: list[str]
    ) -> tuple[int, str, str]:
        """Run main() with given args; return (exit_code, stdout, stderr)."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with patch.object(
                swb, "fetch_article_html",
                side_effect=AssertionError("network attempted"),
            ):
                with patch("sys.argv", ["starwars_backgrounds.py"] + argv):
                    with patch("sys.stdout", stdout_buf):
                        with patch("sys.stderr", stderr_buf):
                            code = main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_help_wins_over_valid_options(self):
        """--help combined with valid options prints help and exits 0."""
        target = str(self.tmp_root / "custom")
        for argv in (
            ["--help", "--overwrite", "--output-dir", target],
            ["--overwrite", "--output-dir", target, "--help"],
        ):
            with self.subTest(argv=argv):
                code, stdout, stderr = self._run_main(argv)

            self.assertEqual(code, 0)
            self.assertIn("--output-dir", stdout)
            self.assertEqual(stderr, "")
        # No directory created and no download started (SC-003)
        self.assertFalse(Path(target).exists())

    def test_blank_value_precedes_help(self):
        """Blank --output-dir value errors even when --help is present."""
        for argv in (["--output-dir", "", "--help"], ["--help", "--output-dir", ""]):
            with self.subTest(argv=argv):
                code, stdout, stderr = self._run_main(argv)

            self.assertEqual(code, 2)
            self.assertIn("--output-dir", stderr)
            # No help text displayed on usage errors (argparse writes to stderr)
            self.assertEqual(stdout, "")

    def test_unrecognized_option_precedes_help(self):
        """Unrecognized option errors even when --help is present."""
        for argv in (["--bogus", "--help"], ["--help", "--bogus"]):
            with self.subTest(argv=argv):
                code, _, stderr = self._run_main(argv)

            self.assertEqual(code, 2)
            self.assertIn("--bogus", stderr)


if __name__ == "__main__":
    unittest.main()
