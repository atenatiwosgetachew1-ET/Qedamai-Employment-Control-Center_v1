from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    company_dashboard,
    csrf_token_view,
    customer_portal_consume_reset_token_view,
    customer_portal_bootstrap_login_view,
    customer_portal_validate_reset_token_view,
    login_view,
    logout_view,
    me_view,
    public_sync_key_view,
    rotate_sync_key_view,
    retry_due_sync_jobs_view,
    retry_sync_job_view,
    sync_jobs_view,
    sync_keys_view,
    ManagedLicenseEventViewSet,
    ManagedOrganizationViewSet,
    ManagedPlanViewSet,
    ManagedSubscriptionViewSet,
)

router = DefaultRouter()
router.register("organizations", ManagedOrganizationViewSet, basename="managed-organization")
router.register("plans", ManagedPlanViewSet, basename="managed-plan")
router.register("subscriptions", ManagedSubscriptionViewSet, basename="managed-subscription")
router.register("license-events", ManagedLicenseEventViewSet, basename="managed-license-event")

urlpatterns = [
    path("csrf/", csrf_token_view, name="company-csrf"),
    path(
        "customer-portals/bootstrap-login/",
        customer_portal_bootstrap_login_view,
        name="company-customer-portal-bootstrap-login",
    ),
    path(
        "customer-portals/password-reset-tokens/validate/",
        customer_portal_validate_reset_token_view,
        name="company-customer-portal-validate-reset-token",
    ),
    path(
        "customer-portals/password-reset-tokens/consume/",
        customer_portal_consume_reset_token_view,
        name="company-customer-portal-consume-reset-token",
    ),
    path("sync-keys/<str:key_id>/public/", public_sync_key_view, name="company-sync-key-public"),
    path("sync-keys/", sync_keys_view, name="company-sync-keys"),
    path("sync-keys/rotate/", rotate_sync_key_view, name="company-sync-key-rotate"),
    path("sync-jobs/", sync_jobs_view, name="company-sync-jobs"),
    path("sync-jobs/retry-due/", retry_due_sync_jobs_view, name="company-sync-jobs-retry-due"),
    path("sync-jobs/<int:job_id>/retry/", retry_sync_job_view, name="company-sync-job-retry"),
    path("login/", login_view, name="company-login"),
    path("logout/", logout_view, name="company-logout"),
    path("me/", me_view, name="company-me"),
    path("dashboard/", company_dashboard, name="company-dashboard"),
    path("", include(router.urls)),
]
