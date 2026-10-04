import unittest
from unittest import mock

from flask import session

from arma_panel import config, create_app
from arma_panel.security import client_ip


def make_app(behind_proxy):
    with mock.patch.object(config, "PANEL_BEHIND_PROXY", behind_proxy):
        app = create_app()

    @app.get("/_test")
    def probe():
        session["seen"] = True
        return {"ip": client_ip()}

    return app.test_client()


class ClientAddressTest(unittest.TestCase):
    def test_direct_access_ignores_forwarded_headers(self):
        client = make_app(behind_proxy=False)
        response = client.get("/_test", headers={"X-Forwarded-For": "6.6.6.6"},
                              environ_base={"REMOTE_ADDR": "203.0.113.5"})
        self.assertEqual(response.get_json()["ip"], "203.0.113.5")

    def test_behind_proxy_uses_the_address_nginx_added(self):
        # nginx appends the address it saw to whatever the client sent.
        client = make_app(behind_proxy=True)
        response = client.get("/_test", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.5"},
                              environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(response.get_json()["ip"], "203.0.113.5")


class SessionCookieTest(unittest.TestCase):
    def cookie(self, client, **headers):
        return client.get("/_test", headers=headers).headers["Set-Cookie"]

    def test_plain_http(self):
        self.assertNotIn("Secure", self.cookie(make_app(behind_proxy=False)))

    def test_https_through_the_proxy(self):
        client = make_app(behind_proxy=True)
        self.assertIn("Secure", self.cookie(client, **{"X-Forwarded-Proto": "https"}))
        self.assertNotIn("Secure", self.cookie(client, **{"X-Forwarded-Proto": "http"}))

    def test_forwarded_scheme_ignored_without_proxy(self):
        client = make_app(behind_proxy=False)
        self.assertNotIn("Secure", self.cookie(client, **{"X-Forwarded-Proto": "https"}))


if __name__ == "__main__":
    unittest.main()
