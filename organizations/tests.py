"""Organization tenancy tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership, UserProfile

User = get_user_model()


class OrganizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass12345!")
        self.org_a = Organization.objects.create(name="A")
        self.org_b = Organization.objects.create(name="B")
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org_a, role="owner"
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org_b, role="member"
        )

    def test_active_org_defaults(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        org = profile.ensure_active_organization()
        self.assertIsNotNone(org)
        self.assertIn(org.id, {self.org_a.id, self.org_b.id})

    def test_switch_org(self):
        self.client.login(username="u1", password="pass12345!")
        resp = self.client.post(
            "/organization/switch/",
            {"organization_id": self.org_b.id, "next": "/organization/"},
        )
        self.assertEqual(resp.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.active_organization_id, self.org_b.id)
