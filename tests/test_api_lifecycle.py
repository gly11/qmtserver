from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiLifecycleTests(unittest.TestCase):
    def test_qmt_status_and_connect(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            status = client.get("/qmt/status")
            connected = client.post("/qmt/connect")

        self.assertFalse(status.json()["quote"]["connected"])
        self.assertTrue(connected.json()["quote"]["connected"])

    def test_qmt_reconnect_and_disconnect(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            reconnected = client.post("/qmt/reconnect")
            disconnected = client.post("/qmt/disconnect")

        self.assertTrue(reconnected.json()["quote"]["connected"])
        self.assertFalse(disconnected.json()["quote"]["connected"])
        self.assertEqual(disconnected.json()["lifecycle"]["state"], "disconnected")


if __name__ == "__main__":
    unittest.main()
