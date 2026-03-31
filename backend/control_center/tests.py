from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from .models import (
    CompanySyncKey,
    ManagedOrganization,
    ManagedPlan,
    ManagedSubscription,
    OrganizationPasswordResetToken,
    SyncDeliveryJob,
)


class CompanySyncKeyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="company-admin",
            password="strong-pass-123",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_sync_keys_endpoint_bootstraps_active_key(self):
        response = self.client.get("/api/sync-keys/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertTrue(response.data[0]["is_active"])
        self.assertEqual(CompanySyncKey.objects.filter(is_active=True).count(), 1)

    def test_rotate_sync_key_deactivates_previous_key(self):
        self.client.get("/api/sync-keys/")
        first_key = CompanySyncKey.objects.get(is_active=True)

        response = self.client.post("/api/sync-keys/rotate/")
        self.assertEqual(response.status_code, 200)

        first_key.refresh_from_db()
        self.assertFalse(first_key.is_active)
        self.assertEqual(CompanySyncKey.objects.filter(is_active=True).count(), 1)


class SyncDeliveryJobTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="company-admin",
            password="strong-pass-123",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

    @patch("control_center.services.post_sync", return_value=(False, "Network unavailable"))
    def test_failed_plan_sync_creates_retryable_job(self, mocked_post_sync):
        ManagedOrganization.objects.create(
            name="Acme Corp",
            slug="acme-corp",
            portal_api_base_url="http://localhost:8000",
        )
        response = self.client.post(
            "/api/plans/",
            {
                "code": "starter",
                "name": "Starter",
                "monthly_price": "25.00",
                "currency": "USD",
                "max_superadmins": 1,
                "max_admins": 1,
                "max_staff": 8,
                "max_customers": 20,
                "feature_flags": {"audit_log_enabled": True},
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SyncDeliveryJob.objects.count(), 1)
        job = SyncDeliveryJob.objects.first()
        self.assertEqual(job.status, SyncDeliveryJob.STATUS_FAILED)
        self.assertEqual(job.attempts, 1)
        self.assertTrue(job.next_retry_at is not None)
        self.assertEqual(job.base_url, "http://localhost:8000")

    @patch("control_center.services.post_sync", return_value=(True, ""))
    def test_retry_sync_job_endpoint_marks_job_succeeded(self, mocked_post_sync):
        plan = ManagedPlan.objects.create(
            code="starter",
            name="Starter",
            monthly_price="25.00",
        )
        job = SyncDeliveryJob.objects.create(
            target_type=SyncDeliveryJob.TARGET_PLAN,
            target_id=plan.id,
            endpoint="/api/company-sync/plans/",
            payload={"external_id": "company-plan-1", "code": "starter", "name": "Starter"},
            status=SyncDeliveryJob.STATUS_FAILED,
            attempts=1,
            last_error="Previous failure",
        )
        response = self.client.post(f"/api/sync-jobs/{job.id}/retry/")
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, SyncDeliveryJob.STATUS_SUCCEEDED)
        self.assertEqual(job.attempts, 2)


class CustomerPortalBootstrapLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = ManagedOrganization.objects.create(
            name="Acme Corp",
            slug="acme-corp",
            superadmin_username="acme-admin",
            superadmin_email="acme@example.com",
            status=ManagedOrganization.STATUS_ACTIVE,
            read_only_mode=False,
        )
        self.organization.set_superadmin_password("bootstrap-pass-123")
        self.organization.save(update_fields=["superadmin_password_hash", "updated_at"])
        self.plan = ManagedPlan.objects.create(
            code="starter",
            name="Starter",
            monthly_price="25.00",
            max_superadmins=1,
            max_admins=2,
            max_staff=10,
            max_customers=50,
            feature_flags={"audit_log_enabled": True},
        )
        self.subscription = ManagedSubscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            status=ManagedSubscription.STATUS_ACTIVE,
            last_payment_status=ManagedSubscription.PAYMENT_PAID,
        )

    def test_bootstrap_login_returns_organization_payload_for_valid_credentials(self):
        response = self.client.post(
            "/api/customer-portals/bootstrap-login/",
            {
                "username": "acme-admin",
                "password": "bootstrap-pass-123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["organization"]["slug"], "acme-corp")
        self.assertEqual(response.data["organization"]["subscription"]["status"], ManagedSubscription.STATUS_ACTIVE)
        self.assertEqual(response.data["organization"]["subscription"]["plan"]["code"], "starter")

    def test_bootstrap_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/api/customer-portals/bootstrap-login/",
            {
                "username": "acme-admin",
                "password": "wrong-pass",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data["success"])

    def test_creating_organization_hashes_superadmin_password(self):
        user = User.objects.create_user(
            username="company-admin",
            password="strong-pass-123",
            is_staff=True,
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(
            "/api/organizations/",
            {
                "name": "Beta Corp",
                "slug": "beta-corp",
                "superadmin_username": "beta-admin",
                "superadmin_email": "beta@example.com",
                "superadmin_password": "beta-pass-123",
                "status": ManagedOrganization.STATUS_PENDING,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        organization = ManagedOrganization.objects.get(slug="beta-corp")
        self.assertNotEqual(organization.superadmin_password_hash, "")
        self.assertNotEqual(organization.superadmin_password_hash, "beta-pass-123")
        self.assertTrue(organization.check_superadmin_password("beta-pass-123"))


class SuperadminPasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="company-admin",
            password="strong-pass-123",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)
        self.organization = ManagedOrganization.objects.create(
            name="Acme Corp",
            slug="acme-reset",
            portal_api_base_url="http://localhost:8000",
            superadmin_username="acme-admin",
            superadmin_email="acme@example.com",
            portal_base_url="http://localhost:5173",
            status=ManagedOrganization.STATUS_ACTIVE,
        )
        self.organization.set_superadmin_password("old-pass-123")
        self.organization.save(update_fields=["superadmin_password_hash", "updated_at"])

    @patch("control_center.views.sync_organization_to_customer_portal", return_value=(True, ""))
    def test_reset_superadmin_password_updates_hash_and_syncs(self, mocked_sync):
        response = self.client.post(
            f"/api/organizations/{self.organization.id}/reset-superadmin-password/",
            {"new_password": "new-pass-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.organization.refresh_from_db()
        self.assertTrue(self.organization.check_superadmin_password("new-pass-123"))
        mocked_sync.assert_called_once_with(
            self.organization,
            superadmin_password="new-pass-123",
        )

    def test_reset_superadmin_password_requires_superadmin_username(self):
        self.organization.superadmin_username = ""
        self.organization.save(update_fields=["superadmin_username", "updated_at"])
        response = self.client.post(
            f"/api/organizations/{self.organization.id}/reset-superadmin-password/",
            {"new_password": "new-pass-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data["success"])

    @patch("control_center.services.send_mail", return_value=1)
    def test_request_superadmin_password_reset_issues_token_and_reset_url(self, mocked_send_mail):
        response = self.client.post(
            f"/api/organizations/{self.organization.id}/request-superadmin-password-reset/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["email_sent"])
        self.assertIn("token=", response.data["reset_url"])
        self.assertEqual(OrganizationPasswordResetToken.objects.count(), 1)
        token = OrganizationPasswordResetToken.objects.first()
        self.assertEqual(token.delivery_email, "acme@example.com")
        self.assertIsNotNone(token.email_sent_at)
        mocked_send_mail.assert_called_once()

    @patch("control_center.services.send_mail", return_value=1)
    def test_validate_and_consume_token_updates_company_password_hash(self, mocked_send_mail):
        issue_response = self.client.post(
            f"/api/organizations/{self.organization.id}/request-superadmin-password-reset/",
            {},
            format="json",
        )
        self.assertEqual(issue_response.status_code, 200)
        token = OrganizationPasswordResetToken.objects.first()

        validate_response = self.client.post(
            "/api/customer-portals/password-reset-tokens/validate/",
            {"token": token.token},
            format="json",
        )
        self.assertEqual(validate_response.status_code, 200)
        self.assertTrue(validate_response.data["success"])

        consume_response = self.client.post(
            "/api/customer-portals/password-reset-tokens/consume/",
            {"token": token.token, "new_password": "fresh-pass-123"},
            format="json",
        )
        self.assertEqual(consume_response.status_code, 200)
        self.assertTrue(consume_response.data["success"])
        self.organization.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(self.organization.check_superadmin_password("fresh-pass-123"))
        self.assertIsNotNone(token.used_at)
