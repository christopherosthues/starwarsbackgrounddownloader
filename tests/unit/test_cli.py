"""Tests for CLI exit codes, stderr error format, and usage errors (US3)."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import starwars_backgrounds as swb
from starwars_backgrounds import Format, derive_filename, main
from tests.unit.base_test_case import ServerTestCase

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
        # New two-phase summary format (R8): moved, duplicates discarded, failed
        self.assertIn("moved", stdout.lower())
        self.assertNotIn("ERROR", stderr)

    def test_exit_0_on_all_skipped(self):
        """Exit 0 when all items are skipped (already exist)."""
        filename = derive_filename(1, "Test BG", Format.JPEG)
        (self.output_dir / filename).write_bytes(b"existing")

        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(
                swb, "download_image",
                return_value=(swb.Format.JPEG, 1024),
            ):
                code, stdout, stderr = self._run_main([])

        self.assertEqual(code, 0)
        # In two-phase pipeline, existing files are detected as duplicates during move phase
        summary_lines = [l for l in stdout.splitlines() if l.startswith("Summary:")]
        self.assertTrue(summary_lines)
        self.assertIn("Summary:", stdout)
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
            with patch.object(
                swb, "download_image",
                return_value=(swb.Format.JPEG, 1024),
            ):
                code_first, _, _ = self._run_main([])
                code_second, stdout_second, _ = self._run_main([])

        self.assertEqual(code_first, 0)
        self.assertEqual(code_second, 0)
        # Second run: existing content is detected as duplicate during move phase
        summary_lines = [l for l in stdout_second.splitlines() if l.startswith("Summary:")]
        self.assertTrue(summary_lines)


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

        def fake_download(url, dest_dir, **kwargs):  # pylint: disable=unused-argument
            dest_dirs.append(Path(dest_dir))
            filename = kwargs.get("filename")
            if filename and Path(dest_dir).is_dir():
                (Path(dest_dir) / filename).write_bytes(b"\xff\xd8\xff" + b"\x00" * 1021)
            return (Format.JPEG, 1024)

        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(swb, "download_image", side_effect=fake_download):
                with patch.object(swb, "resolve_output_root") as mock_default:
                    code, _, _ = self._run_main(
                        ["--output-dir", str(self.custom_dir)]
                    )

        self.assertEqual(code, 0)
        self.assertTrue(dest_dirs, "No downloads were performed")
        # In two-phase pipeline, dest_dir is staging; files are moved to custom_dir after
        for dest in dest_dirs:
            self.assertIn("swbdl", str(dest))
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
        # Join with the platform separator so this is a nested path on every OS
        # (a literal backslash would only nest on Windows).
        target = str(blocker / "nested")

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
        for flag in ("--help", "-h", "--overwrite", "--output-dir", "--delay"):
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


class TestTwoPhaseOutput(unittest.TestCase):
    """US3 (T011): two-phase stdout progress and summary format."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "StarWarsBackground"
        self.output_dir.mkdir(parents=True)
        self.staged_dir = Path(self._tmp.name) / "staged"

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

    def test_summary_format_moved_duplicates_failed(self):
        """Summary uses 'X moved, Y duplicates discarded, Z failed' format."""
        with patch.object(swb, "fetch_article_html", return_value=FIXTURE_HTML):
            with patch.object(
                swb, "download_image",
                return_value=(swb.Format.JPEG, 1024),
            ):
                code, stdout, _ = self._run_main([])

        self.assertEqual(code, 0)
        summary_lines = [l for l in stdout.splitlines() if l.startswith("Summary:")]
        self.assertTrue(summary_lines, "No Summary line found")
        summary = summary_lines[0]
        # New format: moved, duplicates discarded, failed
        self.assertIn("moved", summary.lower())
        self.assertIn("discarded", summary.lower())
        self.assertIn("failed", summary.lower())

    def test_exit_1_on_partial_failure(self):
        """Exit 1 when one item fails among many."""
        multi_html = (
            '<html><body>'
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/one.jpeg" '
            'alt="One"></figure>'
            '<figure><img src="https://lumiere-a.akamaihd.net/v1/images/two.jpeg" '
            'alt="Two"></figure>'
            '</body></html>'
        )
        call_count = 0

        def side_effect(_, __, ___):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (swb.Format.JPEG, 1024)
            raise RuntimeError("simulated failure")

        with patch.object(swb, "fetch_article_html", return_value=multi_html):
            with patch.object(swb, "download_image", side_effect=side_effect):
                code, _, stderr = self._run_main([])

        self.assertEqual(code, 1)
        self.assertIn("ERROR", stderr)


class TestDownloadProgressNotDuplicated(ServerTestCase):
    """Regression: the download phase prints exactly one progress line per item."""

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

    def test_exactly_one_progress_line_per_item(self):
        """A full run prints one [i/N] line per item (no duplicated lines)."""
        html = (
            '<html><body>'
            f'<figure><img src="{self.server.base_url}/test.jpeg" alt="Test BG"></figure>'
            '</body></html>'
        )
        with patch.object(swb, "LUMIERE_CDN_PREFIX", self.server.base_url + "/"):
            with patch.object(swb, "fetch_article_html", return_value=html):
                code, stdout, _ = self._run_main([])

        self.assertEqual(code, 0)
        progress_lines = [
            line for line in stdout.splitlines() if line.startswith("[1/1]")
        ]
        self.assertEqual(
            len(progress_lines),
            1,
            f"Expected exactly one progress line per item: {stdout!r}",
        )


