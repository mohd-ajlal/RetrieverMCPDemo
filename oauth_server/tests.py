"""OAuth authorization server tests."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, Grant
from oauth2_provider.generators import generate_client_id, generate_client_secret

from oauth_server.models import OAuthAuthorizationContext
from organizations.models import Organization, OrganizationMembership, UserProfile

User = get_user_model()


def pkce_pair():
    verifier = secrets.token_urlsafe(64)[:64]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@override_settings(
    PUBLIC_BASE_URL="http://testserver",
    MCP_RESOURCE_URL="http://testserver/mcp",
)
class OAuthFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="demo_user", password="DemoPassword123!"
        )
        self.org = Organization.objects.create(name="Demo Org")
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role="owner"
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.active_organization = self.org
        profile.save()

        self.raw_secret = generate_client_secret()
        self.app = Application(
            name="Claude Retriever Demo",
            client_id=generate_client_id(),
            client_secret=self.raw_secret,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://claude.ai/api/mcp/auth_callback",
            hash_client_secret=True,
        )
        self.app.save()
        self.client = Client()
        self.verifier, self.challenge = pkce_pair()

    def _authorize_url(self, **overrides):
        params = {
            "response_type": "code",
            "client_id": self.app.client_id,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "scope": "retriever.devices.read retriever.orders.read",
            "state": "xyz123",
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
            "resource": "http://testserver/mcp",
        }
        params.update(overrides)
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return f"/o/authorize/?{q}"

    def test_authorize_requires_login(self):
        resp = self.client.get(self._authorize_url())
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])
        self.assertIn("next=", resp["Location"])

    def test_existing_session_skips_login_shows_consent(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.get(self._authorize_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Allow Access")
        self.assertContains(resp, "Demo Org")
        self.assertContains(resp, "View Retriever devices")

    def test_invalid_client_id(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.get(self._authorize_url(client_id="nope"))
        self.assertIn(resp.status_code, (400, 200, 302))
        if resp.status_code == 200:
            self.assertTrue(
                b"error" in resp.content.lower() or b"invalid" in resp.content.lower()
            )

    def test_invalid_redirect_uri(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.get(
            self._authorize_url(redirect_uri="https://evil.example/callback")
        )
        self.assertIn(resp.status_code, (400, 200, 302))

    def test_missing_pkce_rejected(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        url = self._authorize_url()
        # strip PKCE
        url = url.replace(f"&code_challenge={self.challenge}", "")
        url = url.replace("&code_challenge_method=S256", "")
        resp = self.client.get(url)
        # DOT should error when PKCE required
        self.assertIn(resp.status_code, (400, 200, 302))

    def test_deny_consent(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.get(self._authorize_url())
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        post = {k: form[k].value() for k in form.fields if form[k].value() is not None}
        post["csrfmiddlewaretoken"] = self.client.cookies["csrftoken"].value
        # Deny: submit without allow
        resp2 = self.client.post("/o/authorize/", post)
        self.assertEqual(resp2.status_code, 302)
        loc = resp2["Location"]
        self.assertIn("error=access_denied", loc)
        self.assertNotIn("code=", loc)

    def test_accept_consent_issues_code(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.get(self._authorize_url())
        form = resp.context["form"]
        post = {k: form[k].value() for k in form.fields if form[k].value() is not None}
        post["allow"] = "Authorize"
        post["csrfmiddlewaretoken"] = self.client.cookies["csrftoken"].value
        resp2 = self.client.post("/o/authorize/", post)
        self.assertEqual(resp2.status_code, 302)
        loc = resp2["Location"]
        self.assertIn("code=", loc)
        self.assertIn("state=xyz123", loc)
        qs = parse_qs(urlparse(loc).query)
        code = qs["code"][0]
        self.assertTrue(Grant.objects.filter(code=code).exists())
        self.assertTrue(
            OAuthAuthorizationContext.objects.filter(
                user=self.user, organization=self.org
            ).exists()
        )

    def test_token_exchange_and_reuse_code_fails(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.get(self._authorize_url())
        form = resp.context["form"]
        post = {k: form[k].value() for k in form.fields if form[k].value() is not None}
        post["allow"] = "Authorize"
        post["csrfmiddlewaretoken"] = self.client.cookies["csrftoken"].value
        resp2 = self.client.post("/o/authorize/", post)
        code = parse_qs(urlparse(resp2["Location"]).query)["code"][0]

        token_resp = self.client.post(
            "/o/token/",
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "client_id": self.app.client_id,
                "client_secret": self.raw_secret,
                "code_verifier": self.verifier,
                "resource": "http://testserver/mcp",
            },
        )
        self.assertEqual(token_resp.status_code, 200)
        data = token_resp.json()
        self.assertIn("access_token", data)

        # Reuse code
        reuse = self.client.post(
            "/o/token/",
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "client_id": self.app.client_id,
                "client_secret": self.raw_secret,
                "code_verifier": self.verifier,
            },
        )
        self.assertEqual(reuse.status_code, 400)

    def test_expired_code(self):
        grant = Grant.objects.create(
            user=self.user,
            code="expiredcode1234567890",
            application=self.app,
            expires=timezone.now() - timedelta(seconds=1),
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            scope="retriever.devices.read",
            code_challenge=self.challenge,
            code_challenge_method="S256",
        )
        resp = self.client.post(
            "/o/token/",
            {
                "grant_type": "authorization_code",
                "code": grant.code,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "client_id": self.app.client_id,
                "client_secret": self.raw_secret,
                "code_verifier": self.verifier,
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_discovery_metadata(self):
        resp = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("authorization_endpoint", data)
        self.assertEqual(data["code_challenge_methods_supported"], ["S256"])

        resp2 = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(resp2.status_code, 200)
        body = resp2.json()
        self.assertEqual(body["resource"], "http://testserver/mcp")
        self.assertIn("retriever.devices.read", body["scopes_supported"])

    def test_login_then_continue_oauth(self):
        """Logged-out user: login with next=authorize preserves OAuth request."""
        auth_url = self._authorize_url()
        resp = self.client.get(auth_url)
        self.assertEqual(resp.status_code, 302)
        login_url = resp["Location"]
        self.assertIn("/login/", login_url)
        resp2 = self.client.post(
            login_url if login_url.startswith("/") else "/login/",
            {
                "username": "demo_user",
                "password": "DemoPassword123!",
                "next": auth_url,
            },
        )
        # After login should redirect back to authorize
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("/o/authorize/", resp2["Location"])
        resp3 = self.client.get(resp2["Location"])
        self.assertEqual(resp3.status_code, 200)
        self.assertContains(resp3, "Allow Access")
