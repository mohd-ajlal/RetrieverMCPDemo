"""Web CRUD and tenant isolation for devices/orders."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from organizations.models import Organization, OrganizationMembership, UserProfile
from retriever.models import DeploymentOrder, Device, ReturnOrder
from retriever.services import DeviceService, OrderService

User = get_user_model()


class WebCrudTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="demo_user", password="DemoPassword123!"
        )
        self.org = Organization.objects.create(name="Demo Org")
        self.other = Organization.objects.create(name="Other Org")
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role="owner"
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.active_organization = self.org
        profile.save()
        self.client = Client()
        self.client.login(username="demo_user", password="DemoPassword123!")

    def test_create_device_via_web(self):
        resp = self.client.post(
            "/devices/new/",
            {
                "name": "ThinkPad",
                "device_type": "laptop",
                "serial_number": "SN-1",
                "status": "available",
            },
        )
        self.assertEqual(resp.status_code, 302)
        device = Device.objects.get(name="ThinkPad")
        self.assertEqual(device.organization_id, self.org.id)

    def test_cannot_edit_other_org_device(self):
        other_device = Device.objects.create(
            organization=self.other, name="Secret", serial_number="X"
        )
        resp = self.client.get(f"/devices/{other_device.id}/edit/")
        self.assertEqual(resp.status_code, 404)

    def test_create_and_delete_deployment_order(self):
        device = Device.objects.create(
            organization=self.org, name="Mac", serial_number="A1"
        )
        resp = self.client.post(
            "/orders/deployments/new/",
            {
                "reference": "DEP-100",
                "device": device.id,
                "status": "pending",
                "notes": "ship it",
            },
        )
        self.assertEqual(resp.status_code, 302)
        order = DeploymentOrder.objects.get(reference="DEP-100")
        resp2 = self.client.post(f"/orders/deployments/{order.id}/delete/")
        self.assertEqual(resp2.status_code, 302)
        self.assertFalse(DeploymentOrder.objects.filter(id=order.id).exists())

    def test_return_order_crud(self):
        resp = self.client.post(
            "/orders/returns/new/",
            {
                "reference": "RET-1",
                "status": "pending",
                "notes": "",
                "device": "",
            },
        )
        self.assertEqual(resp.status_code, 302)
        order = ReturnOrder.objects.get(reference="RET-1")
        resp2 = self.client.post(
            f"/orders/returns/{order.id}/edit/",
            {
                "reference": "RET-1",
                "status": "received",
                "notes": "received",
                "device": "",
            },
        )
        self.assertEqual(resp2.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "received")

    def test_service_tenant_isolation_delete(self):
        other_device = Device.objects.create(
            organization=self.other, name="Other Laptop"
        )
        with self.assertRaises(Exception):
            DeviceService.delete_device(self.org.id, other_device.id)
        self.assertTrue(Device.objects.filter(id=other_device.id).exists())

    def test_service_rejects_cross_org_device_on_order(self):
        other_device = Device.objects.create(
            organization=self.other, name="Other Laptop"
        )
        with self.assertRaises(Exception):
            OrderService.create_deployment_order(
                self.org.id,
                reference="DEP-BAD",
                device_id=other_device.id,
            )