class TestDuplicateDiscardLine(ServerTestCase):
    """Regression: hash-match discards report which file was discarded (R8)."""

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

    def test_discard_line_names_the_duplicate_file(self):
        """Two items with identical content: the second is reported as discarded."""
        html = (
            '<html><body>'
            f'<figure><img src="{self.server.base_url}/one.jpeg" alt="One"></figure>'
            f'<figure><img src="{self.server.base_url}/two.jpeg" alt="Two"></figure>'
            '</body></html>'
        )
        with patch.object(swb, "LUMIERE_CDN_PREFIX", self.server.base_url + "/"):
            with patch.object(swb, "fetch_article_html", return_value=html):
                code, stdout, _ = self._run_main([])

        self.assertEqual(code, 0)
        discard_lines = [
            line for line in stdout.splitlines() if "duplicate (hash match)" in line
        ]
        self.assertEqual(
            len(discard_lines),
            1,
            f"Expected exactly one discard line: {stdout!r}",
        )
        # The discarded item is the second occurrence of the content.
        self.assertIn("two.jpg", discard_lines[0])
        summary = next(line for line in stdout.splitlines() if line.startswith("Summary:"))
        self.assertIn("1 duplicates discarded", summary)


class TestDelayOption(unittest.TestCase):
    """T016: --delay parsing, validation, and inter-request throttling."""

    MULTI_ITEM_HTML = """\
<html><body>
<figure><img src="https://lumiere-a.akamaihd.net/v1/images/one.jpeg" alt="One"></figure>
<figure><img src="https://lumiere-a.akamaihd.net/v1/images/two.jpeg" alt="Two"></figure>
</body></html>
"""

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

    def test_default_delay_0_2_between_items(self):
        """Default delay of 0.2s pauses between successive item requests."""
        sleep_calls: list[float] = []
        with patch.object(swb, "_sleep", side_effect=sleep_calls.append):
            with patch.object(
                swb, "fetch_article_html", return_value=self.MULTI_ITEM_HTML
            ):
                with patch.object(
                    swb, "download_image",
                    return_value=(swb.Format.JPEG, 1024),
                ):
                    code, _, _ = self._run_main([])

        self.assertEqual(code, 0)
        # Two items -> one inter-request pause at the default delay.
        self.assertEqual(sleep_calls, [0.2])

    def test_explicit_delay_applied_between_items(self):
        """The --delay value is used for the inter-request pause."""
        sleep_calls: list[float] = []
        with patch.object(swb, "_sleep", side_effect=sleep_calls.append):
            with patch.object(
                swb, "fetch_article_html", return_value=self.MULTI_ITEM_HTML
            ):
                with patch.object(
                    swb, "download_image",
                    return_value=(swb.Format.JPEG, 1024),
                ):
                    code, _, _ = self._run_main(["--delay", "1.25"])

        self.assertEqual(code, 0)
        self.assertEqual(sleep_calls, [1.25])

    def test_delay_applied_after_failed_item(self):
        """The pause still applies when the preceding item failed."""
        sleep_calls: list[float] = []

        def side_effect(url, dest_dir, **kwargs):  # pylint: disable=unused-argument
            raise RuntimeError("simulated failure")

        with patch.object(swb, "_sleep", side_effect=sleep_calls.append):
            with patch.object(
                swb, "fetch_article_html", return_value=self.MULTI_ITEM_HTML
            ):
                with patch.object(swb, "download_image", side_effect=side_effect):
                    code, _, _ = self._run_main(["--delay", "0.75"])

        self.assertEqual(code, 1)
        # Both items failed; the pause between them still happened once.
        self.assertEqual(sleep_calls, [0.75])

    def test_blank_delay_rejected_with_usage_error(self):
        """Blank --delay value exits 2 before any download starts."""
        with patch.object(swb, "fetch_article_html") as mock_fetch:
            code, _, stderr = self._run_main(["--delay", ""])

        self.assertEqual(code, 2)
        self.assertIn("error", stderr.lower())
        mock_fetch.assert_not_called()

    def test_negative_delay_rejected_with_usage_error(self):
        """Negative --delay value exits 2 before any download starts."""
        with patch.object(swb, "fetch_article_html") as mock_fetch:
            code, _, stderr = self._run_main(["--delay", "-1"])

        self.assertEqual(code, 2)
        self.assertIn("error", stderr.lower())
        mock_fetch.assert_not_called()

    def test_non_numeric_delay_rejected_with_usage_error(self):
        """Non-numeric --delay value exits 2."""
        code, _, stderr = self._run_main(["--delay", "abc"])

        self.assertEqual(code, 2)
        self.assertIn("error", stderr.lower())


if __name__ == "__main__":
    unittest.main()
