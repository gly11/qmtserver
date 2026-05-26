from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_returns_connection_clock_version_and_sample(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get("/v1/diagnostics")

        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("qmt", body["data"])
        self.assertIn("clock", body["data"])
        self.assertIn("version", body["data"])
        self.assertIn("sample", body["data"])
        self.assertEqual(body["data"]["sample"]["symbol"], "000001.SZ")


if __name__ == "__main__":
    unittest.main()
