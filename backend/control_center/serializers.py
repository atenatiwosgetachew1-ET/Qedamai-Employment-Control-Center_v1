from rest_framework import serializers

from .models import (
    CompanySyncKey,
    ManagedLicenseEvent,
    ManagedOrganization,
    ManagedPlan,
    ManagedSubscription,
    OrganizationPasswordResetToken,
    SyncDeliveryJob,
)


class ManagedPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagedPlan
        fields = (
            "id",
            "code",
            "name",
            "description",
            "monthly_price",
            "currency",
            "max_superadmins",
            "max_admins",
            "max_staff",
            "max_customers",
            "feature_flags",
            "is_active",
            "last_synced_at",
            "last_sync_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "last_synced_at", "last_sync_error", "created_at", "updated_at")


class ManagedSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ManagedSubscription
        fields = (
            "id",
            "organization",
            "organization_name",
            "plan",
            "plan_name",
            "status",
            "starts_at",
            "renews_at",
            "grace_ends_at",
            "cancelled_at",
            "last_payment_status",
            "notes",
            "last_synced_at",
            "last_sync_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "last_synced_at", "last_sync_error", "created_at", "updated_at")


class ManagedOrganizationSerializer(serializers.ModelSerializer):
    portal_base_url = serializers.CharField(required=False, allow_blank=True)
    portal_api_base_url = serializers.CharField(required=False, allow_blank=True)
    superadmin_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        style={"input_type": "password"},
    )
    subscription = ManagedSubscriptionSerializer(read_only=True)

    def validate_portal_base_url(self, value):
        value = (value or "").strip()
        if value and "://" not in value:
            value = f"http://{value}"
        validator = serializers.URLField(allow_blank=True, required=False)
        return validator.run_validation(value)

    def validate_portal_api_base_url(self, value):
        value = (value or "").strip()
        if value and "://" not in value:
            value = f"http://{value}"
        validator = serializers.URLField(allow_blank=True, required=False)
        return validator.run_validation(value)

    def create(self, validated_data):
        superadmin_password = validated_data.pop("superadmin_password", "")
        organization = super().create(validated_data)
        if superadmin_password:
            organization.set_superadmin_password(superadmin_password)
            organization.save(update_fields=["superadmin_password_hash", "updated_at"])
        return organization

    def update(self, instance, validated_data):
        superadmin_password = validated_data.pop("superadmin_password", "")
        organization = super().update(instance, validated_data)
        if superadmin_password:
            organization.set_superadmin_password(superadmin_password)
            organization.save(update_fields=["superadmin_password_hash", "updated_at"])
        return organization

    class Meta:
        model = ManagedOrganization
        fields = (
            "id",
            "name",
            "slug",
            "portal_base_url",
            "portal_api_base_url",
            "superadmin_username",
            "superadmin_email",
            "superadmin_password",
            "external_reference",
            "billing_contact_name",
            "billing_contact_email",
            "reputation_tier",
            "status",
            "read_only_mode",
            "notes",
            "subscription",
            "last_synced_at",
            "last_sync_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "last_synced_at", "last_sync_error", "created_at", "updated_at")


class ManagedLicenseEventSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ManagedLicenseEvent
        fields = (
            "id",
            "organization",
            "organization_name",
            "subscription",
            "actor_username",
            "action",
            "old_status",
            "new_status",
            "notes",
            "created_at",
        )
        read_only_fields = fields


class CompanyUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()


class CompanySyncKeyPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySyncKey
        fields = ("key_id", "algorithm", "public_key_pem", "is_active")
        read_only_fields = fields


class CompanySyncKeyAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySyncKey
        fields = (
            "id",
            "key_id",
            "algorithm",
            "public_key_pem",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SyncDeliveryJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncDeliveryJob
        fields = (
            "id",
            "target_type",
            "target_id",
            "base_url",
            "endpoint",
            "payload",
            "status",
            "attempts",
            "last_error",
            "next_retry_at",
            "last_attempted_at",
            "last_succeeded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrganizationPasswordResetTokenSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = OrganizationPasswordResetToken
        fields = (
            "id",
            "organization",
            "organization_name",
            "delivery_email",
            "created_by_username",
            "expires_at",
            "used_at",
            "email_sent_at",
            "last_delivery_error",
            "created_at",
        )
        read_only_fields = fields


class BootstrapPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagedPlan
        fields = (
            "id",
            "code",
            "name",
            "description",
            "monthly_price",
            "currency",
            "max_superadmins",
            "max_admins",
            "max_staff",
            "max_customers",
            "feature_flags",
            "is_active",
        )
        read_only_fields = fields


class BootstrapSubscriptionSerializer(serializers.ModelSerializer):
    plan = BootstrapPlanSerializer(read_only=True)

    class Meta:
        model = ManagedSubscription
        fields = (
            "id",
            "status",
            "starts_at",
            "renews_at",
            "grace_ends_at",
            "cancelled_at",
            "last_payment_status",
            "notes",
            "plan",
        )
        read_only_fields = fields


class BootstrapOrganizationSerializer(serializers.ModelSerializer):
    subscription = BootstrapSubscriptionSerializer(read_only=True)

    class Meta:
        model = ManagedOrganization
        fields = (
            "id",
            "external_reference",
            "name",
            "slug",
            "portal_base_url",
            "portal_api_base_url",
            "superadmin_username",
            "superadmin_email",
            "billing_contact_name",
            "billing_contact_email",
            "reputation_tier",
            "status",
            "read_only_mode",
            "notes",
            "subscription",
        )
        read_only_fields = fields
