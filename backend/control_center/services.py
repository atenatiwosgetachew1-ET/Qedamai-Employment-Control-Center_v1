import uuid
from datetime import timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from urllib.parse import urlencode

from .models import (
    CompanySyncKey,
    ManagedLicenseEvent,
    ManagedOrganization,
    ManagedPlan,
    ManagedSubscription,
    OrganizationPasswordResetToken,
    SyncDeliveryJob,
)
from .portal_sync import post_sync, sync_is_configured


def record_license_event(*, organization, subscription=None, actor_username="", action="", old_status="", new_status="", notes=""):
    return ManagedLicenseEvent.objects.create(
        organization=organization,
        subscription=subscription,
        actor_username=actor_username or "",
        action=action,
        old_status=old_status or "",
        new_status=new_status or "",
        notes=notes or "",
    )


def sync_organization_from_subscription(subscription: ManagedSubscription):
    organization = subscription.organization
    if subscription.status == ManagedSubscription.STATUS_CANCELLED:
        organization.status = ManagedOrganization.STATUS_CANCELLED
        organization.read_only_mode = True
    elif subscription.status == ManagedSubscription.STATUS_SUSPENDED:
        organization.status = ManagedOrganization.STATUS_SUSPENDED
    elif subscription.status == ManagedSubscription.STATUS_GRACE:
        organization.status = ManagedOrganization.STATUS_GRACE
    elif subscription.status in {ManagedSubscription.STATUS_ACTIVE, ManagedSubscription.STATUS_TRIAL}:
        organization.status = ManagedOrganization.STATUS_ACTIVE
        organization.read_only_mode = False
    elif subscription.status == ManagedSubscription.STATUS_EXPIRED:
        organization.status = ManagedOrganization.STATUS_SUSPENDED
    organization.save(update_fields=["status", "read_only_mode", "updated_at"])


def apply_subscription_change(*, subscription: ManagedSubscription, actor_username: str, notes: str = ""):
    old_status = ""
    if subscription.pk:
        old_status = (
            ManagedSubscription.objects.filter(pk=subscription.pk)
            .values_list("status", flat=True)
            .first()
            or ""
        )
    if subscription.status == ManagedSubscription.STATUS_CANCELLED and not subscription.cancelled_at:
        subscription.cancelled_at = timezone.now()
    subscription.save()
    sync_organization_from_subscription(subscription)
    record_license_event(
        organization=subscription.organization,
        subscription=subscription,
        actor_username=actor_username,
        action="subscription.updated",
        old_status=old_status,
        new_status=subscription.status,
        notes=notes,
    )


def ensure_active_sync_key() -> CompanySyncKey:
    existing = CompanySyncKey.objects.filter(is_active=True).order_by("-updated_at", "-created_at").first()
    if existing:
        return existing

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return CompanySyncKey.objects.create(
        key_id=f"company-sync-{uuid.uuid4().hex[:16]}",
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        is_active=True,
    )


def rotate_sync_key() -> CompanySyncKey:
    CompanySyncKey.objects.filter(is_active=True).update(is_active=False)
    return ensure_active_sync_key()


def _update_sync_status(instance, *, ok: bool, error_message: str):
    instance.last_synced_at = timezone.now() if ok else instance.last_synced_at
    instance.last_sync_error = "" if ok else error_message
    instance.save(update_fields=["last_synced_at", "last_sync_error", "updated_at"])


def _clear_sync_error(instance):
    if instance.last_sync_error:
        instance.last_sync_error = ""
        instance.save(update_fields=["last_sync_error", "updated_at"])


def _organization_sync_base_url(organization: ManagedOrganization) -> str:
    return (organization.portal_api_base_url or "").strip()


def _plan_sync_base_urls(plan: ManagedPlan) -> list[str]:
    urls = []
    seen = set()
    for base_url in (
        ManagedOrganization.objects.exclude(portal_api_base_url="")
        .values_list("portal_api_base_url", flat=True)
        .distinct()
    ):
        normalized = (base_url or "").strip().rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            urls.append(normalized)
    if urls:
        return urls
    return []


