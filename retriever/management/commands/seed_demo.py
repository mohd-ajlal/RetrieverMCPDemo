from __future__ import annotations

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import Application

from organizations.models import Organization, OrganizationMembership, UserProfile
from retriever.models import DeploymentOrder, Device, ReturnOrder

User = get_user_model()

DEMO_PASSWORD = "DemoPassword123!"
CLAUDE_REDIRECT_URIS = "\n".join(
    [
        "https://claude.ai/api/mcp/auth_callback",
        "https://claude.com/api/mcp/auth_callback",
        "http://localhost/callback",
        "http://127.0.0.1/callback",
    ]
)


class Command(BaseCommand):
    help = "Seed demo users, organizations, devices, orders, and Claude OAuth client."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="demo_user",
            defaults={"email": "demo@retriever.example"},
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        self.stdout.write(f"User demo_user ({'created' if created else 'updated'})")

        org, _ = Organization.objects.get_or_create(name="Retriever Demo Organization")
        OrganizationMembership.objects.get_or_create(
            user=user,
            organization=org,
            defaults={"role": OrganizationMembership.Role.OWNER},
        )
        # Second org for tenant isolation demos
        other, _ = Organization.objects.get_or_create(name="Other Organization")
        OrganizationMembership.objects.get_or_create(
            user=user,
            organization=other,
            defaults={"role": OrganizationMembership.Role.MEMBER},
        )

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.active_organization = org
        profile.save(update_fields=["active_organization"])

        devices = [
            ("MacBook Pro", "MBP-001", "laptop"),
            ("Dell Latitude", "DLL-002", "laptop"),
            ("ThinkPad", "TP-003", "laptop"),
        ]
        device_objs = []
        for name, serial, dtype in devices:
            d, _ = Device.objects.get_or_create(
                organization=org,
                serial_number=serial,
                defaults={"name": name, "device_type": dtype, "status": "available"},
            )
            device_objs.append(d)

        DeploymentOrder.objects.get_or_create(
            organization=org,
            reference="DEP-0001",
            defaults={
                "device": device_objs[0],
                "status": DeploymentOrder.Status.PENDING,
                "notes": "sample deployment",
            },
        )
        ReturnOrder.objects.get_or_create(
            organization=org,
            reference="RET-0001",
            defaults={
                "device": device_objs[1],
                "status": ReturnOrder.Status.PENDING,
                "notes": "sample return",
            },
        )

        # Devices in other org (must never leak via MCP for demo_user's consent org)
        Device.objects.get_or_create(
            organization=other,
            serial_number="OTHER-999",
            defaults={"name": "Secret Other Device", "device_type": "laptop"},
        )

        app = Application.objects.filter(name="Claude Retriever Demo").first()
        raw_secret = None
        if app is None:
            raw_secret = generate_client_secret()
            app = Application(
                name="Claude Retriever Demo",
                client_id=generate_client_id(),
                client_secret=raw_secret,
                client_type=Application.CLIENT_CONFIDENTIAL,
                authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
                redirect_uris=CLAUDE_REDIRECT_URIS,
                hash_client_secret=True,
                skip_authorization=False,
            )
            app.save()
            self.stdout.write(self.style.SUCCESS("Created OAuth client: Claude Retriever Demo"))
        else:
            self.stdout.write("OAuth client Claude Retriever Demo already exists")
            self.stdout.write(
                self.style.WARNING(
                    "Client secret is hashed and cannot be re-displayed. "
                    "Delete the Application in admin and re-run seed_demo to rotate."
                )
            )

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("=== Demo credentials ==="))
        self.stdout.write(f"Username: demo_user")
        self.stdout.write(f"Password: {DEMO_PASSWORD}")
        self.stdout.write(f"Organization: {org.name}")
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("=== Claude OAuth client ==="))
        self.stdout.write(f"Client ID: {app.client_id}")
        if raw_secret:
            self.stdout.write(f"Client Secret: {raw_secret}")
            self.stdout.write(
                self.style.WARNING("Store this secret now — it will not be shown again.")
            )
        self.stdout.write("Redirect URI: https://claude.ai/api/mcp/auth_callback")
        self.stdout.write("MCP URL: set PUBLIC_BASE_URL then use {PUBLIC_BASE_URL}/mcp")
