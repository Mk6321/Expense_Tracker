"""Domain exceptions. Routes never build error bodies by hand -- they raise these
and the handlers in app.main render the §7 envelope."""


class AppError(Exception):
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "Request could not be processed."

    def __init__(self, message: str | None = None, error_code: str | None = None):
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found."


class GroupAccessDenied(AppError):
    """Raised as 404 on purpose -- never leak whether a group id exists (§5)."""

    status_code = 404
    error_code = "GROUP_ACCESS_DENIED"
    message = "User does not belong to this group."


class AuthError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Not authenticated."


class PermissionDenied(AppError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed."


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Conflicting state."


class OptimisticLockError(ConflictError):
    error_code = "VERSION_CONFLICT"
    message = "This record was modified by someone else. Reload and try again."
