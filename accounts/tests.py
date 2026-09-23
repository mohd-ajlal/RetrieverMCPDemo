"""Authentication and session tests."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from organizations.models import OrganizationMembership, UserProfile

User = get_user_model()


class AuthSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="demo_user", password="DemoPassword123!"
        )
        self.client = Client()

    def test_not_logged_in_redirects_from_dashboard(self):
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_login_success(self):
        resp = self.client.post(
            "/login/",
            {"username": "demo_user", "password": "DemoPassword123!"},
        )
        self.assertEqual(resp.status_code, 302)
        resp2 = self.client.get("/dashboard/")
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "demo_user")

    def test_wrong_password(self):
        resp = self.client.post(
            "/login/",
            {"username": "demo_user", "password": "wrong"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["user"].is_authenticated)

    def test_logout(self):
        self.client.login(username="demo_user", password="DemoPassword123!")
        resp = self.client.post("/logout/")
        self.assertEqual(resp.status_code, 302)
        resp2 = self.client.get("/dashboard/")
        self.assertEqual(resp2.status_code, 302)

    def test_login_page_links_to_signup(self):
        resp = self.client.get("/login/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "/signup/")


class SignupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.payload = {
            "username": "new_user",
            "email": "new@example.com",
            "organization_name": "New Corp",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        }

    def test_signup_creates_user_org_and_membership(self):
        resp = self.client.post("/signup/", self.payload)
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="new_user")
        self.assertEqual(user.email, "new@example.com")
        membership = OrganizationMembership.objects.get(user=user)
        self.assertEqual(membership.organization.name, "New Corp")
        self.assertEqual(membership.role, OrganizationMembership.Role.OWNER)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.active_organization_id, membership.organization_id)

    def test_signup_then_dashboard(self):
        self.client.post("/signup/", self.payload)
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "new_user")
        self.assertContains(resp, "New Corp")

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username="new_user", password="OtherPass123!")
        resp = self.client.post("/signup/", self.payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["user"].is_authenticated)
        self.assertContains(resp, "already exists")

    def test_login_works_for_signed_up_user(self):
        self.client.post("/signup/", self.payload)
        self.client.logout()
        resp = self.client.post(
            "/login/",
            {"username": "new_user", "password": "SecurePass123!"},
        )
        self.assertEqual(resp.status_code, 302)
        resp2 = self.client.get("/dashboard/")
        self.assertEqual(resp2.status_code, 200)

    def test_signup_preserves_next_for_oauth(self):
        next_url = "/o/authorize/?client_id=abc&state=xyz"
        resp = self.client.post(
            f"/signup/?next={next_url}",
            {**self.payload, "next": next_url},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/o/authorize/", resp["Location"])
