from rest_framework.permissions import BasePermission

from tenants.models import TenantMembership


class HasTenantRole(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        if not request.user.is_authenticated or tenant is None:
            return False

        return TenantMembership.objects.filter(
            user=request.user,
            business=tenant,
            is_active=True,
            role__in=self.allowed_roles,
        ).exists()


class IsTenantMember(BasePermission):
    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        if not request.user.is_authenticated or tenant is None:
            return False
        return TenantMembership.objects.filter(
            user=request.user,
            business=tenant,
            is_active=True,
        ).exists()


class IsBusinessAdmin(HasTenantRole):
    allowed_roles = (
        TenantMembership.Role.OWNER_ADMIN,
        TenantMembership.Role.MANAGER,
    )