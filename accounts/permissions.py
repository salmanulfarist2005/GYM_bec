from rest_framework import permissions

class IsSuperUser(permissions.BasePermission):
    """
    Allow access only to superuser users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.user_type == 'superuser')


class IsGymAdmin(permissions.BasePermission):
    """
    Allow access only to gym admin users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.user_type == 'admin'


class IsMember(permissions.BasePermission):
    """
    Allow access only to member users
    (Changed from IsCustomer to IsMember)
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.user_type == 'member'


class IsGymAdminOrMember(permissions.BasePermission):
    """
    Allow access to gym admins or members
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.user_type in ['admin', 'member'] or request.user.is_superuser)


class IsSuperUserOrAdmin(permissions.BasePermission):
    """
    Allow access to superuser or admin users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.user_type in ['superuser', 'admin'])


class IsCustomer(permissions.BasePermission):
    """
    DEPRECATED: Use IsMember instead
    Kept for backward compatibility
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.user_type == 'customer'
