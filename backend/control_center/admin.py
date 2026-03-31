from django.contrib import admin

from .models import (
    CompanySyncKey,
    ManagedLicenseEvent,
    ManagedOrganization,
    ManagedPlan,
    ManagedSubscription,
    SyncDeliveryJob,
)

admin.site.site_header = "Employment Portal Company Console"
admin.site.site_title = "Employment Portal Company Console"
admin.site.index_title = "Company Control Center"

admin.site.register(ManagedOrganization)
admin.site.register(ManagedPlan)
admin.site.register(ManagedSubscription)
admin.site.register(ManagedLicenseEvent)
admin.site.register(CompanySyncKey)
admin.site.register(SyncDeliveryJob)
