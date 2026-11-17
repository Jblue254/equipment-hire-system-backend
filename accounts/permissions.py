from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """
    Allows access only to users with the ADMIN role.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == request.user.Role.ADMIN
        )


class IsAdminOrStorekeeper(BasePermission):
    """
    Allows access to both system roles.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in [
                request.user.Role.ADMIN,
                request.user.Role.STOREKEEPER,
            ]
        )