def _deliver_sync_job(job: SyncDeliveryJob) -> tuple[bool, str]:
    sync_key = ensure_active_sync_key()
    ok, error_message = post_sync(
        job.endpoint,
        job.payload,
        key_id=sync_key.key_id,
        private_key_pem=sync_key.private_key_pem,
        base_url=job.base_url,
    )
    job.attempts += 1
    job.last_attempted_at = timezone.now()
    if ok:
        job.status = SyncDeliveryJob.STATUS_SUCCEEDED
        job.last_error = ""
        job.last_succeeded_at = timezone.now()
        job.next_retry_at = None
    else:
        job.status = SyncDeliveryJob.STATUS_FAILED
        job.last_error = error_message
        delay_minutes = min(60, 5 * max(1, job.attempts))
        job.next_retry_at = timezone.now() + timedelta(minutes=delay_minutes)
    job.save()
    return ok, error_message


def enqueue_sync_job(*, target_type: str, target_id: int, base_url: str, endpoint: str, payload: dict) -> SyncDeliveryJob:
    return SyncDeliveryJob.objects.create(
        target_type=target_type,
        target_id=target_id,
        base_url=base_url,
        endpoint=endpoint,
        payload=payload,
        status=SyncDeliveryJob.STATUS_PENDING,
    )


def retry_sync_job(job: SyncDeliveryJob) -> tuple[bool, str]:
    return _deliver_sync_job(job)


def retry_due_sync_jobs(limit: int = 25) -> int:
    now = timezone.now()
    jobs = (
        SyncDeliveryJob.objects.filter(status=SyncDeliveryJob.STATUS_FAILED, next_retry_at__lte=now)
        .order_by("next_retry_at")[:limit]
    )
    processed = 0
    for job in jobs:
        _deliver_sync_job(job)
        processed += 1
    return processed


def build_superadmin_reset_url(organization: ManagedOrganization, token: str) -> str:
    base_url = (organization.portal_base_url or "").rstrip("/")
    reset_path = getattr(settings, "ORGANIZATION_PORTAL_RESET_PATH", "/reset-password")
    query = urlencode({"token": token})
    return f"{base_url}{reset_path}?{query}"


