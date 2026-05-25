from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Tenant, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "tenant", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Breathe", {"fields": ("tenant",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Breathe", {"fields": ("tenant",)}),
    )
