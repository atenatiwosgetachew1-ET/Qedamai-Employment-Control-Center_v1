from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class ManagedOrganization(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_GRACE = "grace"
    STATUS_SUSPENDED = "suspended"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_GRACE, "Grace"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    REPUTATION_LOW = "low"
    REPUTATION_STANDARD = "standard"
    REPUTATION_TRUSTED = "trusted"

    REPUTATION_CHOICES = [
        (REPUTATION_LOW, "Low"),
        (REPUTATION_STANDARD, "Standard"),
        (REPUTATION_TRUSTED, "Trusted"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    portal_base_url = models.URLField(blank=True, default="")
    portal_api_base_url = models.URLField(blank=True, default="")
    superadmin_username = models.CharField(max_length=150, blank=True, default="")
    superadmin_email = models.EmailField(blank=True, default="")
    superadmin_password_hash = models.CharField(max_length=255, blank=True, default="")
    external_reference = models.CharField(max_length=120, blank=True, default="")
    billing_contact_name = models.CharField(max_length=255, blank=True, default="")
    billing_contact_email = models.EmailField(blank=True, default="")
    reputation_tier = models.CharField(
        max_length=20,
        choices=REPUTATION_CHOICES,
        default=REPUTATION_STANDARD,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    read_only_mode = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def set_superadmin_password(self, raw_password: str):
        self.superadmin_password_hash = make_password(raw_password)

    def check_superadmin_password(self, raw_password: str) -> bool:
        if not self.superadmin_password_hash:
            return False
        return check_password(raw_password, self.superadmin_password_hash)


class ManagedPlan(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    max_superadmins = models.PositiveIntegerField(default=1)
    max_admins = models.PositiveIntegerField(default=1)
    max_staff = models.PositiveIntegerField(default=4)
    max_customers = models.PositiveIntegerField(default=5)
    feature_flags = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ManagedSubscription(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_GRACE = "grace"
    STATUS_SUSPENDED = "suspended"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_GRACE, "Grace"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_CANCELLED = "cancelled"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
        (PAYMENT_CANCELLED, "Cancelled"),
    ]

    organization = models.OneToOneField(
        ManagedOrganization,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        ManagedPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    starts_at = models.DateTimeField(null=True, blank=True)
    renews_at = models.DateTimeField(null=True, blank=True)
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    last_payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )
    notes = models.TextField(blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name"]

    def __str__(self):
        return f"{self.organization} - {self.plan} ({self.status})"


class ManagedLicenseEvent(models.Model):
    organization = models.ForeignKey(
        ManagedOrganization,
        on_delete=models.CASCADE,
        related_name="license_events",
    )
    subscription = models.ForeignKey(
        ManagedSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")
    action = models.CharField(max_length=64)
    old_status = models.CharField(max_length=20, blank=True, default="")
    new_status = models.CharField(max_length=20, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} - {self.action}"


class CompanySyncKey(models.Model):
    ALGORITHM_ED25519 = "ed25519"
    ALGORITHM_CHOICES = [
        (ALGORITHM_ED25519, "Ed25519"),
    ]

    key_id = models.CharField(max_length=120, unique=True)
    algorithm = models.CharField(
        max_length=20,
        choices=ALGORITHM_CHOICES,
        default=ALGORITHM_ED25519,
    )
    private_key_pem = models.TextField()
    public_key_pem = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return self.key_id


class SyncDeliveryJob(models.Model):
    TARGET_PLAN = "plan"
    TARGET_ORGANIZATION = "organization"
    TARGET_SUBSCRIPTION = "subscription"
    TARGET_CHOICES = [
        (TARGET_PLAN, "Plan"),
        (TARGET_ORGANIZATION, "Organization"),
        (TARGET_SUBSCRIPTION, "Subscription"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_id = models.PositiveIntegerField()
    base_url = models.URLField(blank=True, default="")
    endpoint = models.CharField(max_length=255)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    next_retry_at = models.DateTimeField(null=True, blank=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    last_succeeded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.target_type}:{self.target_id} -> {self.endpoint} ({self.status})"


class OrganizationPasswordResetToken(models.Model):
    organization = models.ForeignKey(
        ManagedOrganization,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token = models.CharField(max_length=64, unique=True)
    delivery_email = models.EmailField(blank=True, default="")
    created_by_username = models.CharField(max_length=150, blank=True, default="")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    last_delivery_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.slug} reset token"
