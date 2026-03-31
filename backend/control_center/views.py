from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    CompanySyncKey,
    ManagedLicenseEvent,
    ManagedOrganization,
    ManagedPlan,
    ManagedSubscription,
    SyncDeliveryJob,
)
from .permissions import IsCompanyOperator
from .serializers import (
    BootstrapOrganizationSerializer,
    CompanyUserSerializer,
    CompanySyncKeyAdminSerializer,
    CompanySyncKeyPublicSerializer,
    ManagedLicenseEventSerializer,
    ManagedOrganizationSerializer,
    ManagedPlanSerializer,
    ManagedSubscriptionSerializer,
    OrganizationPasswordResetTokenSerializer,
    SyncDeliveryJobSerializer,
)
from .services import apply_subscription_change, record_license_event
from .services import (
    consume_superadmin_password_reset_token,
    ensure_active_sync_key,
    issue_superadmin_password_reset,
    rotate_sync_key,
    retry_due_sync_jobs,
    retry_sync_job,
    sync_organization_to_customer_portal,
    sync_plan_to_customer_portal,
    sync_subscription_to_customer_portal,
    validate_superadmin_password_reset_token,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token_view(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["GET"])
@permission_classes([AllowAny])
def public_sync_key_view(request, key_id):
    try:
        key = CompanySyncKey.objects.get(key_id=key_id, is_active=True)
    except CompanySyncKey.DoesNotExist:
        return Response({"detail": "Sync key not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(CompanySyncKeyPublicSerializer(key).data)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def customer_portal_bootstrap_login_view(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    if not username or not password:
        return Response(
            {
                "success": False,
                "message": "Username and password are required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    matches = list(
        ManagedOrganization.objects.select_related("subscription", "subscription__plan")
        .filter(superadmin_username=username)
        .exclude(superadmin_password_hash="")
    )
    for organization in matches:
        if organization.check_superadmin_password(password):
            return Response(
                {
                    "success": True,
                    "organization": BootstrapOrganizationSerializer(organization).data,
                }
            )

    return Response(
        {
            "success": False,
            "message": "Invalid bootstrap credentials.",
        },
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def customer_portal_validate_reset_token_view(request):
    raw_token = (request.data.get("token") or "").strip()
    if not raw_token:
        return Response(
            {"success": False, "message": "Reset token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    token, error_message = validate_superadmin_password_reset_token(raw_token)
    if not token:
        return Response(
            {"success": False, "message": error_message},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(
        {
            "success": True,
            "organization": BootstrapOrganizationSerializer(token.organization).data,
            "expires_at": token.expires_at,
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def customer_portal_consume_reset_token_view(request):
    raw_token = (request.data.get("token") or "").strip()
    new_password = request.data.get("new_password") or ""
    if not raw_token or not new_password.strip():
        return Response(
            {"success": False, "message": "Reset token and new password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    organization, error_message = consume_superadmin_password_reset_token(
        raw_token=raw_token,
        new_password=new_password,
    )
    if not organization:
        return Response(
            {"success": False, "message": error_message},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {
            "success": True,
            "organization": BootstrapOrganizationSerializer(organization).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def sync_keys_view(request):
    ensure_active_sync_key()
    keys = CompanySyncKey.objects.all()
    return Response(CompanySyncKeyAdminSerializer(keys, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def rotate_sync_key_view(request):
    key = rotate_sync_key()
    return Response(
        {
            "success": True,
            "key": CompanySyncKeyAdminSerializer(key).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def sync_jobs_view(request):
    jobs = SyncDeliveryJob.objects.all()[:100]
    return Response(SyncDeliveryJobSerializer(jobs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def retry_sync_job_view(request, job_id):
    try:
        job = SyncDeliveryJob.objects.get(pk=job_id)
    except SyncDeliveryJob.DoesNotExist:
        return Response({"detail": "Sync job not found."}, status=status.HTTP_404_NOT_FOUND)
    ok, error_message = retry_sync_job(job)
    return Response(
        {
            "success": ok,
            "job": SyncDeliveryJobSerializer(job).data,
            "error": error_message,
        },
        status=status.HTTP_200_OK if ok else status.HTTP_409_CONFLICT,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def retry_due_sync_jobs_view(request):
    processed = retry_due_sync_jobs()
    return Response({"success": True, "processed": processed})


@csrf_protect
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    user = authenticate(username=username, password=password)
    if not user or not (user.is_staff or user.is_superuser):
        return Response(
            {"success": False, "message": "Invalid company operator credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    login(request, user)
    return Response(
        {
            "success": True,
            "user": CompanyUserSerializer(user).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def logout_view(request):
    logout(request)
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def me_view(request):
    return Response(CompanyUserSerializer(request.user).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCompanyOperator])
def company_dashboard(request):
    return Response(
        {
            "name": "Employment Portal Company Control Center",
            "organizations": ManagedOrganization.objects.count(),
            "plans": ManagedPlan.objects.count(),
            "subscriptions": ManagedSubscription.objects.count(),
            "active_subscriptions": ManagedSubscription.objects.filter(status="active").count(),
            "grace_subscriptions": ManagedSubscription.objects.filter(status="grace").count(),
            "suspended_subscriptions": ManagedSubscription.objects.filter(status="suspended").count(),
            "recent_events": ManagedLicenseEventSerializer(
                ManagedLicenseEvent.objects.select_related("organization", "subscription")[:10],
                many=True,
            ).data,
        }
    )


class ManagedOrganizationViewSet(viewsets.ModelViewSet):
    queryset = ManagedOrganization.objects.all()
    serializer_class = ManagedOrganizationSerializer
    permission_classes = [IsAuthenticated, IsCompanyOperator]

    def perform_create(self, serializer):
        superadmin_password = serializer.validated_data.get("superadmin_password", "")
        organization = serializer.save()
        record_license_event(
            organization=organization,
            actor_username=self.request.user.username,
            action="organization.created",
            new_status=organization.status,
            notes="Organization created from company control center.",
        )
        sync_organization_to_customer_portal(
            organization,
            superadmin_password=superadmin_password,
        )

    def perform_update(self, serializer):
        superadmin_password = serializer.validated_data.get("superadmin_password", "")
        original = self.get_object()
        old_status = original.status
        organization = serializer.save()
        record_license_event(
            organization=organization,
            actor_username=self.request.user.username,
            action="organization.updated",
            old_status=old_status,
            new_status=organization.status,
            notes="Organization updated from company control center.",
        )
        sync_organization_to_customer_portal(
            organization,
            superadmin_password=superadmin_password,
        )

    @action(detail=True, methods=["post"], url_path="reset-superadmin-password")
    def reset_superadmin_password(self, request, pk=None):
        organization = self.get_object()
        new_password = request.data.get("new_password") or ""
        if not new_password.strip():
            return Response(
                {
                    "success": False,
                    "message": "A new password is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not organization.superadmin_username:
            return Response(
                {
                    "success": False,
                    "message": "This organization does not have a superadmin username configured.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        organization.set_superadmin_password(new_password)
        organization.save(update_fields=["superadmin_password_hash", "updated_at"])
        record_license_event(
            organization=organization,
            actor_username=self.request.user.username,
            action="organization.superadmin_password_reset",
            new_status=organization.status,
            notes="Organization superadmin password reset from company control center.",
        )
        sync_organization_to_customer_portal(
            organization,
            superadmin_password=new_password,
        )
        return Response(
            {
                "success": True,
                "organization": ManagedOrganizationSerializer(organization).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="request-superadmin-password-reset")
    def request_superadmin_password_reset(self, request, pk=None):
        organization = self.get_object()
        token, reset_url, email_sent, delivery_error = issue_superadmin_password_reset(
            organization=organization,
            actor_username=self.request.user.username,
        )
        if not token:
            return Response(
                {
                    "success": False,
                    "message": delivery_error,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "success": True,
                "organization": ManagedOrganizationSerializer(organization).data,
                "reset_token": OrganizationPasswordResetTokenSerializer(token).data,
                "reset_url": reset_url,
                "email_sent": email_sent,
                "delivery_error": delivery_error,
            }
        )


class ManagedPlanViewSet(viewsets.ModelViewSet):
    queryset = ManagedPlan.objects.all()
    serializer_class = ManagedPlanSerializer
    permission_classes = [IsAuthenticated, IsCompanyOperator]

    def perform_create(self, serializer):
        plan = serializer.save()
        sync_plan_to_customer_portal(plan)

    def perform_update(self, serializer):
        plan = serializer.save()
        sync_plan_to_customer_portal(plan)


class ManagedSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = ManagedSubscription.objects.select_related("organization", "plan").all()
    serializer_class = ManagedSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsCompanyOperator]

    def perform_create(self, serializer):
        subscription = serializer.save()
        apply_subscription_change(
            subscription=subscription,
            actor_username=self.request.user.username,
            notes="Subscription created from company control center.",
        )
        sync_plan_to_customer_portal(subscription.plan)
        sync_organization_to_customer_portal(subscription.organization)
        sync_subscription_to_customer_portal(subscription)

    def perform_update(self, serializer):
        subscription = serializer.save()
        apply_subscription_change(
            subscription=subscription,
            actor_username=self.request.user.username,
            notes="Subscription updated from company control center.",
        )
        sync_plan_to_customer_portal(subscription.plan)
        sync_organization_to_customer_portal(subscription.organization)
        sync_subscription_to_customer_portal(subscription)


class ManagedLicenseEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ManagedLicenseEvent.objects.select_related("organization", "subscription").all()
    serializer_class = ManagedLicenseEventSerializer
    permission_classes = [IsAuthenticated, IsCompanyOperator]