def issue_superadmin_password_reset(*, organization: ManagedOrganization, actor_username: str):
    if not organization.superadmin_username:
        return None, "", False, "This organization does not have a superadmin username configured."
    if not organization.superadmin_email:
        return None, "", False, "This organization does not have a superadmin email configured."
    if not organization.portal_base_url:
        return None, "", False, "This organization does not have a portal base URL configured."

    now = timezone.now()
    OrganizationPasswordResetToken.objects.filter(
        organization=organization,
        used_at__isnull=True,
        expires_at__gt=now,
    ).delete()
    token = OrganizationPasswordResetToken.objects.create(
        organization=organization,
        token=uuid.uuid4().hex,
        delivery_email=organization.superadmin_email,
        created_by_username=actor_username,
        expires_at=now + timedelta(minutes=getattr(settings, "SUPERADMIN_RESET_TOKEN_TTL_MINUTES", 60)),
    )
    reset_url = build_superadmin_reset_url(organization, token.token)

    email_sent = False
    delivery_error = ""
    try:
        sent_count = send_mail(
            subject=f"Reset your {organization.name} portal password",
            message=(
                f"Hello {organization.superadmin_username},\n\n"
                f"Use the link below to reset your password:\n{reset_url}\n\n"
                f"This link expires at {token.expires_at.isoformat()}."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
            recipient_list=[organization.superadmin_email],
            fail_silently=False,
        )
        email_sent = sent_count > 0
        token.email_sent_at = timezone.now() if email_sent else None
        token.last_delivery_error = "" if email_sent else "Email backend did not confirm delivery."
    except Exception as exc:
        delivery_error = str(exc)
        token.last_delivery_error = delivery_error
    token.save(update_fields=["email_sent_at", "last_delivery_error"])

    record_license_event(
        organization=organization,
        actor_username=actor_username,
        action="organization.superadmin_password_reset_requested",
        new_status=organization.status,
        notes="Organization superadmin password reset link issued from company control center.",
    )
    return token, reset_url, email_sent, delivery_error


def validate_superadmin_password_reset_token(raw_token: str):
    token = (
        OrganizationPasswordResetToken.objects.select_related("organization")
        .filter(token=raw_token)
        .first()
    )
    if not token:
        return None, "Reset token not found."
    if token.used_at:
        return None, "Reset token has already been used."
    if token.expires_at <= timezone.now():
        return None, "Reset token has expired."
    return token, ""


def consume_superadmin_password_reset_token(*, raw_token: str, new_password: str):
    token, error_message = validate_superadmin_password_reset_token(raw_token)
    if not token:
        return None, error_message
    organization = token.organization
    organization.set_superadmin_password(new_password)
    organization.save(update_fields=["superadmin_password_hash", "updated_at"])
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    record_license_event(
        organization=organization,
        actor_username="",
        action="organization.superadmin_password_reset_completed",
        new_status=organization.status,
        notes="Organization superadmin completed a token-based password reset.",
    )
    return organization, ""


def sync_plan_to_customer_portal(plan):
    base_urls = _plan_sync_base_urls(plan)
    if not base_urls and not sync_is_configured():
        _clear_sync_error(plan)
        return True, ""
    payload = {
        "external_id": f"company-plan-{plan.id}",
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "monthly_price": str(plan.monthly_price),
        "currency": plan.currency,
        "max_superadmins": plan.max_superadmins,
        "max_admins": plan.max_admins,
        "max_staff": plan.max_staff,
        "max_customers": plan.max_customers,
        "feature_flags": plan.feature_flags,
        "is_active": plan.is_active,
    }
    if not base_urls:
        base_urls = [""]
    errors = []
    for base_url in base_urls:
        job = enqueue_sync_job(
            target_type=SyncDeliveryJob.TARGET_PLAN,
            target_id=plan.id,
            base_url=base_url,
            endpoint="/api/company-sync/plans/",
            payload=payload,
        )
        ok, error_message = _deliver_sync_job(job)
        if not ok:
            errors.append(error_message)
    ok = not errors
    _update_sync_status(plan, ok=ok, error_message="; ".join(errors))
    return ok, "; ".join(errors)


def sync_organization_to_customer_portal(organization, *, superadmin_password: str = ""):
    base_url = _organization_sync_base_url(organization)
    if not sync_is_configured(base_url):
        _clear_sync_error(organization)
        return True, ""
    payload = {
        "external_id": f"company-organization-{organization.id}",
        "name": organization.name,
        "slug": organization.slug,
        "superadmin_username": organization.superadmin_username,
        "status": organization.status,
        "billing_contact_name": organization.billing_contact_name,
        "billing_contact_email": organization.billing_contact_email,
        "reputation_tier": organization.reputation_tier,
        "read_only_mode": organization.read_only_mode,
    }
    if superadmin_password:
        payload["superadmin_password"] = superadmin_password
    job = enqueue_sync_job(
        target_type=SyncDeliveryJob.TARGET_ORGANIZATION,
        target_id=organization.id,
        base_url=base_url,
        endpoint="/api/company-sync/organizations/",
        payload=payload,
    )
    ok, error_message = _deliver_sync_job(job)
    _update_sync_status(organization, ok=ok, error_message=error_message)
    return ok, error_message


def sync_subscription_to_customer_portal(subscription):
    base_url = _organization_sync_base_url(subscription.organization)
    if not sync_is_configured(base_url):
        _clear_sync_error(subscription)
        return True, ""
    payload = {
        "external_id": f"company-subscription-{subscription.id}",
        "organization_external_id": f"company-organization-{subscription.organization_id}",
        "plan_external_id": f"company-plan-{subscription.plan_id}",
        "status": subscription.status,
        "starts_at": subscription.starts_at.isoformat() if subscription.starts_at else None,
        "renews_at": subscription.renews_at.isoformat() if subscription.renews_at else None,
        "grace_ends_at": subscription.grace_ends_at.isoformat() if subscription.grace_ends_at else None,
        "cancelled_at": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
        "last_payment_status": subscription.last_payment_status,
        "notes": subscription.notes,
    }
    job = enqueue_sync_job(
        target_type=SyncDeliveryJob.TARGET_SUBSCRIPTION,
        target_id=subscription.id,
        base_url=base_url,
        endpoint="/api/company-sync/subscriptions/",
        payload=payload,
    )
    ok, error_message = _deliver_sync_job(job)
    _update_sync_status(subscription, ok=ok, error_message=error_message)
    return ok, error_message
