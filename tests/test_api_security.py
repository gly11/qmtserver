from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from qmtserver.api import create_app
from qmtserver.config import load_settings
from tests.fakes import FakeService


class ApiSecurityTests(unittest.TestCase):
    def test_health_does_not_require_token(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_protected_routes_require_token_when_configured(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token", transparent_rpc=True),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            status = client.get("/qmt/status")
            methods = client.get("/rpc/methods")
            rpc = client.post(
                "/rpc",
                json={"target": "xtdata", "method": "get_sector_list", "args": [], "kwargs": {}},
            )

        self.assertEqual(status.status_code, 401)
        self.assertEqual(methods.status_code, 401)
        self.assertEqual(rpc.status_code, 401)
        self.assertEqual(status.json()["detail"]["code"], "UNAUTHORIZED")

    def test_protected_routes_accept_valid_bearer_token(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/qmt/status",
                headers={"Authorization": "Bearer dev-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("quote", response.json())

    def test_protected_routes_reject_invalid_bearer_token(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            app.state.qmt_service = FakeService()
            response = client.get(
                "/qmt/status",
                headers={"Authorization": "Bearer wrong-token"},
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
