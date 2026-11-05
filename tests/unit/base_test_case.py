"""Shared base test cases for unit tests."""

import tempfile
from pathlib import Path
from unittest import TestCase

from tests.unit.stub_server import StubServer


class ServerTestCase(TestCase):
    """Base case that starts a :class:`StubServer` and provides a temp output dir.

    Subclasses inherit:
      - ``self.server`` — a running :class:`StubServer` (started in setUpClass,
        stopped in tearDownClass);
      - ``self.output_dir`` — a fresh <Temp>/StarWarsBackground directory created
        per test and cleaned up automatically.
    """

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
